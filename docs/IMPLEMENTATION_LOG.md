# Implementation Log

One entry per step of [IMPLEMENTATION_PROMPTS.md](IMPLEMENTATION_PROMPTS.md). Each new agent session reads this file first.

## Step 0 — Repository bootstrap (2026-10-12)

Done:
- Folder layout from design §10. Python packages have `__init__.py`; otherwise-empty folders have a short README.
- `backend/pyproject.toml` (package `app`): runtime dependencies, `dev` extras, ruff and pytest config. pytest markers `ollama`, `cloud`, `presidio`; by default `-m "not ollama and not cloud"`.
- `.gitignore`, `.env.example`, `config.yaml` (full structure from design §9 plus `routing`, `rag`, `privacy`, `sessions`, `courses`).
- `backend/app/core/config.py`: `Settings` loads `config.yaml` (or `APP_CONFIG`) plus `.env`; `get_settings()` is cached.
- `backend/tests/conftest.py`: a `use_config(overrides)` fixture deep-merges overrides into a temp copy of `config.yaml`; the settings cache is cleared around every test.
- `.github/workflows/ci.yml`: ruff + pytest with `en_core_web_sm`. The frontend job is stubbed (commented out) for Step 9.
- Copied unchanged: the course folder's `model-boundary-test/` → `eval/model-boundary-test/` (without `__pycache__`), and `ai-tutor-bench/data/testset.jsonl` → `data/synthetic/ai_tutor_bench_testset.jsonl`.
- Root `README.md` with the project summary, layout and dev setup.

Files: `backend/pyproject.toml`, `backend/app/core/config.py`, `backend/tests/{conftest.py,test_config.py}`, `config.yaml`, `.env.example`, `.gitignore`, `.github/workflows/ci.yml`, `README.md`, `eval/`, `data/synthetic/`.

Decisions:
- **Secrets and URLs live in the environment only**: `OLLAMA_URL`, `CLOUD_BASE_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL`, `ADMIN_TOKEN`, `DATABASE_URL` are top-level `Settings` fields. `config.yaml` has no `base_url` or cloud `model`, unlike the example in design §9. Precedence: env > `.env` > `config.yaml` > defaults. Empty `.env` values count as unset.
- `ollama_url` is the native API root (`http://192.168.2.25:11434`, no `/v1`). Step 3 uses `/api/chat`, because thinking has to be turned off explicitly.
- Two invariants are enforced by config types:
  - `llm.local.think` and `llm.understand.think` are `Literal[False]`;
  - `privacy.log_raw_text` is `Literal[False]`.
- Config sections use `extra="forbid"`, so a typo in `config.yaml` fails at startup. Top-level unknown keys are ignored, so that unrelated `.env` variables do not break startup.
- `learner.weak_evidence: false` for the MVP (design §12). Beta turns it on after E1.
- `privacy.entities` lists the three built-in Presidio entities plus the three custom recognizers planned for Step 4. DATE_TIME and LOCATION are left out (over-redaction).
- `cloud_enabled` is true only when both `CLOUD_API_KEY` and `CLOUD_MODEL` are set.
- Python venv at repo-root `.venv` (git-ignored).

Interface changes: none (no schemas yet).

Known gaps / TODO:
- `content/topics/` is empty until Step 5; `frontend/` until Step 9.
- `en_core_web_lg` (production spaCy model) is not installed yet; Step 4 decides whether the dev machine needs it.

How to try it:
```powershell
.venv\Scripts\python -m pip install -e "backend[dev]"
cd backend
..\.venv\Scripts\python -m ruff check .
..\.venv\Scripts\python -m pytest -q
```
