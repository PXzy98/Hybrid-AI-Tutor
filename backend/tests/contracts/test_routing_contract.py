"""Contract for every registered router (Tongkai's implementation is picked up automatically).

Run only these: python -m pytest tests/contracts -k routing
"""
import time

import pytest

from app.core.registry import import_submodules, routers
from app.core.schemas import PIIEntity, PIIResult, RouteInput, RouteScore
from app.routing.interface import RouteScorer

import_submodules("app.routing")

CLEAN = PIIResult(sanitized_text="What is high blood pressure?")
SENSITIVE = PIIResult(
    entities=[PIIEntity(type="HEALTH_DETAIL", text="I have asthma", start=0, end=13, score=0.9,
                        placeholder="<HEALTH_DETAIL_1>")],
    is_sensitive=True, cloud_safe=False,
    sanitized_text="<HEALTH_DETAIL_1>. Why does my inhaler make me shaky?",
)
INPUTS = [
    RouteInput(sanitized_question="What is high blood pressure?", topic="high_blood_pressure", pii=CLEAN,
               passage_count=4),
    RouteInput(sanitized_question="", topic="asthma", pii=PIIResult(sanitized_text=""), passage_count=0),
    RouteInput(sanitized_question=SENSITIVE.sanitized_text, topic="asthma", pii=SENSITIVE, passage_count=2,
               level="basic", kc_ids=["AST.2"]),
    RouteInput(sanitized_question="Compare the long-term kidney effects of untreated hypertension " * 40,
               topic="high_blood_pressure", pii=CLEAN, passage_count=0, level="advanced"),
]


@pytest.fixture(params=routers.names())
def router(request) -> RouteScorer:
    return routers.get(request.param)()


def test_implements_protocol(router):
    assert isinstance(router, RouteScorer)


@pytest.mark.parametrize("x", INPUTS, ids=["clean", "empty", "sensitive", "long"])
def test_score_in_range_and_fast(router, x):
    t0 = time.perf_counter()
    out = router.route_score(x)
    assert time.perf_counter() - t0 < 1.0
    assert isinstance(out, RouteScore)
    assert 0.0 <= out.score <= 1.0


@pytest.mark.parametrize("x", INPUTS, ids=["clean", "empty", "sensitive", "long"])
def test_deterministic(router, x):
    assert router.route_score(x) == router.route_score(x)
