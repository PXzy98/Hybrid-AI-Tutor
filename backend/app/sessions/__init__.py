from sqlalchemy import Engine

from app.core.registry import import_submodules, session_stores
from app.sessions.interface import SessionStore


def load_session_store(name: str, engine: Engine) -> SessionStore:
    """Instantiate the session store registered under `name` (config: sessions.store)."""
    import_submodules("app.sessions")
    return session_stores.get(name)(engine)
