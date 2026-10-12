"""Shared data models: the contract between pipeline steps, the API and teammates' components.

Design: docs/System_Design_v3.md §9. Teammates code against these models, so any change here
must be listed under "Interface changes" in docs/IMPLEMENTATION_LOG.md. Never rename or remove a field
without agreement.
"""
from datetime import UTC, datetime
from typing import Literal

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


class RouteInput(BaseModel):
    sanitized_question: str
    topic: str
    pii: PIIResult
    passage_count: int = Field(ge=0)
    level: Level | None = None
    kc_ids: list[str] = []


class RouteScore(BaseModel):
    score: float = Field(ge=0.0, le=1.0)  # >= routing.threshold -> cloud
    reasons: list[str] = []


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
    llm: LLMResult | None = None
    answer: str | None = None
    check_item: CheckItemPublic | None = None
    checks: list[CheckResult] = []
    warnings: list[str] = []
    timings_ms: dict[str, float] = {}

    # placeholder -> original value. Private: never serialized, logged or shown in repr.
    _pii_mapping: dict[str, str] = PrivateAttr(default_factory=dict)

    @property
    def pii_mapping(self) -> dict[str, str]:
        return self._pii_mapping

    def set_pii_mapping(self, mapping: dict[str, str]) -> None:
        self._pii_mapping = dict(mapping)

    def clear_pii_mapping(self) -> None:
        self._pii_mapping = {}
