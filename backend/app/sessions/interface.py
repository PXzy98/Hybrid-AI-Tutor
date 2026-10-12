from typing import Protocol, runtime_checkable

from app.core.schemas import Turn


@runtime_checkable
class SessionStore(Protocol):
    """Sanitized conversation history per session (design §3). Constructed with the DB engine."""

    def history(self, session_id: str, last: int = 6) -> list[Turn]:
        """The last `last` turns, oldest first."""
        ...

    def append(self, session_id: str, turn: Turn) -> None:
        """Store one turn. `turn.text` must already be sanitized."""
        ...
