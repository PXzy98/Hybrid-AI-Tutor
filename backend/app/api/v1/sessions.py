from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from app.api.deps import ServicesDep
from app.auth.deps import Student
from app.core.schemas import Turn

router = APIRouter()


class SessionHistory(BaseModel):
    session_id: str
    turns: list[Turn]


@router.get("/sessions/{session_id}", response_model=SessionHistory)
def get_session(session_id: str, user: Student, services: ServicesDep, last: int = 50):
    """Sanitized history of one of the caller's own sessions (oldest first)."""
    owner = services.sessions.owner(session_id)
    if owner is not None and owner != user.student_id:
        raise HTTPException(404, "session not found")  # same answer as for a session that does not exist
    turns = services.sessions.history(session_id, last=min(last, 200)) if owner else []
    return SessionHistory(session_id=session_id, turns=turns)
