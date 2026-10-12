from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ServicesDep
from app.core.schemas import Turn

router = APIRouter()


class SessionHistory(BaseModel):
    session_id: str
    turns: list[Turn]


@router.get("/sessions/{session_id}", response_model=SessionHistory)
def get_session(session_id: str, services: ServicesDep, last: int = 50):
    """Sanitized history of a session (oldest first)."""
    turns = services.sessions.history(session_id, last=min(last, 200))
    return SessionHistory(session_id=session_id, turns=turns)
