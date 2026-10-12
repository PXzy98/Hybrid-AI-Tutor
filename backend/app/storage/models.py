"""Database tables. Text columns hold SANITIZED text only (privacy invariant 1)."""
from datetime import UTC, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field, SQLModel


def _now() -> datetime:
    return datetime.now(UTC)


class RequestLog(SQLModel, table=True):
    __tablename__ = "request_log"

    id: int | None = Field(default=None, primary_key=True)
    request_id: str = Field(index=True)
    created_at: datetime = Field(default_factory=_now)
    session_id: str = Field(index=True)
    student_id: str = Field(index=True)  # internal pseudonymous ID
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
    role: str
    text: str  # sanitized
    created_at: datetime = Field(default_factory=_now)
