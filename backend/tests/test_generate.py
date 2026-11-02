import pytest

from app.core.schemas import AskRequest, Chunk, LearnerContext, PIIResult, RequestContext, Turn
from app.core.services import build_services
from app.llm.base import LLMError, LLMUnavailable
from app.llm.cloud_guard import CloudClient
from app.llm.fake import FakeLLMClient
from app.pipeline.steps.generate import (
    CLOUD_FALLBACK_WARNING,
    CLOUD_MISSING_WARNING,
    LOCAL_CAPABILITY_NOTE,
    PRIVACY_BLOCK_WARNING,
    GenerateStep,
)
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
    def _make(fallback=True, policy="local_only"):
        s = build_services(use_config({"llm": {"cloud": {"fallback_to_local": fallback}},
                                       "privacy": {"health_detail_policy": policy}}))
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
    reason = CLOUD_FALLBACK_WARNING if failure == "error" else CLOUD_MISSING_WARNING
    assert ctx.warnings == [reason, LOCAL_CAPABILITY_NOTE]  # why, and that the router expected the cloud


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


HEALTH = "I have asthma, can I still run?"


def health_ctx() -> RequestContext:
    ctx = make_ctx("cloud")
    ctx.request = ctx.request.model_copy(update={"question": HEALTH})
    ctx.pii = PIIResult(sanitized_text="I have <HEALTH_DETAIL_1>, can I still run?", is_sensitive=True,
                        cloud_safe=False)
    return ctx


async def test_leak_guard_blocks_whatever_the_router(services):
    """The guard no longer depends on routing.impl: a name the filter missed never leaves."""
    s = services()
    transport = FakeLLMClient("cloud answer", backend="cloud")
    s.cloud_llm = CloudClient(transport)
    ctx = make_ctx("cloud")
    ctx.pii = PIIResult(sanitized_text="I'm Bob Ng. How does salt raise blood pressure?", is_sensitive=False)
    ctx = await GenerateStep(s).run(ctx)
    assert transport.calls == [] and ctx.cloud_request is None
    assert ctx.answer == "local answer" and ctx.warnings == [PRIVACY_BLOCK_WARNING, LOCAL_CAPABILITY_NOTE]


async def test_personal_health_stays_local_by_default(services):
    s = services()
    transport = FakeLLMClient("cloud answer", backend="cloud")
    s.cloud_llm = CloudClient(transport)
    ctx = await GenerateStep(s).run(health_ctx())
    assert transport.calls == [] and ctx.answer == "local answer" and ctx.llm.fell_back is True
    assert ctx.warnings[0] == PRIVACY_BLOCK_WARNING


async def test_generalize_sends_only_the_checked_rewrite(services):
    s = services(policy="generalize")
    s.local_llm = FakeLLMClient(["Can a person with asthma run safely?", "local answer"])
    transport = FakeLLMClient("cloud answer", backend="cloud")
    s.cloud_llm = CloudClient(transport)
    ctx = await GenerateStep(s).run(health_ctx())
    assert ctx.answer == "cloud answer" and ctx.warnings == []
    assert ctx.cloud_request.sanitized_question == "Can a person with asthma run safely?"
    sent = transport.sent_text()
    assert "I have" not in sent and "HEALTH_DETAIL" not in sent


@pytest.mark.parametrize("rewrite", ["Can I run with my asthma?", "Is running safe with a peak flow of 300?",
                                     "Can Bob Ng run with asthma?"])
async def test_generalize_rejects_a_personal_rewrite(services, rewrite):
    s = services(policy="generalize")
    s.local_llm = FakeLLMClient([rewrite, "local answer"])
    transport = FakeLLMClient("cloud answer", backend="cloud")
    s.cloud_llm = CloudClient(transport)
    ctx = await GenerateStep(s).run(health_ctx())
    assert transport.calls == [] and ctx.answer == "local answer"
    assert ctx.warnings[0] == PRIVACY_BLOCK_WARNING


# ------------------------------------------------------------- privacy.llm_check (Beta) at the cloud gate
def llm_check_ctx(question: str) -> RequestContext:
    ctx = RequestContext(request_id="r", target="cloud",
                         request=AskRequest(student_id="s1", topic="asthma", question=question))
    ctx.pii = PIIResult(sanitized_text=question.replace("300418277", "<STUDENT_ID_1>"), cloud_safe=True)
    return ctx


@pytest.mark.parametrize(("reply", "question", "cloud", "called"), [
    ('{"personal_health": true}', "Is a cough at night a sign of asthma?", False, True),
    ('{"personal_health": false}', "What triggers asthma attacks?", True, True),
    (LLMError("timeout"), "What triggers asthma attacks?", False, True),  # fails closed
    ("not json", "What triggers asthma attacks?", False, True),
    ('{"personal_health": true}', "When is the quiz due?", True, False),  # no health topic: no call
])
async def test_llm_check_at_the_cloud_gate(use_config, reply, question, cloud, called):
    s = build_services(use_config({"privacy": {"llm_check": True}}))
    s.local_llm = FakeLLMClient("local answer", model="fake-local")
    s.understand_llm = FakeLLMClient(reply)
    s.cloud_llm = CloudClient(FakeLLMClient("cloud answer", model="gpt-test", backend="cloud"))
    ctx = await GenerateStep(s).run(llm_check_ctx(question))
    assert (ctx.llm.backend == "cloud") == cloud
    assert bool(s.understand_llm.calls) == called
    if not cloud:
        assert PRIVACY_BLOCK_WARNING in ctx.warnings and ctx.cloud_request is None


async def test_llm_check_sees_only_the_redacted_text_and_runs_once(use_config):
    s = build_services(use_config({"privacy": {"llm_check": True}}))
    s.understand_llm = FakeLLMClient('{"personal_health": false}')
    s.cloud_llm = CloudClient(FakeLLMClient("cloud answer", model="gpt-test", backend="cloud"))
    step, ctx = GenerateStep(s), llm_check_ctx("My student number is 300418277. What triggers asthma?")
    await step.produce(ctx)
    await step.produce(ctx, safety_retry=True)
    assert len(s.understand_llm.calls) == 1 and "300418277" not in s.understand_llm.sent_text()


async def test_llm_check_is_off_by_default(services):
    s = services()
    s.understand_llm = FakeLLMClient('{"personal_health": true}')
    s.cloud_llm = CloudClient(FakeLLMClient("cloud answer", model="gpt-test", backend="cloud"))
    ctx = await GenerateStep(s).run(make_ctx("cloud"))
    assert ctx.llm.backend == "cloud" and s.understand_llm.calls == []
