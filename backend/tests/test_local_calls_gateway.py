"""Task Z17 (audit B3): the small local calls on the original text (understand, the generalize rewrite,
llm_check) use the request's stored trusted local connection through the gateway, like the answers.
Fictional questions; the models are fakes."""
import asyncio

import pytest

from app.core.schemas import AskRequest, EffectiveSettings, PIIResult, RequestContext
from app.core.services import build_services
from app.llm.base import LLMUnavailable
from app.llm.fake import FakeLLMClient
from app.pipeline.steps.generate import llm_flags_health
from app.pipeline.steps.understand import UnderstandStep, local_helper
from tests.conftest import UNDERSTOOD_NOTHING


@pytest.fixture
def services(use_config):
    s = build_services(use_config({"privacy": {"llm_check": True}}))
    s.local_llm = FakeLLMClient("deployment local", model="deployment-local")
    s.understand_llm = FakeLLMClient(UNDERSTOOD_NOTHING, model="deployment-understand")
    return s


def stored(services, monkeypatch, client, trust="trusted_local"):
    """A stored connection of the request's settings, without a database row or a network."""
    monkeypatch.setattr(services.gateway, "resolve", lambda role, settings: (client, trust, "endpoint:7"))


def ctx(endpoint: int | None, question: str = "What does blood pressure measure?") -> RequestContext:
    c = RequestContext(request_id="r", settings=EffectiveSettings(course_id=1, local_endpoint_id=endpoint),
                       request=AskRequest(student_id="s1", topic="high_blood_pressure", question=question))
    c.pii = PIIResult(sanitized_text=question, cloud_safe=True)
    return c


def test_without_a_stored_connection_the_deployment_clients_are_used(services):
    assert local_helper(services, ctx(None), services.understand_llm) is services.understand_llm
    assert local_helper(services, ctx(None), services.local_llm) is services.local_llm


def test_the_stored_trusted_local_connection_is_used(services, monkeypatch):
    vllm = FakeLLMClient('{"personal_health": false}', model="qwen-on-vllm")
    stored(services, monkeypatch, vllm)
    client = local_helper(services, ctx(7), services.understand_llm)
    asyncio.run(client.complete([{"role": "user", "content": "q"}], max_tokens=50))
    assert vllm.calls and vllm.calls[0]["max_tokens"] == 50 and not services.understand_llm.calls


def test_an_external_connection_never_gets_the_original_text(services, monkeypatch):
    cloud = FakeLLMClient("should not be called")
    stored(services, monkeypatch, cloud, trust="external")
    client = local_helper(services, ctx(7), services.understand_llm)
    with pytest.raises(LLMUnavailable):
        asyncio.run(client.complete([{"role": "user", "content": "q"}]))
    assert not cloud.calls


def test_llm_check_runs_on_the_stored_connection_and_fails_closed(services, monkeypatch):
    vllm = FakeLLMClient('{"personal_health": true}', model="qwen-on-vllm")
    stored(services, monkeypatch, vllm)
    c = ctx(7, "My mother takes metformin for her diabetes, is that common?")
    assert asyncio.run(llm_flags_health(c, services)) is True
    assert vllm.calls and not services.understand_llm.calls
    stored(services, monkeypatch, vllm, trust="external")  # refused: the question stays local
    assert asyncio.run(llm_flags_health(ctx(7, c.request.question), services)) is True


def test_the_understand_step_uses_the_stored_connection(services, monkeypatch):
    vllm = FakeLLMClient(UNDERSTOOD_NOTHING, model="qwen-on-vllm")
    stored(services, monkeypatch, vllm)
    asyncio.run(UnderstandStep(services).run(ctx(7)))
    assert len(vllm.calls) == 1 and not services.understand_llm.calls


def test_a_connection_that_cannot_be_resolved_keeps_the_question_local(services, monkeypatch):
    from app.llm.ssrf import UnsafeEndpoint

    def broken(role, settings):
        raise UnsafeEndpoint("the name does not resolve")
    monkeypatch.setattr(services.gateway, "resolve", broken)
    c = ctx(7, "My mother takes metformin for her diabetes, is that common?")
    assert asyncio.run(llm_flags_health(c, services)) is True  # fails closed, does not raise
    assert c.pii.llm_checked
