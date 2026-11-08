"""Database engine and schema (task Z3): PostgreSQL only, schema managed by Alembic.

`DATABASE_URL` is a PostgreSQL URL (`postgresql+psycopg://user@host:5432/db`). Keep the password out of
the URL: libpq reads it from `PGPASSWORD` (Docker Compose sets it from `POSTGRES_PASSWORD` in `.env`).
`init_db` upgrades the schema to the newest Alembic revision at startup; an advisory lock makes parallel
API workers wait for each other instead of migrating twice.
"""
from functools import lru_cache
from pathlib import Path

from alembic import command
from alembic.config import Config
from alembic.script import ScriptDirectory
from sqlalchemy import Engine, text
from sqlalchemy.pool import NullPool
from sqlmodel import create_engine

from app.storage import models  # noqa: F401  (registers the tables on SQLModel.metadata)

BACKEND = Path(__file__).resolve().parents[2]
_MIGRATION_LOCK = 590_201  # pg_advisory_lock key for schema upgrades


class DatabaseConfigError(RuntimeError):
    """DATABASE_URL is missing or not a PostgreSQL URL."""


def normalize_url(url: str | None) -> str:
    if not url or not url.strip():
        raise DatabaseConfigError(
            "Set DATABASE_URL to a PostgreSQL URL (see .env.example and docs/DATABASE.md).")
    url = url.strip()
    for prefix in ("postgresql://", "postgres://"):
        if url.startswith(prefix):
            url = "postgresql+psycopg://" + url.removeprefix(prefix)
    if not url.startswith("postgresql+psycopg://"):
        raise DatabaseConfigError("Only PostgreSQL is supported: DATABASE_URL must start with postgresql://.")
    return url


def make_engine(url: str | None, *, pooled: bool = True, password: str | None = None) -> Engine:
    """Engine for DATABASE_URL. `pooled=False` opens a connection per use (tests, short-lived tools).

    `password` (the PGPASSWORD setting) is given to the driver directly, so it never appears in a URL.
    Without it libpq still reads PGPASSWORD from the environment.
    """
    kwargs: dict = {"pool_pre_ping": True} if pooled else {"poolclass": NullPool}
    if password:
        kwargs["connect_args"] = {"password": password}
    return create_engine(normalize_url(url), **kwargs)


def alembic_config(engine: Engine | None = None) -> Config:
    cfg = Config(str(BACKEND / "alembic.ini"))
    cfg.set_main_option("script_location", str(BACKEND / "alembic"))
    if engine is not None:
        cfg.attributes["engine"] = engine
    return cfg


@lru_cache(maxsize=1)
def head_revision() -> str:
    return ScriptDirectory.from_config(alembic_config()).get_current_head()


def _current_revision(conn) -> str | None:
    if conn.execute(text("SELECT to_regclass('alembic_version')")).scalar() is None:
        return None
    return conn.execute(text("SELECT version_num FROM alembic_version")).scalar()


def init_db(engine: Engine) -> None:
    """Upgrade the schema to the newest revision (a no-op when it is current)."""
    with engine.connect() as conn:
        if _current_revision(conn) == head_revision():
            conn.rollback()
            return
        conn.execute(text("SELECT pg_advisory_lock(:k)"), {"k": _MIGRATION_LOCK})
        try:
            cfg = alembic_config()
            cfg.attributes["connection"] = conn
            command.upgrade(cfg, "head")
            conn.commit()
        finally:
            conn.execute(text("SELECT pg_advisory_unlock(:k)"), {"k": _MIGRATION_LOCK})
            conn.commit()
