"""V19: a course type selects its own routing heads and, optionally, its own router; the cloud gate still
decides last. Hand-made heads on a 4-dimensional embedding; fictional questions only."""
import json

import numpy as np
import pytest

from app.core.config import RoutingConfig
from app.core.schemas import AskRequest, EffectiveSettings, PIIResult, RequestContext, SemanticAnalysis
from app.core.services import build_services
from app.llm.cloud_guard import CloudClient
from app.llm.fake import FakeLLMClient
from app.pipeline.settings_view import router_of
from app.pipeline.steps.analyze_route import AnalyzeRouteStep, route_input
from app.pipeline.steps.generate import PRIVACY_BLOCK_WARNING, GenerateStep
from app.pipeline.steps.route import RouteStep
from app.routing import question_type
from app.routing.models import HEADS, load_weights, weights_path
from app.routing.semantic import SemanticRouter
from app.routing.stub import StubRouter
from app.routing.train import output_dir

ENCODER = "test-encoder"
DIMENSION = 4
QUESTION = np.array([1.0, 0.0, 0.0, 0.0], dtype=np.float32)


def write_heads(folder, cloud_bias: float, *, method="lr", course_type=None):
    """Heads whose cloud probability is sigmoid(cloud_bias) for every question (coef 0)."""
    folder.mkdir(parents=True, exist_ok=True)
    metadata = {"schema_version": 1, "method": method, "embedding_model": ENCODER, "dimension": DIMENSION,
                "label_origin": "test"}
    if course_type:
        metadata["course_type"] = course_type
    arrays = {"prototypes": np.eye(DIMENSION, dtype=np.float32)}
    for head in HEADS:
        arrays[f"{head}_coef"] = np.zeros((1, DIMENSION))
        arrays[f"{head}_intercept"] = np.array([cloud_bias if head == "cloud_required" else -4.0])
        arrays[f"{head}_a"] = np.array([-1.0])  # p = 1 / (1 + exp(a * d + b)) = sigmoid(d)
        arrays[f"{head}_b"] = np.array([0.0])
    np.savez_compressed(folder / f"semantic_{method}.npz", metadata=np.array(json.dumps(metadata)), **arrays)


def config(tmp_path) -> RoutingConfig:
    return RoutingConfig(model_dir=str(tmp_path), embedding_model=ENCODER)


def router_for(tmp_path) -> SemanticRouter:
    router = SemanticRouter()
    router.cfg = config(tmp_path)
    return router


def test_a_type_without_its_own_heads_routes_exactly_as_the_shared_heads(tmp_path):
    write_heads(tmp_path, -2.0)
    router = router_for(tmp_path)
    shared = router.classify(QUESTION, "lr")
    for course_type in ("ece", "computer_science", "general", None):
        assert weights_path(router.cfg, "lr", course_type) == tmp_path / "semantic_lr.npz"
        assert router.classify(QUESTION, "lr", course_type) == shared


def test_a_type_with_its_own_heads_uses_them(tmp_path):
    write_heads(tmp_path, -2.0)
    write_heads(tmp_path / "ece", 2.0, course_type="ece")
    router = router_for(tmp_path)
    assert router.classify(QUESTION, "lr", "ece").cloud_probability == pytest.approx(1 / (1 + np.exp(-2.0)))
    general = router.classify(QUESTION, "lr", "general")
    assert general.cloud_probability == pytest.approx(1 / (1 + np.exp(2.0)))
    # only the methods it has: svm of ece falls back to the shared svm heads
    write_heads(tmp_path, -2.0, method="svm")
    assert weights_path(router.cfg, "svm", "ece") == tmp_path / "semantic_svm.npz"


@pytest.mark.parametrize("course_type", ["../ece", "ECE", "ece/..", "no_such_type", "", "ece\\x"])
def test_an_unknown_or_path_like_type_gets_the_shared_heads(tmp_path, course_type):
    write_heads(tmp_path, -2.0)
    write_heads(tmp_path / "ece", 2.0, course_type="ece")
    (tmp_path / "no_such_type").mkdir()
    write_heads(tmp_path / "no_such_type", 2.0)
    assert weights_path(config(tmp_path), "lr", course_type) == tmp_path / "semantic_lr.npz"


def test_heads_of_another_type_are_refused_and_the_question_goes_to_the_cloud(tmp_path):
    write_heads(tmp_path, -2.0)
    write_heads(tmp_path / "ece", -2.0, course_type="computer_science")  # copied into the wrong folder
    cfg = config(tmp_path)
    with pytest.raises(ValueError):
        load_weights(cfg, "lr", "ece")
    router = router_for(tmp_path)
    router.embed = lambda question: QUESTION
    x = route_input(ctx_for("ece"))
    analysis = router.analyze(x)
    assert not analysis.reliable  # the failure fallback: never admitted to local
    assert router.decide(x, analysis, 0.6).target == "cloud"


def test_the_question_type_head_follows_the_course_type(tmp_path):
    def head(folder, logistics: bool):
        folder.mkdir(parents=True, exist_ok=True)
        metadata = {"schema_version": 1, "embedding_model": ENCODER, "dimension": DIMENSION, "threshold": 0.5}
        coef = np.array([5.0 if logistics else -5.0, 0, 0, 0])
        np.savez_compressed(folder / question_type.WEIGHTS_NAME, metadata=np.array(json.dumps(metadata)),
                            coef=coef, intercept=np.array([0.0]))
    head(tmp_path, logistics=False)
    head(tmp_path / "ece", logistics=True)
    cfg = config(tmp_path)
    assert question_type.classify(QUESTION, cfg) == "concept"
    assert question_type.classify(QUESTION, cfg, "general") == "concept"
    assert question_type.classify(QUESTION, cfg, "ece") == "logistics"
    assert question_type.classify(QUESTION, cfg, "../ece") == "concept"


def test_training_writes_a_type_folder_only_for_a_known_type(tmp_path):
    cfg = config(tmp_path)
    assert output_dir(cfg, None) == tmp_path
    assert output_dir(cfg, "ece") == tmp_path / "ece"
    for bad in ("../ece", "nope", "ECE"):
        with pytest.raises(ValueError):
            output_dir(cfg, bad)


# ------------------------------------------------------------------------------------- the route steps
def ctx_for(course_type: str, *, local_only=False, question="How does a voltage divider work?",
            cloud_safe=True) -> RequestContext:
    settings = EffectiveSettings(course_id=1, course_type=course_type, local_only=local_only)
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question=question),
                         settings=settings)
    ctx.pii = PIIResult(sanitized_text=question, cloud_safe=cloud_safe, is_sensitive=not cloud_safe)
    return ctx


class RecordingRouter:
    """Stands in for the semantic router and records the course type it is asked with."""

    cfg = RoutingConfig()

    def __init__(self):
        self.types = []

    def embed(self, text):
        return QUESTION

    def classify(self, vector, method, course_type=None):
        self.types.append(course_type)
        return SemanticAnalysis(method=method, cloud_probability=0.1, reliable=True)

    def question_kind(self, vector, course_type=None):
        self.types.append(course_type)
        return "concept"


async def test_the_route_step_hands_the_course_type_to_the_router(use_config):
    services = build_services(use_config({"routing": {"impl": "semantic"}}))
    services.router = RecordingRouter()
    await AnalyzeRouteStep(services).run(ctx_for("ece"))
    assert services.router.types == ["ece", "ece"]  # route heads and question type head
    assert route_input(ctx_for("medical_science")).course_type == "medical_science"


async def test_by_course_type_picks_the_named_router_and_others_keep_the_default(use_config):
    services = build_services(use_config({"routing": {"impl": "semantic", "by_course_type": {"ece": "stub"},
                                                      "stub_score": 0.9}}))
    impl, router = router_of(ctx_for("ece"), services)
    assert impl == "stub" and isinstance(router, StubRouter)
    assert router_of(ctx_for("general"), services) == ("semantic", services.router)
    # a request without settings (unit tests of single steps) keeps the default
    bare = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question="q"))
    assert router_of(bare, services)[0] == "semantic"
    ctx = await RouteStep(services).run(ctx_for("ece"))
    assert ctx.target == "cloud" and ctx.route.score == 0.9  # the stub decided, not the semantic heads


async def test_a_type_router_cannot_send_a_local_only_course_to_the_cloud(use_config):
    services = build_services(use_config({"routing": {"impl": "semantic", "by_course_type": {"ece": "stub"},
                                                      "stub_score": 1.0}}))
    ctx = await RouteStep(services).run(ctx_for("ece", local_only=True))
    assert ctx.target == "local"


async def test_a_type_router_cannot_send_personal_health_detail_to_the_cloud(use_config):
    """The type's router proposes the cloud; the cloud gate in the generate step keeps the question local."""
    services = build_services(use_config({
        "routing": {"impl": "semantic", "by_course_type": {"medical_science": "stub"}, "stub_score": 1.0,
                    "force_local_if_not_cloud_safe": False},
        "privacy": {"health_detail_policy": "local_only"}}))
    services.local_llm = FakeLLMClient("local answer", model="fake-local")
    transport = FakeLLMClient("cloud answer", backend="cloud")
    services.cloud_llm = CloudClient(transport)
    ctx = ctx_for("medical_science", question="I have asthma, can I still run?", cloud_safe=False)
    ctx.pii = PIIResult(sanitized_text="I have <HEALTH_DETAIL_1>, can I still run?", cloud_safe=False,
                        is_sensitive=True)
    ctx = await RouteStep(services).run(ctx)
    assert ctx.target == "cloud"  # what the router proposed
    ctx = await GenerateStep(services).run(ctx)
    assert transport.calls == [] and ctx.answer == "local answer"
    assert PRIVACY_BLOCK_WARNING in ctx.warnings
