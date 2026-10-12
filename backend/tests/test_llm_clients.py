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

    def __init__(self, reply="Cloud answer.", error=None):
        self.kwargs = None
        self.reply, self.error = reply, error
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self._create))

    async def _create(self, **kwargs):
        self.kwargs = kwargs
        if self.error:
            raise self.error
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))],
                               usage=SimpleNamespace(prompt_tokens=11, completion_tokens=22))


async def test_openai_compat_request_and_result():
    fake = FakeOpenAI()
    client = OpenAICompatClient("https://x", "key", "gpt-test", max_tokens=300, client=fake)
    res = await client.complete(MSGS, json_schema={"type": "object"})
    assert fake.kwargs["model"] == "gpt-test" and fake.kwargs["max_tokens"] == 300
    assert fake.kwargs["response_format"] == {"type": "json_object"}
    assert (res.text, res.backend, res.prompt_tokens) == ("Cloud answer.", "cloud", 11)


async def test_openai_compat_maps_errors():
    req = httpx.Request("POST", "https://x")
    down = FakeOpenAI(error=openai.APIConnectionError(request=req))
    client = OpenAICompatClient("https://x", "k", "m", client=down)
    with pytest.raises(LLMUnavailable):
        await client.complete(MSGS)
    client = OpenAICompatClient("https://x", "k", "m", client=FakeOpenAI(reply=""))
    with pytest.raises(LLMError, match="empty"):
        await client.complete(MSGS)


@pytest.mark.ollama
async def test_real_ollama_smoke():
    """Run with: python -m pytest -m ollama  (needs the GPU server)."""
    s = get_settings()
    client = OllamaClient(s.ollama_url, s.llm.local.model, max_tokens=64)
    res = await client.complete([{"role": "user", "content": "Reply with exactly one word: hello"}])
    assert res.text and res.backend == "local" and res.completion_tokens
