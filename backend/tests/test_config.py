import pytest
from pydantic import ValidationError

from app.core.config import get_settings


def test_loads_repo_config_yaml():
    s = get_settings()
    assert s.routing.threshold == 0.6
    assert s.pipeline[0] == "privacy_filter"
    assert "update_learner" in s.post_response
    assert s.topics() == ["high_blood_pressure", "type2_diabetes", "asthma", "migraine", "pneumonia"]
    assert s.llm.local.think is False


def test_settings_are_cached():
    assert get_settings() is get_settings()


def test_use_config_overrides_one_value(use_config):
    s = use_config({"routing": {"threshold": 0.8}})
    assert s.routing.threshold == 0.8
    assert s.routing.impl == "stub"  # untouched keys keep their config.yaml value


def test_env_overrides_yaml(use_config, monkeypatch):
    monkeypatch.setenv("OLLAMA_URL", "http://localhost:11434")
    monkeypatch.setenv("CLOUD_API_KEY", "")
    s = use_config()
    assert s.ollama_url == "http://localhost:11434"
    assert s.cloud_api_key is None
    assert s.cloud_enabled is False


@pytest.mark.parametrize(
    "overrides",
    [
        {"llm": {"local": {"think": True}}},  # thinking must stay off
        {"privacy": {"log_raw_text": True}},  # privacy invariant 1
        {"routing": {"threshold": 1.5}},
        {"learner": {"levels": {"basic_below": 0.8}}},  # basic_below > advanced_above
        {"routing": {"treshold": 0.5}},  # typo in a section key
    ],
)
def test_invalid_config_is_rejected(use_config, overrides):
    with pytest.raises(ValidationError):
        use_config(overrides)


def test_missing_config_file_is_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setenv("APP_CONFIG", str(tmp_path / "nope.yaml"))
    with pytest.raises(FileNotFoundError, match="config file not found"):
        get_settings()
