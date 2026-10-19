"""Shared data models: the contract between pipeline steps, the API and teammates' components.

Design: docs/System_Design_v3.md §9. Teammates code against these models, so any change here
must be listed under "Interface changes" in docs/IMPLEMENTATION_LOG.md. Never rename or remove a field
without agreement.
"""

from datetime import UTC, datetime
from time import perf_counter
from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, PrivateAttr

Level = Literal["basic", "intermediate", "advanced"]
Sequencing = Literal["example_first", "concept_first"]
Detail = Literal["concise", "detailed"]
Target = Literal["local", "cloud"]


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- request / privacy
class AskRequest(BaseModel):
    session_id: str = ""  # empty -> the API starts a new session
    course_id: str = "default"
    student_id: str = Field(min_length=1)  # internal pseudonymous ID, never the real student number
    topic: str = Field(min_length=1)  # must be listed in config.yaml (checked by the API)
    question: str = Field(min_length=1, max_length=4000)
    language: str = "en"
    routing_method: Literal["lr", "svm"] | None = None


class PIIEntity(BaseModel):
    type: str  # e.g. PERSON, STUDENT_ID, HEALTH_DETAIL
    text: str
    start: int
    end: int
    score: float
    placeholder: str  # e.g. <PERSON_1>


class PIIResult(BaseModel):
    entities: list[PIIEntity] = []
    is_sensitive: bool = False
    cloud_safe: bool = True  # False -> the request must stay local
    sanitized_text: str


# ------------------------------------------------------------------- RAG / routing
class Chunk(BaseModel):
    text: str
    source: str
    topic: str
    score: float
    kc_ids: list[str] = []
    level: Level | None = None
    # Optional; old Retriever implementations continue to work unchanged.
    # approved=False rejects a source; verified_at/valid_until support freshness checks.
    metadata: dict[str, Any] = {}


class RouteInput(BaseModel):
    sanitized_question: str
    topic: str
    pii: PIIResult
    passage_count: int = Field(ge=0)
    level: Level | None = None
    kc_ids: list[str] = []
    passages: list[Chunk] = []
    method: Literal["lr", "svm"] | None = None
    retrieval_status: str = "unknown"
    conversation_context: str = ""

    @property
    def contextual_question(self) -> str:
        if not self.conversation_context:
            return self.sanitized_question
        return (
            f"Previous student questions: {self.conversation_context}\n"
            f"Current question: {self.sanitized_question}"
        )


class SemanticAnalysis(BaseModel):
    method: str
    cloud_probability: float = Field(1, ge=0, le=1)
    evidence_probability: float = Field(1, ge=0, le=1)
    freshness_probability: float = Field(0, ge=0, le=1)
    nearest_similarity: float = Field(0, ge=-1, le=1)
    requires_evidence: bool = True
    requires_fresh_evidence: bool = False
    reliable: bool = False
    label_origin: str = "unavailable"
    reason: str = "semantic models unavailable"


class EvidenceAssessment(BaseModel):
    status: Literal["not_required", "unavailable", "empty", "insufficient", "uncertain", "sufficient"]
    retrieved_count: int = 0
    accepted_indices: list[int] = []  # best QA-supported passage per question unit: the routing decision
    # passages the relevance model judged relevant to the question: what the answer may use
    relevant_indices: list[int] = []
    checked: bool = False  # the evidence models actually ran (False: skipped, missing or failed)
    coverage: float = Field(0, ge=0, le=1)
    # A QA-support estimate, not a factual-correctness probability.
    support_scores: list[float] = []
    reason: str = ""


class RoutingProgress(BaseModel):
    stage: str
    status: Literal["running", "completed", "skipped", "failed"]
    elapsed_ms: float
    duration_ms: float | None = None
    detail: str = ""


class RouteScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)  # >= routing.threshold -> cloud
    reasons: list[str] = []
    target: Target | None = None
    method: str | None = None
    analysis: SemanticAnalysis | None = None
    evidence: EvidenceAssessment | None = None
    # Only accepted course evidence is passed to either generator.
    accepted_indices: list[int] = []


# ------------------------------------------------------------------------------ LLM
class LLMResult(BaseModel):
    text: str
    model: str
    backend: Target
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    latency_ms: float
    fell_back: bool = False


class CheckResult(BaseModel):
    name: str
    status: Literal["pass", "warn", "fail"]
    detail: str = ""


class Turn(BaseModel):
    role: Literal["student", "tutor"]
    text: str  # sanitized text only
    created_at: datetime = Field(default_factory=_now)


# -------------------------------------------------------------------------- learner
class Preferences(BaseModel):
    sequencing: Sequencing = "example_first"
    detail: Detail = "concise"
    source: Literal["default", "onboarding", "feedback"] = "default"


class KcState(BaseModel):
    kc_id: str
    p_mastery: float = Field(ge=0.0, le=1.0)
    level: Level
    n_obs: int = 0
    last_seen: datetime | None = None


class MisconceptionRef(BaseModel):
    id: str
    kc_id: str
    statement: str
    correction: str
    status: Literal["suspected", "confirmed", "resolved"]


class KcRecommendation(BaseModel):
    kc_id: str
    name: str
    reason: str


class CloudLabels(BaseModel):
    """The only learner information that may reach the cloud (design §8.1)."""

    model_config = ConfigDict(extra="forbid")

    level: Level
    sequencing: Sequencing
    detail: Detail


class LearnerContext(BaseModel):
    """Full learner view for the LOCAL model only. Never sent to the cloud."""

    kc_states: dict[str, KcState] = {}
    focus_level: Level = "intermediate"
    misconceptions: list[MisconceptionRef] = []
    preferences: Preferences = Preferences()
    next_kc: KcRecommendation | None = None
    personalized: bool = True

    def to_cloud_labels(self) -> CloudLabels:
        return CloudLabels(
            level=self.focus_level,
            sequencing=self.preferences.sequencing,
            detail=self.preferences.detail,
        )


class Evidence(BaseModel):
    kc_id: str
    kind: Literal["strong", "weak", "diagnostic"]
    correct: bool | None = None  # strong / diagnostic
    signal: Literal["confusion", "misconception"] | None = None  # weak
    misconception_id: str | None = None
    item_id: str | None = None
    source: Literal["check", "understand", "onboarding"]


class Understanding(BaseModel):
    kc_ids: list[str] = []
    question_type: Literal["definition", "how_why", "self_management", "check_my_answer", "other"] = "other"
    confusion: bool = False
    misconception_ids: list[str] = []


class CheckItemPublic(BaseModel):
    """A check question as sent to the student: deliberately has no answer key."""

    model_config = ConfigDict(extra="forbid")

    id: str
    kc_id: str
    stem: str
    options: dict[str, str]


# ---------------------------------------------------------------------------- cloud
class CloudRequest(BaseModel):
    """The ONLY type the cloud client accepts (privacy invariants 2 and 3)."""

    model_config = ConfigDict(extra="forbid")

    sanitized_question: str
    topic: str
    passages: list[str] = []  # course material, not student data
    labels: CloudLabels
    language: str = "en"


# --------------------------------------------------------------------------- answer
class Source(BaseModel):
    title: str
    source: str
    kc_ids: list[str] = []


class AskResponse(BaseModel):
    session_id: str
    answer: str
    sources: list[Source] = []
    model_used: str
    route_target: Target
    route_score: float | None = None
    check_item: CheckItemPublic | None = None
    kc_level: Level | None = None
    next_kc: KcRecommendation | None = None
    checks: list[CheckResult] = []
    warnings: list[str] = []
    timings_ms: dict[str, float] = {}
    routing_method: str | None = None
    routing_details: RouteScore | None = None
    routing_progress: list[RoutingProgress] = []


class RequestContext(BaseModel):
    """The one object every pipeline step reads and writes."""

    request_id: str
    request: AskRequest
    learner: LearnerContext | None = None
    understanding: Understanding | None = None
    pii: PIIResult | None = None
    history: list[Turn] = []
    passages: list[Chunk] = []
    route: RouteScore | None = None
    target: Target | None = None
    cloud_request: CloudRequest | None = None
    generalized_question: str | None = None  # privacy.health_detail_policy=generalize: the checked rewrite
    llm: LLMResult | None = None
    answer: str | None = None
    check_item: CheckItemPublic | None = None
    checks: list[CheckResult] = []
    warnings: list[str] = []
    timings_ms: dict[str, float] = {}
    semantic_analysis: SemanticAnalysis | None = None
    retrieval_status: str = "unknown"
    routing_progress: list[RoutingProgress] = []
    show_routing_progress: bool = False
    _progress_sink: Any = PrivateAttr(default=None)
    _request_started: float = PrivateAttr(default_factory=perf_counter)

    def set_progress_sink(self, sink) -> None:
        self._progress_sink = sink

    async def report(self, stage: str, status: str, detail: str = "", duration_ms: float | None = None):
        if not self.show_routing_progress:
            return
        event = RoutingProgress(
            stage=stage,
            status=status,
            detail=detail,
            duration_ms=duration_ms,
            elapsed_ms=round((perf_counter() - self._request_started) * 1000, 2),
        )
        self.routing_progress.append(event)
        if self._progress_sink is not None:
            await self._progress_sink(event)

    # placeholder -> original value. Private: never serialized, logged or shown in repr.
    _pii_mapping: dict[str, str] = PrivateAttr(default_factory=dict)

    @property
    def pii_mapping(self) -> dict[str, str]:
        return self._pii_mapping

    def set_pii_mapping(self, mapping: dict[str, str]) -> None:
        self._pii_mapping = dict(mapping)

    def clear_pii_mapping(self) -> None:
        self._pii_mapping = {}
