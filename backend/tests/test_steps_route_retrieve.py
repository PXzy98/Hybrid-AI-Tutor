import pytest

from app.core.schemas import (
    AskRequest,
    LearnerContext,
    PIIResult,
    RequestContext,
    Understanding,
)
from app.core.services import build_services
from app.pipeline.steps.retrieve import RetrieveStep
from app.pipeline.steps.route import RouteStep

QUESTION = "How does salt affect blood pressure?"


def make_ctx(cloud_safe=True, **kw) -> RequestContext:
    req = AskRequest(student_id="s", topic="high_blood_pressure", question=QUESTION)
    ctx = RequestContext(request_id="r", request=req, **kw)
    ctx.pii = PIIResult(sanitized_text=QUESTION, cloud_safe=cloud_safe, is_sensitive=not cloud_safe)
    return ctx


@pytest.mark.parametrize(
    ("stub_score", "cloud_safe", "target"),
    [(0.0, True, "local"), (0.6, True, "cloud"), (0.9, True, "cloud"), (0.9, False, "local")],
)
async def test_route_threshold_and_force_local(use_config, stub_score, cloud_safe, target):
    services = build_services(use_config({"routing": {"stub_score": stub_score}}))
    ctx = await RouteStep(services).run(make_ctx(cloud_safe=cloud_safe))
    assert ctx.target == target
    assert ctx.route.score == stub_score
    if not cloud_safe and stub_score >= 0.6:
        assert "forced local: not cloud_safe" in ctx.route.reasons


async def test_force_local_can_be_disabled(use_config):
    services = build_services(use_config({"routing": {"stub_score": 0.9,
                                                      "force_local_if_not_cloud_safe": False}}))
    ctx = await RouteStep(services).run(make_ctx(cloud_safe=False))
    assert ctx.target == "cloud"


async def test_route_defaults_to_local_when_it_fails(use_config):
    services = build_services(use_config())
    ctx = make_ctx()
    ctx.pii = None
    with pytest.raises(RuntimeError):
        await RouteStep(services).run(ctx)
    assert ctx.target == "local"


async def test_retrieve_passes_sanitized_query_kcs_and_level(use_config):
    services = build_services(use_config({"rag": {"impl": "fixture", "k": 2}}))
    seen = {}
    real = services.retriever.retrieve

    def spy(query, topic, k, kc_ids, level):
        seen.update(query=query, topic=topic, k=k, kc_ids=kc_ids, level=level)
        return real(query, topic, k, kc_ids, level)

    services.retriever.retrieve = spy
    ctx = make_ctx(learner=LearnerContext(focus_level="basic"), understanding=Understanding(kc_ids=["HBP.5"]))
    ctx = await RetrieveStep(services).run(ctx)
    assert seen == {"query": "How does salt affect blood pressure?", "topic": "high_blood_pressure", "k": 2,
                    "kc_ids": ["HBP.5"], "level": "basic"}
    assert len(ctx.passages) == 2 and ctx.passages[0].kc_ids == ["HBP.5"]


async def test_retrieve_ignores_unpersonalized_learner(use_config):
    services = build_services(use_config({"rag": {"impl": "fixture"}}))
    ctx = await RetrieveStep(services).run(make_ctx(learner=LearnerContext(personalized=False)))
    assert ctx.passages  # topic-only results, no level filter
