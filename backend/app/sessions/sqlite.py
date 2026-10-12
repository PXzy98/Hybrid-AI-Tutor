from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.core.registry import session_stores
from app.core.schemas import Turn
from app.storage.models import SessionTurn


@session_stores.register("sqlite")
class SqliteSessionStore:
    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def history(self, session_id: str, last: int = 6) -> list[Turn]:
        if last <= 0:
            return []
        with Session(self.engine) as s:
            rows = s.exec(
                select(SessionTurn)
                .where(SessionTurn.session_id == session_id)
                .order_by(col(SessionTurn.id).desc())
                .limit(last)
            ).all()
        return [Turn(role=r.role, text=r.text, created_at=r.created_at) for r in reversed(rows)]

    def append(self, session_id: str, turn: Turn) -> None:
        with Session(self.engine) as s:
            s.add(SessionTurn(session_id=session_id, role=turn.role, text=turn.text,
                              created_at=turn.created_at))
            s.commit()
