import copy
from pathlib import Path

import pytest
import yaml

from app.core.config import DEFAULT_CONFIG, get_settings


def _deep_merge(base: dict, overrides: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


@pytest.fixture(autouse=True)
def _fresh_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every test starts with an empty settings cache and its own SQLite file (never data/app.db)."""
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


@pytest.fixture
def make_client(use_config, monkeypatch: pytest.MonkeyPatch):
    """Start the app (lifespan included) with config overrides: `with make_client({...}) as client:`."""
    from fastapi.testclient import TestClient

    from app.main import create_app

    def _make(overrides: dict | None = None) -> TestClient:
        monkeypatch.setenv("OLLAMA_URL", "http://127.0.0.1:9")  # closed port: health check fails fast
        use_config(overrides)
        return TestClient(create_app())

    return _make


@pytest.fixture
def use_config(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Override parts of config.yaml for one test.

    Example: `settings = use_config({"routing": {"threshold": 0.8}})`
    """

    def _apply(overrides: dict | None = None):
        base = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
        path = tmp_path / "config.yaml"
        path.write_text(yaml.safe_dump(_deep_merge(base, overrides or {})), encoding="utf-8")
        monkeypatch.setenv("APP_CONFIG", str(path))
        get_settings.cache_clear()
        return get_settings()

    return _apply
