import pytest
from pydantic import ValidationError

from app.core.schemas import (
    AskRequest,
    CheckItemPublic,
    CloudLabels,
    CloudRequest,
    LearnerContext,
    MisconceptionRef,
    Preferences,
    RequestContext,
    RouteScore,
)

LABELS = {"level": "basic", "sequencing": "example_first", "detail": "concise"}


def make_ctx(**kw) -> RequestContext:
    req = AskRequest(student_id="s-1", topic="asthma", question="<PERSON_9> asks: what is asthma?")
    return RequestContext(request_id="r-1", request=req, **kw)


@pytest.mark.parametrize("extra", [{"student_id": "s-1"}, {"history": []}, {"misconceptions": ["x"]}])
def test_cloud_request_rejects_extra_fields(extra):
    with pytest.raises(ValidationError):
        CloudRequest(sanitized_question="What is asthma?", topic="asthma", labels=CloudLabels(**LABELS),
                     **extra)


def test_cloud_labels_reject_extra_fields():
    with pytest.raises(ValidationError):
        CloudLabels(**LABELS, p_mastery=0.3)


def test_check_item_public_has_no_answer_key():
    assert "answer" not in CheckItemPublic.model_fields
    with pytest.raises(ValidationError):
        CheckItemPublic(id="HBP.1-q1", kc_id="HBP.1", stem="?", options={"A": "a"}, answer="A")


def test_pii_mapping_is_never_serialized():
    ctx = make_ctx()
    ctx.set_pii_mapping({"<PERSON_1>": "Alice Tremblay"})
    assert ctx.pii_mapping == {"<PERSON_1>": "Alice Tremblay"}
    for dumped in (str(ctx.model_dump()), ctx.model_dump_json(), repr(ctx), str(ctx)):
        assert "Alice Tremblay" not in dumped and "<PERSON_1>" not in dumped
    ctx.clear_pii_mapping()
    assert ctx.pii_mapping == {}


def test_to_cloud_labels_carries_only_coarse_labels():
    lc = LearnerContext(
        focus_level="advanced",
        preferences=Preferences(sequencing="concept_first", detail="detailed", source="onboarding"),
        misconceptions=[MisconceptionRef(id="HBP.MC2", kc_id="HBP.6", statement="s", correction="c",
                                         status="confirmed")],
    )
    labels = lc.to_cloud_labels()
    assert labels.model_dump() == {"level": "advanced", "sequencing": "concept_first", "detail": "detailed"}


def test_learner_context_defaults_are_unpersonalized_safe():
    lc = LearnerContext()
    assert lc.focus_level == "intermediate"
    assert lc.preferences == Preferences()
    assert lc.to_cloud_labels().level == "intermediate"


@pytest.mark.parametrize("score", [-0.1, 1.01])
def test_route_score_bounds(score):
    with pytest.raises(ValidationError):
        RouteScore(score=score)


def test_ask_request_rejects_empty_question():
    with pytest.raises(ValidationError):
        AskRequest(student_id="s-1", topic="asthma", question="")
