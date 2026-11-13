"""Database tables.

Text columns hold SANITIZED text only (privacy invariant 1). Usernames, display names and password
hashes exist only in `account` (privacy invariant 6); every other table uses the random `student_id`.
"""
from datetime import UTC, datetime

from sqlalchemy import JSON, Column, DateTime, ForeignKey, UniqueConstraint
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def _ts(**kwargs):
    """A timezone-aware timestamp column (PostgreSQL timestamptz)."""
    return Field(sa_type=DateTime(timezone=True), **kwargs)


class Account(SQLModel, table=True):
    __tablename__ = "account"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)  # lower-case
    # lower-case (task Z9); accounts from before have <username>@demo.invalid
    email: str | None = Field(default=None, unique=True, index=True)
    display_name: str
    role: str  # system role: admin | instructor | student (course-structure.md 3.1)
    password_hash: str
    student_id: str | None = Field(default=None, unique=True, index=True)  # random UUID; None for instructors
    active: bool = True
    must_change_password: bool = True
    failed_logins: int = 0
    locked_until: datetime | None = _ts(default=None)
    created_at: datetime = _ts(default_factory=utcnow)
    last_login_at: datetime | None = _ts(default=None)


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"

    id: int | None = Field(default=None, primary_key=True)
    # SHA-256 of the cookie token; the token itself is never stored
    token_hash: str = Field(unique=True, index=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = _ts(default_factory=utcnow)
    expires_at: datetime = _ts()


class SurveyResponse(SQLModel, table=True):
    """Anonymous numeric ratings only; never store student IDs or prompt text."""

    __tablename__ = "survey_response"

    id: int | None = Field(default=None, primary_key=True)
    topic: str = Field(index=True, max_length=64)
    helpfulness: int = Field(ge=1, le=5)
    material_relevance: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    source_confidence: int = Field(ge=1, le=5)


def _course_scope() -> Column:
    """course_id of a row that belongs to one course and goes with it (end of term, course deletion)."""
    return Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=True, index=True)


class RequestLog(SQLModel, table=True):
    __tablename__ = "request_log"

    id: int | None = Field(default=None, primary_key=True)
    request_id: str = Field(index=True)
    created_at: datetime = _ts(default_factory=utcnow)
    session_id: str = Field(index=True)
    student_id: str = Field(index=True)  # pseudonymous; "deleted" after the account is deleted
    course_id: int | None = Field(default=None, sa_column=_course_scope())
    topic: str
    sanitized_question: str
    target: str | None = None
    route_score: float | None = None
    model: str | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    timings: dict = Field(default_factory=dict, sa_column=Column(JSON))
    checks: list = Field(default_factory=list, sa_column=Column(JSON))
    warnings: list = Field(default_factory=list, sa_column=Column(JSON))


class SessionTurn(SQLModel, table=True):
    __tablename__ = "session_turn"

    id: int | None = Field(default=None, primary_key=True)
    session_id: str = Field(index=True)
    student_id: str = Field(index=True)  # owner of the session
    course_id: int | None = Field(default=None, sa_column=_course_scope())  # conversations are per course
    role: str
    text: str  # sanitized
    created_at: datetime = _ts(default_factory=utcnow)


# ---------------------------------------------------------------------- learner model (design §5, §9)
# Keyed by student_id and course_id (course-structure.md 4.1); preferences and consent are global. No
# free-text columns: evidence holds IDs, flags and numbers, never question text. course_id is NULL only in
# offline simulations that run on the YAML seed without a course row.

# tables whose rows belong to one course and had no course_id before (assigned to the demo course)
ROWS_OF_A_COURSE = ("learner_kc_state", "learner_topic_level", "evidence_log", "learner_misconception",
                    "request_log", "session_turn")


class LearnerKcState(SQLModel, table=True):
    __tablename__ = "learner_kc_state"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    course_id: int | None = Field(default=None, sa_column=_course_scope())
    kc_id: str = Field(index=True)
    p_mastery: float
    level: str  # basic | intermediate | advanced (with hysteresis)
    n_obs: int = 0  # graded answers (check + diagnostic)
    last_seen: datetime | None = _ts(default=None)


class LearnerTopicLevel(SQLModel, table=True):
    """Focus level per topic, kept so that hysteresis also applies to the topic-level estimate."""

    __tablename__ = "learner_topic_level"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    course_id: int | None = Field(default=None, sa_column=_course_scope())
    topic: str
    level: str
    updated_at: datetime = _ts(default_factory=utcnow)


class LearnerPreference(SQLModel, table=True):
    __tablename__ = "learner_preference"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(unique=True, index=True)
    sequencing: str = "example_first"
    detail: str = "concise"
    source: str = "default"
    implicit: dict = Field(default_factory=dict, sa_column=Column(JSON))  # streak counters per dimension
    updated_at: datetime = _ts(default_factory=utcnow)


class EvidenceLog(SQLModel, table=True):
    __tablename__ = "evidence_log"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    course_id: int | None = Field(default=None, sa_column=_course_scope())
    kc_id: str = Field(index=True)
    kind: str  # strong | weak | diagnostic
    source: str  # check | understand | onboarding
    item_id: str | None = None
    correct: bool | None = None
    signal: str | None = None  # confusion | misconception
    misconception_id: str | None = None
    weight: float = 1.0  # likelihood ratio of a weak signal; 1.0 for graded answers
    created_at: datetime = _ts(default_factory=utcnow)


class Consent(SQLModel, table=True):
    __tablename__ = "consent"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(unique=True, index=True)
    given: bool
    created_at: datetime = _ts(default_factory=utcnow)
    updated_at: datetime = _ts(default_factory=utcnow)


class LearnerMisconception(SQLModel, table=True):
    """Tracked catalog misconceptions (design §5.1): IDs and counts only, never text."""

    __tablename__ = "learner_misconception"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    course_id: int | None = Field(default=None, sa_column=_course_scope())
    misconception_id: str = Field(index=True)
    kc_id: str
    status: str  # suspected | confirmed | resolved
    evidence_count: int = 0  # signals since the misconception was last opened
    updated_at: datetime = _ts(default_factory=utcnow)


class ConfigHistory(SQLModel, table=True):
    """Runtime config changes from the dashboard (design §9). The newest row is applied at startup."""

    __tablename__ = "config_history"

    id: int | None = Field(default=None, primary_key=True)
    changed_at: datetime = _ts(default_factory=utcnow)
    account_id: int | None = None  # the instructor (no username here: identity stays in `account`)
    scope: str = "system"  # system | course (task Z5); v3 rows are "system" in the v1 dashboard format
    course_id: int | None = None
    version: int | None = None  # the settings version this change produced
    values: dict = Field(default_factory=dict, sa_column=Column(JSON))  # the full editable subset after
    previous: dict = Field(default_factory=dict, sa_column=Column(JSON))  # ... and before the change


# ------------------------------------------------------------- course catalog (task Z4, design §2, §5, §10)
# Content status: `draft` is invisible to students (unreviewed or AI-proposed), `active` is published,
# `retired` stays for history and learner state but is not used for new questions.
class Course(SQLModel, table=True):
    __tablename__ = "course"

    id: int | None = Field(default=None, primary_key=True)
    code: str = Field(unique=True, index=True)  # e.g. "MED 0000"
    title: str
    term_label: str = ""  # free text for display, e.g. "Winter 2027"
    course_type: str = "general"  # selects the privacy profile
    visibility_mode: str = "A"  # A | B (design §4.5)
    status: str = "active"  # active | archived
    created_at: datetime = _ts(default_factory=utcnow)
    # incremented by every content edit; processes reload the content when it changes (task Z9)
    content_version: int = Field(default=0, sa_column_kwargs={"server_default": "0"})


class Module(SQLModel, table=True):
    __tablename__ = "module"
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    code: str  # the v3 topic, e.g. "high_blood_pressure"
    title: str
    position: int = 0
    guideline: str = ""


class Kc(SQLModel, table=True):
    __tablename__ = "kc"
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    module_id: int | None = Field(default=None, sa_column=Column(ForeignKey("module.id", ondelete="SET NULL"),
                                                                 index=True))
    code: str  # e.g. "HBP.1"; unique within the course
    name: str
    definition: str = ""
    difficulty: str  # basic | intermediate | advanced
    status: str = "draft"


class KcPrerequisite(SQLModel, table=True):
    """Prerequisite edges; both KCs belong to the same course (checked by the importer)."""

    __tablename__ = "kc_prerequisite"

    kc_id: int = Field(sa_column=Column(ForeignKey("kc.id", ondelete="CASCADE"), primary_key=True))
    prerequisite_id: int = Field(sa_column=Column(ForeignKey("kc.id", ondelete="CASCADE"), primary_key=True))


class CatalogMisconception(SQLModel, table=True):
    __tablename__ = "misconception"
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    kc_id: int = Field(sa_column=Column(ForeignKey("kc.id", ondelete="CASCADE"), nullable=False, index=True))
    code: str  # e.g. "HBP.MC1"
    statement: str
    correction: str
    status: str = "draft"


class CheckItem(SQLModel, table=True):
    __tablename__ = "check_item"
    __table_args__ = (UniqueConstraint("course_id", "code"),)

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    kc_id: int = Field(sa_column=Column(ForeignKey("kc.id", ondelete="CASCADE"), nullable=False, index=True))
    code: str  # e.g. "HBP.1-q4"
    level: str
    stem: str
    # {"A": {"text": ..., "misconception": "HBP.MC4" | null}, ...}; misconceptions by code
    options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    answer: str  # A | B | C | D
    explanation: str = ""
    status: str = "draft"


class Material(SQLModel, table=True):
    """An uploaded course file (design §7); the text lives in the on-disk index, not here."""

    __tablename__ = "material"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    module_id: int | None = Field(default=None, sa_column=Column(ForeignKey("module.id", ondelete="CASCADE"),
                                                                 index=True))
    filename: str
    size_bytes: int = 0
    sha256: str = ""
    scan_status: str = "pending"  # pending | accepted | rejected
    uploaded_at: datetime = _ts(default_factory=utcnow)


class IndexVersion(SQLModel, table=True):
    """The authoritative index version per course (IndexedCourseRetriever's `index_version`)."""

    __tablename__ = "index_version"

    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), primary_key=True))
    version: int = 0
    built_at: datetime | None = _ts(default=None)


class CourseMember(SQLModel, table=True):
    """Membership (design §3.3, §4.5): an account, or a pending e-mail from a CSV import."""

    __tablename__ = "course_member"
    __table_args__ = (UniqueConstraint("course_id", "account_id"), UniqueConstraint("course_id", "email"))

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    account_id: int | None = Field(
        default=None, sa_column=Column(ForeignKey("account.id", ondelete="CASCADE"), index=True))
    email: str | None = None  # only while pending (no account yet); cleared when the account is linked
    role: str  # instructor | student
    status: str = "pending"  # pending | active
    hidden_from_instructor: bool = False
    visible_since: datetime | None = _ts(default=None)
    visibility_ack_at: datetime | None = _ts(default=None)
    created_at: datetime = _ts(default_factory=utcnow)


class CourseInvite(SQLModel, table=True):
    __tablename__ = "course_invite"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    code_hash: str = Field(unique=True, index=True)  # SHA-256 of the invitation code: what join checks
    # the code itself, Fernet-encrypted with SETTINGS_ENCRYPTION_KEY, so instructors can see it again (None
    # without a key: then it is shown only once)
    code_encrypted: str | None = None
    role: str = "student"
    expires_at: datetime | None = _ts(default=None)
    max_uses: int | None = None
    uses: int = 0
    created_at: datetime = _ts(default_factory=utcnow)


# ------------------------------------------------------------------- settings layers (task Z5, design §6)
# Every field is nullable: null means "use the next layer" (course -> system -> config.yaml).
class _SettingsMeta(SQLModel):
    version: int = 1
    updated_at: datetime = _ts(default_factory=utcnow)
    updated_by: int | None = None  # account id
    apply_state: str = "applied"  # applied | applying | failed (design §6.5)
    apply_target_version: int | None = None
    apply_started_at: datetime | None = _ts(default=None)
    apply_error: str | None = None


class SystemSettings(_SettingsMeta, table=True):
    __tablename__ = "system_settings"

    id: int = Field(default=1, primary_key=True)  # exactly one row
    checkers: list | None = Field(default=None, sa_column=Column(JSON))  # optional ones; required are added
    weak_evidence: bool | None = None
    level_basic_below: float | None = None
    level_advanced_above: float | None = None
    level_hysteresis: float | None = None
    knowledge_model: str | None = None  # component
    default_routing_method: str | None = None  # component
    local_llm_url: str | None = None  # component; v1 dashboard (a model endpoint takes precedence, Z6)
    local_llm_model: str | None = None  # component
    default_local_endpoint_id: int | None = Field(
        default=None, sa_column=Column(ForeignKey("model_endpoint.id", ondelete="SET NULL")))
    default_cloud_endpoint_id: int | None = Field(
        default=None, sa_column=Column(ForeignKey("model_endpoint.id", ondelete="SET NULL")))
    enabled_course_types: list | None = Field(default=None, sa_column=Column(JSON))
    previous_values: dict | None = Field(default=None, sa_column=Column(JSON))  # for a rollback (§6.5)


class CourseSettings(_SettingsMeta, table=True):
    __tablename__ = "course_settings"

    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), primary_key=True))
    course_type: str | None = None
    visibility_mode: str | None = None
    local_only: bool | None = None
    routing_preference: str | None = None
    routing_threshold: float | None = None
    show_routing_progress: bool | None = None
    usage_questions_per_minute: int | None = None
    usage_questions_per_day: int | None = None
    usage_cloud_calls_per_day: int | None = None
    local_endpoint_id: int | None = Field(
        default=None, sa_column=Column(ForeignKey("model_endpoint.id", ondelete="SET NULL")))
    cloud_endpoint_id: int | None = Field(
        default=None, sa_column=Column(ForeignKey("model_endpoint.id", ondelete="SET NULL")))


class UsageCounter(SQLModel, table=True):
    """Usage per student + course + period (guide 4.4, task Z10): questions per minute and per day, cloud
    calls per day. Counts only; no question text."""

    __tablename__ = "usage_counter"
    __table_args__ = (UniqueConstraint("student_id", "course_id", "kind", "period", "period_start"),)

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    kind: str  # question | cloud_call
    period: str  # minute | day
    period_start: datetime = _ts()
    count: int = 0
    tokens: int = 0


class Job(SQLModel, table=True):
    """A background job, run by the worker (api-v2.md 3.4 `GET .../jobs/{job_id}`; task Z12)."""

    __tablename__ = "job"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int | None = Field(default=None, sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"),
                                                                 index=True))
    kind: str = Field(index=True)  # e.g. ai_evaluation.generate
    ref_id: int | None = None  # the row the job works on (e.g. ai_evaluation.id)
    status: str = Field(default="queued", index=True)  # queued | running | done | failed
    progress: int = 0  # percent
    error: str | None = None  # a short English message, never course or student text
    created_by: int | None = None  # account id
    created_at: datetime = _ts(default_factory=utcnow)
    started_at: datetime | None = _ts(default=None)
    finished_at: datetime | None = _ts(default=None)


class AiEvaluation(SQLModel, table=True):
    """Instructor AI tier 4: can the local model handle this course? (guide 4.9; task Z12). Generated
    questions, answers and scores are course content; no student data is used."""

    __tablename__ = "ai_evaluation"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int = Field(sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"), nullable=False,
                                            index=True))
    created_by: int | None = None
    # generating -> review (the instructor checks the questions) -> running -> done | failed
    status: str = "generating"
    options: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    questions: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    results: list = Field(default_factory=list, sa_column=Column(JSON, nullable=False))
    report: dict = Field(default_factory=dict, sa_column=Column(JSON, nullable=False))
    error: str | None = None
    created_at: datetime = _ts(default_factory=utcnow)
    updated_at: datetime = _ts(default_factory=utcnow)


class ProcessStatus(SQLModel, table=True):
    """Heartbeat of every api/worker process (design §6.5): which component version it runs."""

    __tablename__ = "process_status"

    process_id: str = Field(primary_key=True)
    kind: str = "api"
    last_seen: datetime = _ts(default_factory=utcnow)
    component_version: int = 0
    error: str | None = None


class AuditLog(SQLModel, table=True):
    """Who did what to which object; IDs and field names only, never student text."""

    __tablename__ = "audit_log"

    id: int | None = Field(default=None, primary_key=True)
    created_at: datetime = _ts(default_factory=utcnow)
    account_id: int | None = Field(default=None, index=True)
    action: str  # e.g. settings.system.update, settings.course.restore
    target: str  # e.g. "system", "course:7"
    details: dict = Field(default_factory=dict, sa_column=Column(JSON))



# ------------------------------------------------------------------- model connections (task Z6, guide 4.11)
class ModelEndpoint(SQLModel, table=True):
    """An OpenAI-compatible or Ollama model connection, of the system or of one course.

    `trust` decides what it may receive: `trusted_local` gets original text and the learner profile (the
    deployment's own model, or a service the instructor confirmed he controls); `external` gets only what
    passed the cloud gate. The API key is stored encrypted (SETTINGS_ENCRYPTION_KEY); only its last four
    characters are shown.
    """

    __tablename__ = "model_endpoint"

    id: int | None = Field(default=None, primary_key=True)
    course_id: int | None = Field(default=None, sa_column=Column(ForeignKey("course.id", ondelete="CASCADE"),
                                                                 index=True))  # None: a system connection
    name: str
    kind: str  # ollama | openai_compat
    base_url: str
    model: str
    trust: str  # trusted_local | external
    api_key_encrypted: str | None = None
    api_key_last4: str | None = None
    created_at: datetime = _ts(default_factory=utcnow)
    updated_at: datetime = _ts(default_factory=utcnow)
    updated_by: int | None = None
    last_test_ok_at: datetime | None = _ts(default=None)



class LoginIdentity(SQLModel, table=True):
    """How an account signs in (course-structure.md 3.1): `password` now; Microsoft Entra ID or Brightspace
    LTI later, without changing other tables."""

    __tablename__ = "login_identity"
    __table_args__ = (UniqueConstraint("provider", "subject"),)

    id: int | None = Field(default=None, primary_key=True)
    account_id: int = Field(sa_column=Column(ForeignKey("account.id", ondelete="CASCADE"), nullable=False,
                                             index=True))
    provider: str = "password"
    # `account:<id>` for `password`; the provider's opaque subject ID later (never identity text)
    subject: str
    created_at: datetime = _ts(default_factory=utcnow)
