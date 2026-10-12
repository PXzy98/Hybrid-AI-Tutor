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
