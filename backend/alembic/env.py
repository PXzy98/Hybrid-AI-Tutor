"""Alembic environment: the app's tables (SQLModel.metadata) on the database of DATABASE_URL."""
from alembic import context
from sqlmodel import SQLModel

from app.storage import models  # noqa: F401  (registers the tables)

target_metadata = SQLModel.metadata


def _run(connection) -> None:
    context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    attributes = context.config.attributes
    if attributes.get("connection") is not None:  # init_db passes its locked connection
        _run(attributes["connection"])
        return
    engine = attributes.get("engine")
    if engine is None:
        from app.core.config import get_settings
        from app.storage.db import make_engine

        settings = get_settings()
        password = settings.pgpassword.get_secret_value() if settings.pgpassword else None
        engine = make_engine(settings.database_url, pooled=False, password=password)
    with engine.connect() as connection:
        _run(connection)


if context.is_offline_mode():
    raise SystemExit("Offline SQL generation is not used; run against a database.")
run_migrations_online()
