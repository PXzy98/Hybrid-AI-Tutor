"""Temporary PostgreSQL databases for tests and evaluation harnesses (task Z3).

`TEST_DATABASE_URL` points at a PostgreSQL server where the account may create databases, for example
`postgresql+psycopg://postgres@127.0.0.1:5432/postgres` (`docker compose up -d db`, see docs/DATABASE.md).
Each run creates its own database `tutor_test_<random>` and drops it afterwards, so nothing touches the
application database.
"""
import os
import uuid
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from sqlalchemy import create_engine, text
from sqlalchemy.engine import make_url
from sqlalchemy.pool import NullPool
from sqlmodel import SQLModel

from app.storage.db import init_db, make_engine, normalize_url

TEST_URL_ENV = "TEST_DATABASE_URL"
DOTENV = Path(__file__).resolve().parents[3] / ".env"


def load_test_env(environ=None) -> None:
    """Take TEST_DATABASE_URL and PGPASSWORD from the repository's .env when they are not in the environment
    (the .env that setup_local.py writes); libpq then reads PGPASSWORD for every test connection."""
    environ = os.environ if environ is None else environ
    if not DOTENV.is_file():
        return
    from dotenv import dotenv_values

    values = dotenv_values(DOTENV)
    for name in (TEST_URL_ENV, "PGPASSWORD"):
        if not environ.get(name) and values.get(name):
            environ[name] = values[name]


def admin_url() -> str:
    load_test_env()
    url = os.environ.get(TEST_URL_ENV, "").strip()
    if not url:
        raise RuntimeError(
            f"Set {TEST_URL_ENV} to a PostgreSQL server for tests, e.g. "
            "postgresql+psycopg://postgres@127.0.0.1:5432/postgres (docs/DATABASE.md).")
    return normalize_url(url)


@contextmanager
def temporary_database(server_url: str | None = None) -> Iterator[str]:
    """Create an empty database with the current schema; yield its URL; drop it afterwards."""
    server = make_url(server_url or admin_url())
    name = f"tutor_test_{uuid.uuid4().hex[:12]}"
    admin = create_engine(server, poolclass=NullPool, isolation_level="AUTOCOMMIT")
    with admin.connect() as conn:
        conn.execute(text(f'CREATE DATABASE "{name}"'))
    url = server.set(database=name).render_as_string(hide_password=False)
    try:
        engine = make_engine(url, pooled=False)
        init_db(engine)
        engine.dispose()
        yield url
    finally:
        with admin.connect() as conn:
            conn.execute(text(f'DROP DATABASE IF EXISTS "{name}" WITH (FORCE)'))
        admin.dispose()


def truncate_all(url: str) -> None:
    """Empty every application table and restart its IDs at 1 (keeps the schema and the Alembic version).

    DELETE instead of TRUNCATE: on small tables it is several times faster (no new files per table).
    """
    engine = make_engine(url, pooled=False)
    with engine.begin() as conn:
        conn.execute(text("SET LOCAL lock_timeout = '10s'"))
        for table in reversed(SQLModel.metadata.sorted_tables):  # children before parents
            conn.execute(text(f'DELETE FROM "{table.name}"'))  # noqa: S608
            if "id" in table.c:
                sequence = f"pg_get_serial_sequence('\"{table.name}\"', 'id')"
                conn.execute(text(f"SELECT setval({sequence}, 1, false)"))
    engine.dispose()


def table_rows(url: str, table: str, where: str = "", params: dict | None = None) -> list[dict]:
    """Rows of one application table as dicts, in primary-key order (tests and audits only)."""
    if table not in SQLModel.metadata.tables:
        raise ValueError(f"unknown table {table!r}")
    engine = make_engine(url, pooled=False)
    with engine.connect() as conn:
        rows = conn.execute(text(f'SELECT * FROM "{table}" {where} ORDER BY id'), params or {})  # noqa: S608
        out = [dict(r._mapping) for r in rows]
    engine.dispose()
    return out


def dump_rows(url: str, exclude: tuple[str, ...] = ()) -> str:
    """Every row of every application table as text, for leak checks over the whole database."""
    lines = []
    for table in SQLModel.metadata.sorted_tables:
        if table.name in exclude:
            continue
        lines += [f"{table.name}: {row}" for row in table_rows(url, table.name)]
    return "\n".join(lines)
