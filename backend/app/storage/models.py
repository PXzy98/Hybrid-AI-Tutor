"""Database tables.

Text columns hold SANITIZED text only (privacy invariant 1). Usernames, display names and password
hashes exist only in `account` (privacy invariant 6); every other table uses the random `student_id`.
"""
from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def utcnow() -> datetime:
    return datetime.now(UTC)


def as_utc(dt: datetime | None) -> datetime | None:
    """SQLite returns naive datetimes; everything is stored in UTC."""
    if dt is None or dt.tzinfo is not None:
        return dt
    return dt.replace(tzinfo=UTC)


class Account(SQLModel, table=True):
    __tablename__ = "account"

    id: int | None = Field(default=None, primary_key=True)
    username: str = Field(unique=True, index=True)  # lower-case
    display_name: str
    role: str  # student | instructor
    password_hash: str
    student_id: str | None = Field(default=None, unique=True, index=True)  # random UUID; None for instructors
    active: bool = True
    must_change_password: bool = True
    failed_logins: int = 0
    locked_until: datetime | None = None
    created_at: datetime = Field(default_factory=utcnow)
    last_login_at: datetime | None = None


class AuthSession(SQLModel, table=True):
    __tablename__ = "auth_session"

    id: int | None = Field(default=None, primary_key=True)
    # SHA-256 of the cookie token; the token itself is never stored
    token_hash: str = Field(unique=True, index=True)
    account_id: int = Field(foreign_key="account.id", index=True)
    created_at: datetime = Field(default_factory=utcnow)
    expires_at: datetime


class SurveyResponse(SQLModel, table=True):
    """Anonymous numeric ratings only; never store student IDs or prompt text."""

    __tablename__ = "survey_response"

    id: int | None = Field(default=None, primary_key=True)
    topic: str = Field(index=True, max_length=64)
    helpfulness: int = Field(ge=1, le=5)
    material_relevance: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    source_confidence: int = Field(ge=1, le=5)


class RequestLog(SQLModel, table=True):
    __tablename__ = "request_log"

    id: int | None = Field(default=None, primary_key=True)
    request_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=utcnow)
    session_id: str = Field(index=True)
    student_id: str = Field(index=True)  # pseudonymous; "deleted" after the account is deleted
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
    role: str
    text: str  # sanitized
    created_at: datetime = Field(default_factory=utcnow)


# ---------------------------------------------------------------------- learner model (design §5, §9)
# Keyed by student_id only. No free-text columns: evidence holds IDs, flags and numbers, never question text.
class LearnerKcState(SQLModel, table=True):
    __tablename__ = "learner_kc_state"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    kc_id: str = Field(index=True)
    p_mastery: float
    level: str  # basic | intermediate | advanced (with hysteresis)
    n_obs: int = 0  # graded answers (check + diagnostic)
    last_seen: datetime | None = None


class LearnerTopicLevel(SQLModel, table=True):
    """Focus level per topic, kept so that hysteresis also applies to the topic-level estimate."""

    __tablename__ = "learner_topic_level"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    topic: str
    level: str
    updated_at: datetime = Field(default_factory=utcnow)


class LearnerPreference(SQLModel, table=True):
    __tablename__ = "learner_preference"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(unique=True, index=True)
    sequencing: str = "example_first"
    detail: str = "concise"
    source: str = "default"
    implicit: dict = Field(default_factory=dict, sa_column=Column(JSON))  # streak counters per dimension
    updated_at: datetime = Field(default_factory=utcnow)


class EvidenceLog(SQLModel, table=True):
    __tablename__ = "evidence_log"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    kc_id: str = Field(index=True)
    kind: str  # strong | weak | diagnostic
    source: str  # check | understand | onboarding
    item_id: str | None = None
    correct: bool | None = None
    signal: str | None = None  # confusion | misconception
    misconception_id: str | None = None
    weight: float = 1.0  # likelihood ratio of a weak signal; 1.0 for graded answers
    created_at: datetime = Field(default_factory=utcnow)


class Consent(SQLModel, table=True):
    __tablename__ = "consent"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(unique=True, index=True)
    given: bool
    created_at: datetime = Field(default_factory=utcnow)
    updated_at: datetime = Field(default_factory=utcnow)


class LearnerMisconception(SQLModel, table=True):
    """Tracked catalog misconceptions (design §5.1): IDs and counts only, never text."""

    __tablename__ = "learner_misconception"

    id: int | None = Field(default=None, primary_key=True)
    student_id: str = Field(index=True)
    misconception_id: str = Field(index=True)
    kc_id: str
    status: str  # suspected | confirmed | resolved
    evidence_count: int = 0  # signals since the misconception was last opened
    updated_at: datetime = Field(default_factory=utcnow)


class ConfigHistory(SQLModel, table=True):
    """Runtime config changes from the dashboard (design §9). The newest row is applied at startup."""

    __tablename__ = "config_history"

    id: int | None = Field(default=None, primary_key=True)
    changed_at: datetime = Field(default_factory=utcnow)
    account_id: int | None = None  # the instructor (no username here: identity stays in `account`)
    values: dict = Field(default_factory=dict, sa_column=Column(JSON))  # the full editable subset after
    previous: dict = Field(default_factory=dict, sa_column=Column(JSON))  # ... and before the change
