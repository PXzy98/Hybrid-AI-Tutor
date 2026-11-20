import json
from types import SimpleNamespace

import httpx
import openai
import pytest

from app.core.config import get_settings
from app.llm.base import LLMError, LLMUnavailable
from app.llm.ollama_client import OllamaClient
from app.llm.openai_compat import OpenAICompatClient

MSGS = [{"role": "system", "content": "s"}, {"role": "user", "content": "What is asthma?"}]
OK = {"message": {"role": "assistant", "content": "Asthma is ..."}, "prompt_eval_count": 42, "eval_count": 7}


def ollama(handler, **kw) -> tuple[OllamaClient, list[dict]]:
    seen: list[dict] = []

    def wrapped(request: httpx.Request) -> httpx.Response:
        seen.append(json.loads(request.content))
        return handler(request)

    transport = httpx.MockTransport(wrapped)
    client = OllamaClient("http://ollama.test:11434/", "qwen3.5:9b", transport=transport, **kw)
    return client, seen


async def test_ollama_request_body_and_result():
    client, seen = ollama(lambda r: httpx.Response(200, json=OK),
                          temperature=0.1, num_ctx=4096, max_tokens=256)
    res = await client.complete(MSGS)
    body = seen[0]
    assert body["think"] is False and body["stream"] is False  # thinking always off
    assert body["model"] == "qwen3.5:9b" and body["messages"] == MSGS
    assert body["options"] == {"temperature": 0.1, "num_ctx": 4096, "num_predict": 256}
    assert "format" not in body
    assert (res.text, res.backend) == ("Asthma is ...", "local")
    assert (res.prompt_tokens, res.completion_tokens) == (42, 7)


async def test_ollama_json_schema_and_max_tokens_override():
    client, seen = ollama(lambda r: httpx.Response(200, json=OK))
    schema = {"type": "object", "properties": {"kc_ids": {"type": "array"}}}
    await client.complete(MSGS, json_schema=schema, max_tokens=64)
    assert seen[0]["format"] == schema and seen[0]["options"]["num_predict"] == 64


async def test_ollama_strips_think_blocks():
    reply = {"message": {"content": "<think>hmm</think>\nThe answer."}}
    client, _ = ollama(lambda r: httpx.Response(200, json=reply))
    assert (await client.complete(MSGS)).text == "The answer."


async def test_ollama_retries_once_on_connection_error():
    attempts = []

    def flaky(request):
        attempts.append(1)
        if len(attempts) == 1:
            raise httpx.ConnectError("refused", request=request)
        return httpx.Response(200, json=OK)

    client, _ = ollama(flaky)
    assert (await client.complete(MSGS)).text == "Asthma is ..."
    assert len(attempts) == 2


async def test_ollama_unreachable_after_retry():
    def down(request):
        raise httpx.ConnectError("refused", request=request)

    client, _ = ollama(down)
    with pytest.raises(LLMUnavailable, match="unreachable"):
        await client.complete(MSGS)


async def test_ollama_timeout_is_not_retried():
    calls = []

    def slow(request):
        calls.append(1)
        raise httpx.ReadTimeout("slow", request=request)

    client, _ = ollama(slow)
    with pytest.raises(LLMUnavailable, match="timed out"):
        await client.complete(MSGS)
    assert len(calls) == 1


@pytest.mark.parametrize(
    ("response", "match"),
    [(httpx.Response(404, json={"error": "model 'x' not found"}), "HTTP 404"),
     (httpx.Response(200, json={"message": {"content": "  "}}), "empty"),
     (httpx.Response(200, text="not json"), "invalid JSON")],
)
async def test_ollama_bad_replies(response, match):
    client, _ = ollama(lambda r: response)
    with pytest.raises(LLMError, match=match) as e:
        await client.complete(MSGS)
    assert "asthma" not in str(e.value).lower()  # errors never echo the prompt


class FakeOpenAI:
    """Stands in for openai.AsyncOpenAI: records kwargs, returns a canned completion or raises."""

    def __init__(self, reply="Cloud answer.", error=None, finish_reason="stop"):
        self.kwargs = None
        self.reply, self.error, self.finish_reason = reply, error, finish_reason
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply),
                                                        finish_reason=self.finish_reason)],
                               usage=SimpleNamespace(prompt_tokens=11, completion_tokens=22))


async def test_openai_compat_request_and_result():
    fake = FakeOpenAI()
    client = OpenAICompatClient("https://x", "key", "gpt-test", max_tokens=300, client=fake)
    res = await client.complete(MSGS, json_schema={"type": "object"})
    assert fake.kwargs["model"] == "gpt-test" and fake.kwargs["max_tokens"] == 300
    assert fake.kwargs["response_format"] == {"type": "json_object"}
    assert (res.text, res.backend, res.prompt_tokens) == ("Cloud answer.", "cloud", 11)


async def test_openai_compat_thinking_off_only_when_asked():
    """vLLM (a trusted local connection) gets thinking switched off; hosted APIs reject the extra field."""
    hosted = FakeOpenAI()
    await OpenAICompatClient("https://x", "k", "m", client=hosted).complete(MSGS)
    assert "extra_body" not in hosted.kwargs
    own = FakeOpenAI()
    await OpenAICompatClient("http://10.0.0.5:8000/v1", "k", "m", client=own,
                             thinking_off=True).complete(MSGS)
    assert own.kwargs["extra_body"] == {"chat_template_kwargs": {"enable_thinking": False}}


def test_trusted_local_connections_switch_thinking_off():
    from app.llm.endpoints import build_client
    from app.storage.models import ModelEndpoint

    def row(trust):
        return ModelEndpoint(name="n", kind="openai_compat", base_url="http://10.0.0.5:8000/v1", model="m",
                             trust=trust)

    assert build_client(row("trusted_local"), None)._extra
    assert not build_client(row("external"), None)._extra
    assert build_client(row("trusted_local"), None).schema_output
    assert not build_client(row("external"), None).schema_output
    assert build_client(row("trusted_local"), None).backend == "local"
    assert build_client(row("external"), None).backend == "cloud"


async def test_the_deployment_local_model_is_its_vllm(use_config, monkeypatch):
    """VLLM_BASE_URL / VLLM_KEY: both local clients (answers and understand) are OpenAI-compatible, trusted
    local (thinking off, the JSON schema, answers reported as local) and send the key."""
    from app.llm.factory import build_llm_clients

    monkeypatch.setenv("VLLM_BASE_URL", "http://10.0.0.5:8000/v1/")
    monkeypatch.setenv("VLLM_KEY", "fictional-key")
    local, _, understand = build_llm_clients(use_config())
    for client in (local, understand):
        assert isinstance(client, OpenAICompatClient)
        assert client._args["base_url"] == "http://10.0.0.5:8000/v1"
        assert client._args["api_key"] == "fictional-key"
        assert client._extra and client.schema_output and client.backend == "local"
    assert local.model == "Qwen3.5-9B" and understand.temperature == 0.0
    fake = FakeOpenAI(reply="Local answer.")
    local._injected = fake
    assert (await local.complete(MSGS)).backend == "local"


async def test_without_vllm_url_the_local_model_is_unavailable(use_config, monkeypatch):
    from app.llm.factory import NoLocalServer, build_llm_clients

    monkeypatch.setenv("VLLM_BASE_URL", "")
    local, _, understand = build_llm_clients(use_config())
    assert isinstance(local, NoLocalServer) and isinstance(understand, NoLocalServer)
    with pytest.raises(LLMUnavailable, match="VLLM_BASE_URL"):
        await local.complete(MSGS)
    with pytest.raises(LLMUnavailable):
        async for _ in local.stream(MSGS):
            pass


async def test_self_hosted_server_gets_the_json_schema():
    """vLLM with only "json_object" makes up its own field names and every structured draft fails
    validation; the course's own server is given the schema to constrain the answer."""
    schema = {"type": "object", "properties": {"items": {"type": "array"}}}
    own = FakeOpenAI(reply="{}")
    await OpenAICompatClient("http://10.0.0.5:8000/v1", "k", "m", client=own,
                             schema_output=True).complete(MSGS, json_schema=schema, max_tokens=4096)
    assert own.kwargs["response_format"] == {"type": "json_schema",
                                             "json_schema": {"name": "answer", "schema": schema}}
    assert own.kwargs["max_tokens"] == 4096


async def test_openai_compat_maps_errors():
    req = httpx.Request("POST", "https://x")
    down = FakeOpenAI(error=openai.APIConnectionError(request=req))
    client = OpenAICompatClient("https://x", "k", "m", client=down)
    with pytest.raises(LLMUnavailable):
        await client.complete(MSGS)
    client = OpenAICompatClient("https://x", "k", "m", client=FakeOpenAI(reply=""))
    with pytest.raises(LLMError, match="empty"):
        await client.complete(MSGS)


async def test_a_failed_model_call_names_the_model_without_class_names():
    req = httpx.Request("POST", "https://x")
    down = FakeOpenAI(error=openai.APIConnectionError(request=req))
    local = OpenAICompatClient("https://x", "k", "m", client=down, backend="local")
    with pytest.raises(LLMUnavailable) as caught:
        await local.complete(MSGS)
    assert str(caught.value) == "the local model cannot be reached; check the model connection"
    slow = FakeOpenAI(error=openai.APITimeoutError(request=req))
    cloud = OpenAICompatClient("https://x", "k", "m", client=slow)
    with pytest.raises(LLMUnavailable, match="^the cloud model did not answer in time"):
        await cloud.complete(MSGS)
    with pytest.raises(LLMUnavailable) as caught:
        async for _ in local.stream(MSGS):
            pass
    assert "local model" in str(caught.value) and "Error" not in str(caught.value)


async def test_openai_compat_reasoning_used_the_whole_budget(caplog):
    """deepseek-flash: hidden reasoning counts against max_tokens and can leave no answer text."""
    client = OpenAICompatClient("https://x", "k", "m", client=FakeOpenAI(reply="", finish_reason="length"))
    with pytest.raises(LLMError, match="cut off"):
        await client.complete(MSGS)
    half = FakeOpenAI(reply="Half an ans", finish_reason="length")
    client = OpenAICompatClient("https://x", "k", "m", client=half)
    res = await client.complete(MSGS)
    assert res.text == "Half an ans" and "cut off" in caplog.text


@pytest.mark.local_model
async def test_real_local_model_smoke():
    """Run with: python -m pytest -m local_model  (needs the vLLM server of VLLM_BASE_URL)."""
    from app.llm.factory import build_local_client

    s = get_settings()
    client = build_local_client(s, s.llm.local.model, temperature=0.0, timeout_s=60, max_tokens=64)
    res = await client.complete([{"role": "user", "content": "Reply with exactly one word: hello"}])
    assert res.text and res.backend == "local" and res.completion_tokens
