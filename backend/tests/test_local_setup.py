"""First-run configuration preserves secrets and validates the account inputs before startup."""

import importlib.util
import io
from pathlib import Path

import pytest
from dotenv import dotenv_values


def setup_module_object():
    path = Path(__file__).resolve().parents[2] / "setup_local.py"
    spec = importlib.util.spec_from_file_location("tutor_local_setup", path)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_env_values_round_trip_without_shell_interpolation():
    setup = setup_module_object()
    password = 'Strong"pass\\word$123汉字'
    values = dotenv_values(stream=io.StringIO(setup.env_text("teacher", password, "qwen3.5:9b-q4_K_M")))
    assert values["INSTRUCTOR_INITIAL_PASSWORD"] == password
    assert values["OLLAMA_URL"] == "http://127.0.0.1:11434"
    assert values["LLM__LOCAL__MODEL"] == values["LLM__UNDERSTAND__MODEL"] == "qwen3.5:9b-q4_K_M"
    assert values["ROUTING__IMPL"] == "semantic" and values["RAG__IMPL"] == "medical_hybrid"


@pytest.mark.parametrize("username,password", [
    ("teacher", "short"), ("teacher1234", "teacher1234"),
    ("teacher", "LongPassword\nInjected"), ("x", "LongPassword123"),
    ("teacher", "LongPassword${HOME}"),
])
def test_invalid_initial_account_values_are_rejected(username, password):
    with pytest.raises(ValueError):
        setup_module_object().env_text(username, password, "qwen3.5:9b")


def test_existing_env_is_preserved_without_password_prompt(tmp_path, monkeypatch):
    setup = setup_module_object()
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    old = b"LOCAL_SENTINEL=keep-this-file\n"
    (tmp_path / ".env").write_bytes(old)
    monkeypatch.setattr("builtins.input", lambda *args: pytest.fail("existing config must not prompt"))
    setup.initialize_env()
    assert (tmp_path / ".env").read_bytes() == old


def test_first_run_retries_short_and_mismatched_passwords(tmp_path, monkeypatch):
    setup = setup_module_object()
    monkeypatch.setattr(setup, "ROOT", tmp_path)
    inputs = iter(["Teacher", "qwen3.5:9b-q4_K_M"])
    passwords = iter(["short", "TestPassword123", "DoesNotMatch123", "TestPassword123", "TestPassword123"])
    monkeypatch.setattr("builtins.input", lambda *args: next(inputs))
    monkeypatch.setattr(setup.getpass, "getpass", lambda *args: next(passwords))
    setup.initialize_env()
    values = dotenv_values(tmp_path / ".env")
    assert values["INSTRUCTOR_USERNAME"] == "teacher"
    assert values["INSTRUCTOR_INITIAL_PASSWORD"] == "TestPassword123"
