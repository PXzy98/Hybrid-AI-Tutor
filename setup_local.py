"""Prepare a local Windows/Linux installation without copying old project code.

Run with Python 3.12: python setup_local.py
Existing .env, accounts and downloaded model caches are preserved.
"""

from __future__ import annotations

import argparse
import getpass
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def execute(args, cwd, env, *, capture=False):
    result = subprocess.run(
        [str(a) for a in args], cwd=cwd, env=env, check=True,
        text=True, encoding="utf-8", errors="replace",
        stdout=subprocess.PIPE if capture else None,
    )
    return result.stdout.strip() if capture else ""


def valid_password(password, username, minimum=10):
    return (
        len(password) >= minimum
        and password.strip().lower() != username.strip().lower()
        and not any(c in password for c in "\r\n\0")
        and "${" not in password  # dotenv expands this sequence even inside quoted values.
    )


def env_text(username, password, ollama_model):
    """Quote values as data; passwords are never interpolated into shell commands."""
    if not re.fullmatch(r"[a-z0-9._-]{3,32}", username) or not valid_password(password, username):
        raise ValueError("Use a username and a different password of at least 10 characters.")
    values = {
        "OLLAMA_URL": "http://127.0.0.1:11434",
        "LLM__LOCAL__MODEL": ollama_model,
        "LLM__UNDERSTAND__MODEL": ollama_model,
        "CLOUD_BASE_URL": "https://api.openai.com/v1",
        "CLOUD_API_KEY": "", "CLOUD_MODEL": "",
        "INSTRUCTOR_USERNAME": username,
        "INSTRUCTOR_INITIAL_PASSWORD": password,
        "DATABASE_URL": "",
        "ROUTING__IMPL": "semantic", "RAG__IMPL": "medical_hybrid",
        "PRIVACY__SPACY_MODEL": "en_core_web_lg",
    }
    return "# Local settings: never commit this file.\n" + "".join(
        f"{k}={json.dumps(v, ensure_ascii=False)}\n" for k, v in values.items()
    )


def initialize_env():
    path = ROOT / ".env"
    if path.exists():
        print("Keeping existing .env.", flush=True)
        return
    while True:
        username = (input("First instructor username [teacher]: ").strip() or "teacher").lower()
        if re.fullmatch(r"[a-z0-9._-]{3,32}", username):
            break
        print("Use 3-32 characters from a-z, 0-9, dot, underscore or hyphen.")
    while True:
        password = getpass.getpass("Initial password (at least 10 characters): ")
        if not valid_password(password, username):
            print("Use at least 10 characters, different from the username; avoid ${...} sequences.")
            continue
        if password != getpass.getpass("Repeat password: "):
            print("Passwords do not match.")
            continue
        break
    model = input("Ollama model [qwen3.5:9b-q4_K_M]: ").strip() or "qwen3.5:9b-q4_K_M"
    # Exclusive creation also prevents overwriting a concurrently created config.
    with path.open("x", encoding="utf-8", newline="\n") as file:
        file.write(env_text(username, password, model))
    print("Created local .env. The first login requires a password change.", flush=True)


CONFIG_CHECK = """
import json
from app.core.config import get_settings
s = get_settings()
assert s.routing.impl == 'semantic', 'Check ROUTING__IMPL in the environment/.env'
assert s.rag.impl == 'medical_hybrid', 'Check RAG__IMPL in the environment/.env'
if s.instructor_username and s.instructor_initial_password:
    assert len(s.instructor_initial_password.get_secret_value()) >= s.auth.min_password_length, (
        'Effective instructor password is too short; check environment overrides and .env'
    )
print(json.dumps({'privacy_model': s.privacy.spacy_model}))
"""

ASSET_CHECK = """
from app.core.config import get_settings
from app.routing.models import sentence_encoder, pair_encoder, load_weights
c = get_settings().routing
sentence_encoder(c.embedding_model, c.model_cache_dir, True)
for name in (c.relevance_model, c.answerability_model):
    pair_encoder(name, c.model_cache_dir, True)
for method in c.enabled_methods:
    meta, _ = load_weights(c, method)
    assert meta['training_count'] == 500
print('Local semantic assets and 500-question weights are ready.')
"""

STARTUP_CHECK = """
from fastapi.testclient import TestClient
from app.main import app
with TestClient(app):
    print('Application startup passed. No answer-generation provider was called.')
"""


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--reuse-python", type=Path, help="Reuse an existing virtualenv's Python executable")
    ap.add_argument("--test", action="store_true", help="Also run backend and frontend automated tests")
    args = ap.parse_args(argv)
    if sys.version_info < (3, 12):  # noqa: UP036 - this bootstrap runs before dependency installation.
        raise RuntimeError("Run this script with Python 3.12 or newer.")
    env = os.environ.copy()
    env["APP_CONFIG"] = str(ROOT / "config.yaml")
    env["PYTHONUTF8"] = "1"
    python = args.reuse_python.resolve() if args.reuse_python else ROOT / ".venv" / (
        "Scripts/python.exe" if os.name == "nt" else "bin/python"
    )
    if args.reuse_python and not python.is_file():
        raise RuntimeError("Existing virtualenv Python not found: " + str(python))
    if not python.is_file():
        execute([sys.executable, "-m", "venv", ROOT / ".venv"], ROOT, env)
    initialize_env()
    backend, frontend = ROOT / "backend", ROOT / "frontend"
    execute([python, "-m", "pip", "install", "--upgrade", "pip"], ROOT, env)
    # Avoid a large accelerator build on a new CPU-only semantic-router environment.
    torch_probe = subprocess.run(
        [str(python), "-c", ("import importlib.metadata as m; from packaging.version import Version; "
                            "assert Version(m.version('torch')) >= Version('2.6')")],
        cwd=ROOT, env=env, capture_output=True, check=False,
    )
    if torch_probe.returncode:
        execute([python, "-m", "pip", "install", "torch>=2.6", "--index-url",
                 "https://download.pytorch.org/whl/cpu"], ROOT, env)
    execute([python, "-m", "pip", "install", "-e", ".[dev]"], backend, env)
    cfg = json.loads(execute([python, "-c", CONFIG_CHECK], backend, env, capture=True))
    # Use exactly the effective configuration, including environment overrides.
    models = [cfg["privacy_model"]]
    if args.test and "en_core_web_sm" not in models:
        models.append("en_core_web_sm")
    for model in models:
        probe = subprocess.run(
            [str(python), "-c", "import spacy,sys; spacy.load(sys.argv[1])", model],
            cwd=backend, env=env, capture_output=True, check=False,
        )
        if probe.returncode:
            execute([python, "-m", "spacy", "download", model], backend, env)
    try:
        execute([python, "-c", ASSET_CHECK], backend, env, capture=True)
    except subprocess.CalledProcessError:
        execute([python, "-m", "app.routing.prepare"], backend, env)
        execute([python, "-c", ASSET_CHECK], backend, env)
    else:
        print("Reusing cached semantic/evidence models and trained weights.", flush=True)
    execute([python, "-c", STARTUP_CHECK], backend, env)
    npm = shutil.which("npm.cmd") or shutil.which("npm")
    if not npm:
        raise RuntimeError("Install Node.js/npm and reopen the terminal, then rerun setup.")
    execute([npm, "ci"], frontend, env)
    execute([npm, "run", "build"], frontend, env)
    if args.test:
        execute([python, "-m", "pytest", "-q"], backend, env)
        execute([npm, "test"], frontend, env)
    print("\nREADY. Start the backend and frontend in separate PowerShell windows.")
    if args.reuse_python:
        print('Backend: .\\start_backend.ps1 -PythonPath "' + str(python) + '"')
    else:
        print("Backend: .\\start_backend.ps1")
    print("Frontend: .\\start_frontend.ps1")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (RuntimeError, OSError, ValueError, subprocess.CalledProcessError) as error:
        print("\nSETUP STOPPED: " + str(error), file=sys.stderr)
        print("Fix the error above and rerun; existing config/data are preserved.", file=sys.stderr)
        raise SystemExit(1) from None
