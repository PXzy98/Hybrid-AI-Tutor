from pathlib import Path

from sqlalchemy import Engine
from sqlmodel import SQLModel, create_engine

from app.storage import models  # noqa: F401  (registers the tables on SQLModel.metadata)


def make_engine(url: str) -> Engine:
    """SQLite file engine (parent folder created) or any other SQLAlchemy URL."""
    if url.startswith("sqlite:///") and not url.startswith("sqlite:///:memory:"):
        Path(url.removeprefix("sqlite:///")).parent.mkdir(parents=True, exist_ok=True)
    connect_args = {"check_same_thread": False} if url.startswith("sqlite") else {}
    return create_engine(url, connect_args=connect_args)


def init_db(engine: Engine) -> None:
    SQLModel.metadata.create_all(engine)
