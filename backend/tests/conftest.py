import copy
import os
from pathlib import Path

import pytest
import yaml

from app.core.config import DEFAULT_CONFIG, Settings, get_settings


def _deep_merge(base: dict, overrides: dict) -> dict:
    out = copy.deepcopy(base)
    for k, v in overrides.items():
        if isinstance(v, dict) and isinstance(out.get(k), dict):
            out[k] = _deep_merge(out[k], v)
        else:
            out[k] = v
    return out


# Applied under every test's config: the small spaCy model (the large one is for production).
# TEST_LEARNER_KNOWLEDGE=rule runs the whole suite with the fallback knowledge model.
TEST_BASE = {"privacy": {"spacy_model": "en_core_web_sm"},
             "learner": {"knowledge": os.environ.get("TEST_LEARNER_KNOWLEDGE", "bkt")}}


def _write_config(path: Path, overrides: dict) -> None:
    base = yaml.safe_load(DEFAULT_CONFIG.read_text(encoding="utf-8"))
    path.write_text(yaml.safe_dump(_deep_merge(_deep_merge(base, TEST_BASE), overrides)), encoding="utf-8")


@pytest.fixture(autouse=True)
def _fresh_settings(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    """Every test starts with an empty settings cache and its own SQLite file (never data/app.db)."""
    # Isolate tests from machine-specific .env (including RAG and privacy overrides).
    monkeypatch.setitem(Settings.model_config, "env_file", None)
    _write_config(tmp_path / "config.yaml", {})
    monkeypatch.setenv("APP_CONFIG", str(tmp_path / "config.yaml"))
    monkeypatch.setenv("DATABASE_URL", f"sqlite:///{(tmp_path / 'test.db').as_posix()}")
    # a developer's .env must not change test behaviour: no instructor bootstrap unless a test asks for it
    monkeypatch.setenv("INSTRUCTOR_USERNAME", "")
    monkeypatch.setenv("INSTRUCTOR_INITIAL_PASSWORD", "")
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
        path = tmp_path / "config.yaml"
        _write_config(path, overrides or {})
        monkeypatch.setenv("APP_CONFIG", str(path))
        get_settings.cache_clear()
        return get_settings()

    return _apply


# ------------------------------------------------------------------------------- accounts
PASSWORD = "correct-horse-battery"


class Api:
    """A started TestClient plus helpers to create accounts and log in.

    The local model is replaced by a FakeLLMClient (`api.local_llm`), so API tests never need Ollama.
    """

    def __init__(self, client) -> None:
        from app.llm.fake import FakeLLMClient

        self.client = client
        self.services = client.app.state.services
        self.accounts = self.services.accounts
        self.local_llm = FakeLLMClient("Fake local answer.", model="fake-local")
        self.services.local_llm = self.local_llm

    def make_student(self, username: str = "alice", display_name: str = "Alice Tremblay",
                     password: str = PASSWORD, must_change: bool = False):
        account, temp = self.accounts.create_student(username, display_name)
        if not must_change:
            account = self.accounts.set_password(account.id, password, must_change=False)
        self.last_temp_password = temp  # for tests of the first-login flow
        return account

    def make_instructor(self, username: str = "prof", password: str = PASSWORD, must_change: bool = False):
        return self.accounts.create_instructor(username, password, must_change=must_change)

    def login(self, username: str, password: str = PASSWORD, expect: int = 200):
        self.client.cookies.clear()
        r = self.client.post("/api/v1/auth/login", json={"username": username, "password": password})
        assert r.status_code == expect, r.text
        return r


@pytest.fixture
def api(make_client):
    with make_client() as client:
        yield Api(client)


@pytest.fixture
def student_client(api):
    api.make_student()
    api.login("alice")
    return api.client


@pytest.fixture
def instructor_client(api):
    api.make_instructor()
    api.login("prof")
    return api.client
