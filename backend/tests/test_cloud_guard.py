"""Privacy invariants 2 and 3: only a CloudRequest reaches the cloud, and it carries nothing personal."""
import inspect

import pytest
from pydantic import ValidationError

from app.core.schemas import (
    AskRequest,
    Chunk,
    CloudLabels,
    CloudRequest,
    KcRecommendation,
    KcState,
    LearnerContext,
    MisconceptionRef,
    PIIEntity,
    PIIResult,
    Preferences,
    RequestContext,
    Turn,
)
from app.llm.base import LLMUnavailable
from app.llm.cloud_guard import CloudClient, build_cloud_request
from app.llm.fake import FakeLLMClient
from app.prompts import render_cloud

RAW = "My name is Alice Tremblay, student 300418277, and I have asthma. Why does my inhaler shake me?"
SANITIZED = ("My name is <PERSON_1>, student <STUDENT_ID_1>, and <HEALTH_DETAIL_1>. "
             "Why does my inhaler shake me?")
SECRETS = ["Alice", "Tremblay", "300418277", "I have asthma", "stu-7f3a", "my brother smokes",
           "Inhalers are addictive", "AST.2", "0.37", "AST.3-q1"]


def rich_ctx() -> RequestContext:
    ctx = RequestContext(
        request_id="r-1",
        request=AskRequest(student_id="stu-7f3a", topic="asthma", question=RAW),
        learner=LearnerContext(
            kc_states={"AST.2": KcState(kc_id="AST.2", p_mastery=0.37, level="basic", n_obs=4)},
            focus_level="basic",
            misconceptions=[MisconceptionRef(id="AST.MC1", kc_id="AST.2", statement="Inhalers are addictive",
                                             correction="They are not.", status="confirmed")],
            preferences=Preferences(sequencing="concept_first", detail="detailed", source="onboarding"),
            next_kc=KcRecommendation(kc_id="AST.3", name="Triggers", reason="lowest mastery"),
        ),
        history=[Turn(role="student", text="my brother smokes"), Turn(role="tutor", text="ok")],
        passages=[Chunk(text="Reliever inhalers can cause a fast heartbeat or shaking.", source="m/a.md",
                        topic="asthma", score=0.9, kc_ids=["AST.2"], level="basic")],
    )
    person = PIIEntity(type="PERSON", text="Alice Tremblay", start=11, end=25, score=0.9,
                       placeholder="<PERSON_1>")
    ctx.pii = PIIResult(sanitized_text=SANITIZED, is_sensitive=True, cloud_safe=True, entities=[person])
    ctx.set_pii_mapping({"<PERSON_1>": "Alice Tremblay", "<STUDENT_ID_1>": "300418277"})
    ctx.check_item = None
    return ctx


def test_cloud_request_contains_only_the_allow_list():
    req = build_cloud_request(rich_ctx())
    assert req.model_dump() == {
        "sanitized_question": SANITIZED,
        "topic": "asthma",
        "passages": ["Reliever inhalers can cause a fast heartbeat or shaking."],
        "labels": {"level": "basic", "sequencing": "concept_first", "detail": "detailed"},
        "language": "en",
    }
    dumped = req.model_dump_json()
    for secret in SECRETS:
        assert secret not in dumped


def test_unpersonalized_learner_gets_default_labels():
    ctx = rich_ctx()
    ctx.learner = LearnerContext(personalized=False, focus_level="advanced")
    assert build_cloud_request(ctx).labels == CloudLabels(level="intermediate", sequencing="example_first",
                                                         detail="concise")
    ctx.learner = None
    assert build_cloud_request(ctx).labels.level == "intermediate"


def test_no_privacy_result_no_cloud_request():
    ctx = rich_ctx()
    ctx.pii = None
    with pytest.raises(ValueError):
        build_cloud_request(ctx)


async def test_cloud_messages_carry_nothing_personal():
    transport = FakeLLMClient("Cloud answer about <PERSON_1>.", model="gpt-test", backend="cloud")
    cloud = CloudClient(transport)
    res = await cloud.complete(build_cloud_request(rich_ctx()))
    assert res.backend == "cloud" and res.text == "Cloud answer about <PERSON_1>."
    sent = transport.sent_text()
    assert "<PERSON_1>" in sent and "Keep them exactly as written" in sent
    assert "Teaching level for this student: basic" in sent
    for secret in SECRETS:
        assert secret not in sent


async def test_cloud_client_accepts_only_cloud_requests():
    cloud = CloudClient(FakeLLMClient())
    ok = build_cloud_request(rich_ctx())
    with pytest.raises(TypeError):
        await cloud.complete(ok.model_dump())  # a dict is not a CloudRequest
    with pytest.raises(TypeError):
        await cloud.complete(rich_ctx())
    fields = ok.model_dump() | {"labels": ok.labels}
    sneaky = CloudRequest.model_construct(**fields, student_id="stu-7f3a")  # skips validation
    await cloud.complete(sneaky)
    assert "stu-7f3a" not in cloud._transport.sent_text()


async def test_cloud_client_unavailable_without_transport():
    cloud = CloudClient(None)
    assert cloud.available is False and cloud.model is None
    with pytest.raises(LLMUnavailable):
        await cloud.complete(build_cloud_request(rich_ctx()))


def test_render_cloud_signature_takes_only_a_cloud_request():
    params = list(inspect.signature(render_cloud).parameters.values())
    assert [p.name for p in params] == ["req"] and params[0].annotation is CloudRequest


def test_cloud_request_schema_has_no_room_for_profile_data():
    with pytest.raises(ValidationError):
        CloudRequest(sanitized_question="q", topic="asthma", labels=CloudLabels(
            level="basic", sequencing="example_first", detail="concise"), kc_states={})
