"""Settings of the evaluation scripts that the app does not read (JUDGE_BASE_URL, JUDGE_MODEL, ...).

The process environment wins; otherwise the repository's .env, the same file the app's settings read. The
app's settings loader does not export .env values into the environment, so a script that only looked at
os.environ would miss them.
"""
import os
from functools import cache
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[2]


@cache
def _dotenv() -> dict[str, str | None]:
    path = ROOT / ".env"
    return dotenv_values(path) if path.exists() else {}


def env(name: str, default: str | None = None) -> str | None:
    """The variable from the environment, else from the repository's .env, else `default`."""
    value = os.environ.get(name)
    if value is None:
        value = _dotenv().get(name)
    return value if value else default


def api_root(url: str) -> str:
    """An OpenAI-compatible server address with or without the trailing /v1, as the API root ending in /v1."""
    url = url.rstrip("/")
    return url if url.endswith("/v1") else f"{url}/v1"
