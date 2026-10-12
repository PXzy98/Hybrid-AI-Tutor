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
def _fresh_settings():
    """Every test starts and ends with an empty settings cache."""
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


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
