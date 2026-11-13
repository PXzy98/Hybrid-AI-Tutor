"""T5: the question type head, its place in the route step, and its use in retrieval. Fictional data only."""
import json

import numpy as np
import pytest

from app.core.config import RoutingConfig
from app.core.schemas import (
    AskRequest,
    PIIResult,
    RequestContext,
    RouteScore,
    SemanticAnalysis,
    Turn,
)
from app.core.services import build_services
from app.pipeline.steps.analyze_route import AnalyzeRouteStep
from app.pipeline.steps.retrieve import RetrieveStep
from app.platform import course_scope
from app.rag.course import FakeCourseRetriever
from app.routing import question_type
from app.routing.semantic import SemanticRouter

DIMENSION = 4


def write_head(folder, *, encoder="test-encoder", threshold=0.5, dimension=DIMENSION, schema=1):
    """A hand-made head: axis 0 of the embedding means logistics, axis 1 means concept."""
    metadata = {"schema_version": schema, "embedding_model": encoder, "dimension": dimension,
                "threshold": threshold}
    coef = np.zeros(dimension, dtype=np.float32)
    coef[0], coef[1] = 6.0, -6.0
    np.savez_compressed(folder / question_type.WEIGHTS_NAME, metadata=np.array(json.dumps(metadata)),
                        coef=coef, intercept=np.zeros(1, dtype=np.float32))


def config(folder, encoder="test-encoder"):
    return RoutingConfig(model_dir=str(folder), embedding_model=encoder)


LOGISTICS = np.array([1, 0, 0, 0], dtype=np.float32)
CONCEPT = np.array([0, 1, 0, 0], dtype=np.float32)


def test_head_separates_fixed_examples(tmp_path):
    write_head(tmp_path)
    cfg = config(tmp_path)
    assert question_type.classify(LOGISTICS, cfg) == "logistics"
    assert question_type.classify(CONCEPT, cfg) == "concept"
    metadata, arrays = question_type.load_weights(cfg)
    assert question_type.logistics_probability(LOGISTICS, metadata, arrays) > 0.99
    assert question_type.logistics_probability(CONCEPT, metadata, arrays) < 0.01
    assert question_type.logistics_probability(np.zeros(DIMENSION, dtype=np.float32), metadata, arrays) == 0.5


def test_threshold_comes_from_the_weight_file(tmp_path):
    write_head(tmp_path, threshold=0.999999)
    weak = np.array([0.5, 0, 0, 0], dtype=np.float32)  # p = 0.95
    assert question_type.classify(weak, config(tmp_path)) == "concept"
    write_head(tmp_path, threshold=0.9)
    assert question_type.classify(weak, config(tmp_path)) == "logistics"


def test_unusable_head_means_concept(tmp_path):
    cfg = config(tmp_path)
    assert question_type.classify(LOGISTICS, cfg) == "concept"  # no file
    write_head(tmp_path, encoder="another-encoder")
    assert question_type.classify(LOGISTICS, cfg) == "concept"  # trained on another encoder
    write_head(tmp_path)
    assert question_type.classify(np.ones(3, dtype=np.float32), cfg) == "concept"  # wrong dimension
    assert question_type.classify(np.full(DIMENSION, np.nan, dtype=np.float32), cfg) == "concept"
    write_head(tmp_path, schema=2)
    assert question_type.classify(LOGISTICS, cfg) == "concept"  # unknown format


def test_shipped_head_on_fixed_questions():
    """The weights in data/routing/models with the real local encoder (skipped when it is not cached)."""
    from app.core.config import get_settings
    from app.routing.models import encode

    cfg = get_settings().routing
    questions = {
        "When is the midterm exam and how much is it worth?": "logistics",
        "Can I hand in the assignment a day late?": "logistics",
        "Which textbook do I need to buy for this course?": "logistics",
        "What time are the teaching assistant's office hours?": "logistics",
        "How does a transistor amplify a signal?": "concept",
        "Why does the Fourier transform of a pulse spread out in frequency?": "concept",
        "Explain how insulin lowers blood sugar.": "concept",
        "What is the time complexity of merge sort?": "concept",
    }
    try:
        vectors = encode(list(questions), cfg)
    except Exception:  # noqa: BLE001 - no cached encoder on this machine
        pytest.skip("local sentence encoder is not available")
    assert [question_type.classify(v, cfg) for v in vectors] == list(questions.values())


# ------------------------------------------------------------------ the route step


class KindRouter:
    """Stands in for the semantic router: the embedding of a text is its length, the kind is given."""

    def __init__(self, kind="logistics", fail=False):
        self.kind, self.fail, self.embedded = kind, fail, []

    def embed(self, text):
        self.embedded.append(text)
        return np.array([float(len(text))])

    def classify(self, vector, method):
        return SemanticAnalysis(method=method, cloud_probability=0.2, reliable=True)

    def question_kind(self, vector):
        if self.fail:
            raise RuntimeError("head broken")
        return self.kind


def make_ctx(question="when is the midterm?", history=()):
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question=question),
                         history=list(history))
    ctx.pii = PIIResult(sanitized_text=question)
    return ctx


async def run_route_step(use_config, router, ctx):
    services = build_services(use_config({"routing": {"impl": "semantic"}}))
    services.router = router
    return await AnalyzeRouteStep(services).run(ctx)


async def test_route_step_sets_the_question_type(use_config):
    router = KindRouter("logistics")
    ctx = await run_route_step(use_config, router, make_ctx())
    assert ctx.question_type == "logistics"
    assert ctx.semantic_analysis.question_kind == "logistics"
    assert ctx.semantic_analysis.cloud_probability == 0.2  # the route heads are untouched
    assert router.embedded == ["when is the midterm?"]  # one encoding, shared with the route heads


async def test_question_type_uses_the_current_question_not_the_history(use_config):
    router = KindRouter("logistics")
    history = [Turn(role="student", text="what is a capacitor?")]
    ctx = await run_route_step(use_config, router, make_ctx(history=history))
    assert ctx.question_type == "logistics"
    assert router.embedded[0].startswith("Previous student questions:")  # for the route heads
    assert router.embedded[1] == "when is the midterm?"  # for the question type


async def test_broken_or_missing_head_never_stops_the_request(use_config):
    ctx = await run_route_step(use_config, KindRouter(fail=True), make_ctx())
    assert ctx.question_type == "concept" and ctx.semantic_analysis.reliable
    router = KindRouter()
    router.question_kind = None  # a router without the head
    assert (await run_route_step(use_config, router, make_ctx())).question_type == "concept"


def test_question_type_is_concept_before_the_route_step_and_without_analysis():
    assert make_ctx().question_type == "concept"


def test_the_semantic_router_asks_the_head_and_leaves_the_route_alone(tmp_path, monkeypatch):
    write_head(tmp_path)
    router = SemanticRouter()
    router.cfg = config(tmp_path)
    assert router.question_kind(LOGISTICS) == "logistics"
    assert router.question_kind(CONCEPT) == "concept"
    assert "question_kind" not in RouteScore.model_fields  # the decision has no say in it


# --------------------------------------------------------------- retrieval gets the kind


class KindRecordingRetriever:
    def __init__(self):
        self.kinds = []

    def retrieve(self, query, topic, k=4, kc_ids=None, level=None):
        self.kinds.append(course_scope._question_kind.get())
        return []


async def test_retrieve_step_passes_the_kind_to_the_retriever_thread(use_config):
    services = build_services(use_config({"rag": {"impl": "fixture"}, "routing": {"impl": "stub"}}))
    services.retriever = KindRecordingRetriever()
    for kind, expected in (("logistics", "logistics"), ("concept", "concept")):
        ctx = make_ctx()
        ctx.semantic_analysis = SemanticAnalysis(method="lr", question_kind=kind)
        await RetrieveStep(services).run(ctx)
        assert services.retriever.kinds[-1] == expected
    assert course_scope._question_kind.get() == "concept"  # restored after the step


def test_course_module_retriever_asks_for_course_level_files_first_only_for_logistics():
    fake = FakeCourseRetriever()
    services = type("S", (), {"course_retriever": fake, "content": type("C", (), {"course_id": 99})()})()
    retriever = course_scope.CourseModuleRetriever(services, 5, {"mod1": 11})
    retriever.retrieve("when is the midterm?", "mod1")
    with course_scope.question_kind("logistics"):
        retriever.retrieve("when is the midterm?", "mod1")
        retriever.retrieve("when is the midterm?", course_scope.GENERAL_TOPIC)
    assert fake.kinds == ["concept", "logistics", "logistics"]
    assert fake.calls[1][1] == 11 and fake.calls[2][1] is None
