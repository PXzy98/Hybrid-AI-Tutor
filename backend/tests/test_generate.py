import pytest

from app.core.schemas import AskRequest, Chunk, LearnerContext, PIIResult, RequestContext, Turn
from app.core.services import build_services
from app.llm.base import LLMError, LLMUnavailable
from app.llm.cloud_guard import CloudClient
from app.llm.fake import FakeLLMClient
from app.pipeline.steps.generate import CLOUD_FALLBACK_WARNING, GenerateStep
from app.prompts import base_system, render_local

RAW = "I'm Bob Ng. How does salt raise blood pressure?"


def make_ctx(target="local", learner=None) -> RequestContext:
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s1", topic="high_blood_pressure",
                                                            question=RAW), target=target, learner=learner)
    sanitized = "I'm <PERSON_1>. How does salt raise blood pressure?"
    ctx.pii = PIIResult(sanitized_text=sanitized, is_sensitive=True)
    ctx.history = [Turn(role="student", text="What is blood pressure?"), Turn(role="tutor", text="It is ...")]
    ctx.passages = [Chunk(text="Salt makes the body hold water.", source="s.md", topic="high_blood_pressure",
                          score=1.0)]
    return ctx


@pytest.fixture
def services(use_config):
    def _make(fallback=True):
        s = build_services(use_config({"llm": {"cloud": {"fallback_to_local": fallback}}}))
        s.local_llm = FakeLLMClient("local answer", model="fake-local")
        return s
    return _make


def test_render_local_uses_full_context():
    ctx = make_ctx(learner=LearnerContext(focus_level="basic"))
    msgs = render_local(ctx)
    assert msgs[0]["role"] == "system" and msgs[0]["content"].startswith(base_system())
    assert "Teaching level for this student: basic" in msgs[0]["content"]
    assert [m["role"] for m in msgs] == ["system", "user", "assistant", "user"]  # history before the question
    last = msgs[-1]["content"]
    assert "Topic: High Blood Pressure" in last and "[1] Salt makes the body hold water." in last
    assert last.endswith(f"Student question: {RAW}")  # the local model may see the original question


def test_render_local_without_material_or_personalization():
    ctx = make_ctx(learner=LearnerContext(personalized=False))
    ctx.passages, ctx.history = [], []
    msgs = render_local(ctx)
    assert "Teaching level" not in msgs[0]["content"]
    assert "Course material: none was found for this question." in msgs[-1]["content"]


async def test_local_route(services):
    s = services()
    ctx = await GenerateStep(s).run(make_ctx("local"))
    assert ctx.answer == "local answer" and ctx.llm.model == "fake-local" and ctx.llm.fell_back is False
    assert ctx.cloud_request is None
    assert RAW in s.local_llm.sent_text()


async def test_cloud_route_sends_only_the_cloud_request(services):
    s = services()
    transport = FakeLLMClient("cloud answer", model="gpt-test", backend="cloud")
    s.cloud_llm = CloudClient(transport)
    ctx = await GenerateStep(s).run(make_ctx("cloud", learner=LearnerContext(focus_level="advanced")))
    assert ctx.answer == "cloud answer" and ctx.llm.backend == "cloud"
    assert ctx.cloud_request is not None and ctx.cloud_request.labels.level == "advanced"
    assert s.local_llm.calls == []  # the local model was not used
    sent = transport.sent_text()
    assert "Bob" not in sent and "s1" not in sent and "What is blood pressure?" not in sent  # no history


@pytest.mark.parametrize("failure", ["not_configured", "error"])
async def test_cloud_failure_falls_back_to_local(services, failure):
    s = services()
    if failure == "error":
        s.cloud_llm = CloudClient(FakeLLMClient(LLMUnavailable("down")))
    ctx = await GenerateStep(s).run(make_ctx("cloud"))
    assert ctx.answer == "local answer" and ctx.llm.fell_back is True and ctx.llm.backend == "local"
    assert ctx.warnings == [CLOUD_FALLBACK_WARNING]


async def test_no_fallback_when_disabled(services):
    s = services(fallback=False)
    with pytest.raises(LLMError):
        await GenerateStep(s).run(make_ctx("cloud"))
    s.cloud_llm = CloudClient(FakeLLMClient(LLMError("bad")))
    with pytest.raises(LLMError):
        await GenerateStep(s).run(make_ctx("cloud"))


async def test_local_failure_propagates(services):
    s = services()
    s.local_llm = FakeLLMClient(LLMUnavailable("ollama down"))
    with pytest.raises(LLMUnavailable):
        await GenerateStep(s).run(make_ctx("local"))
