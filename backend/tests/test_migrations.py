"""Task Z3: PostgreSQL only; the Alembic migrations create exactly the tables the models describe."""
import pytest
from alembic.autogenerate import compare_metadata
from alembic.migration import MigrationContext
from sqlalchemy import inspect, text
from sqlmodel import SQLModel

from app.storage.db import DatabaseConfigError, head_revision, init_db, make_engine, normalize_url
from app.storage.testing import temporary_database


def test_migrations_match_the_models_and_upgrading_twice_is_a_no_op():
    with temporary_database() as url:
        engine = make_engine(url, pooled=False)
        init_db(engine)  # already at head: nothing to do
        with engine.connect() as conn:
            diff = compare_metadata(MigrationContext.configure(conn, opts={"compare_type": True}),
                                    SQLModel.metadata)
            version = conn.execute(text("SELECT version_num FROM alembic_version")).scalar_one()
        assert diff == [], diff
        assert version == head_revision()
        assert set(inspect(engine).get_table_names()) == set(SQLModel.metadata.tables) | {"alembic_version"}
        engine.dispose()


def test_timestamps_are_timezone_aware():
    with temporary_database() as url:
        engine = make_engine(url, pooled=False)
        columns = {c["name"]: c["type"] for c in inspect(engine).get_columns("auth_session")}
        assert columns["expires_at"].timezone is True
        engine.dispose()


@pytest.mark.parametrize("url", ["", None, "sqlite:///data/app.db", "mysql://u@h/db"])
def test_only_postgresql_urls_are_accepted(url):
    with pytest.raises(DatabaseConfigError):
        normalize_url(url)


def test_plain_postgresql_urls_use_psycopg():
    assert normalize_url("postgresql://tutor@db:5432/tutor") == "postgresql+psycopg://tutor@db:5432/tutor"
    assert normalize_url("postgres://tutor@db/tutor") == "postgresql+psycopg://tutor@db/tutor"


def test_test_settings_come_from_dotenv_unless_set_in_the_environment(tmp_path, monkeypatch):
    import app.storage.testing as testing

    env = tmp_path / ".env"
    env.write_text("TEST_DATABASE_URL=postgresql://tutor@127.0.0.1:5432/tutor\nPGPASSWORD=from-dotenv\n",
                   encoding="utf-8")
    monkeypatch.setattr(testing, "DOTENV", env)
    monkeypatch.delenv("TEST_DATABASE_URL", raising=False)
    monkeypatch.delenv("PGPASSWORD", raising=False)
    assert testing.admin_url() == "postgresql+psycopg://tutor@127.0.0.1:5432/tutor"
    import os

    assert os.environ["PGPASSWORD"] == "from-dotenv"
    monkeypatch.setenv("TEST_DATABASE_URL", "postgresql://other@db/x")
    assert testing.admin_url() == "postgresql+psycopg://other@db/x"  # the environment wins
