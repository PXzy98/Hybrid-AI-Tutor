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

## Step 1 — Contracts: schemas, registries, black-box stubs (2026-10-12)

Done:
- `app/core/schemas.py`: all shared models from the Step 1 spec, field names exact.
  - `CloudLabels`, `CloudRequest` and `CheckItemPublic` use `extra="forbid"`.
  - `RequestContext` keeps the PII mapping in a private attribute, accessed through `pii_mapping` / `set_pii_mapping()` / `clear_pii_mapping()`. It never appears in a dump, JSON or repr.
- `app/core/registry.py`: generic `Registry` (`register` / `get` / `names`), plus `import_submodules()` so that any new file in a package registers itself. Instances: `steps`, `checkers`, `knowledge_models`, `preference_models`, `routers`, `retrievers`.
- `app/pipeline/base.py`: `Step` and `Checker` protocols.
- Routing: `RouteScorer` protocol; `stub` router (fixed `routing.stub_score`, default 0.0); `load_router(name)`.
- RAG: `Retriever` protocol; `stub` retriever (returns `[]`); `fixture` retriever (keyword overlap over `data/synthetic/rag_fixture.jsonl`, 6 synthetic HBP chunks, with filter-then-fallback); `load_retriever(name)`.
- Contract tests (`tests/contracts/`) are parametrized over every registered implementation. Verified with a throw-away router file: it appeared as `[demo]` without any other change.
- `docs/INTERFACES.md`: a handout for Tongkai and Siyun.

Files: `backend/app/core/{schemas,registry}.py`, `backend/app/pipeline/base.py`, `backend/app/routing/{__init__,interface,stub}.py`, `backend/app/rag/{__init__,interface,stub}.py`, `data/synthetic/rag_fixture.jsonl`, `backend/tests/{test_schemas,test_registry}.py`, `backend/tests/contracts/*`, `docs/INTERFACES.md`.

Decisions:
- Black boxes are **classes with a no-argument constructor**, registered by name, with a sync method (`route_score` / `retrieve`). This replaces the design's plain functions. Classes can load models once in `__init__`, and the method signatures are exactly the design's functions.
- `retrieve()` gained optional `kc_ids` and `level` (as planned in design §9).
- `AskRequest.question` has a max length of 4000 characters. `student_id` and `topic` must not be empty. Whether the topic is in the config is checked by the API (Step 2), not by the schema.
- `Turn.created_at` defaults to the current UTC time.
- Routing contract: no network, under 1 s, deterministic. RAG contract: at most k chunks, all from the topic, filter falls back to topic results, never raises.

Interface changes:
- New: every model in `schemas.py` (first version). `retrieve()` has the extra optional parameters `kc_ids` and `level`. `RouteInput` has the optional `level` and `kc_ids`.

Known gaps / TODO:
- `docs/INTERFACES.md` still needs to be sent to Tongkai and Siyun, who must confirm the `cloud_safe` force-local rule and the threshold ownership.
- The fixture chunks are synthetic placeholders, not course material.

How to try it:
```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m pytest tests/contracts -v
```

## Step 2 — Pipeline runner, API skeleton, storage (2026-10-12)

Done:
- `pipeline/runner.py`: `PipelineRunner` times every step into `ctx.timings_ms`, even when the step fails, and applies the failure policy:
  - `stop` raises `PipelineError(step, reason)`;
  - `skip` continues;
  - `warn` continues and adds a generic warning.
  - Post-response steps run as a FastAPI background task; their errors are only logged. Log lines contain the step name, the exception type and the request id, never the exception message or request text.
- `build_runner(services)` builds the runner from `config.pipeline` / `config.post_response`. It refuses to start unless `privacy_filter` is the first step with `on_error="stop"` (privacy invariant 5). An unknown step name fails at startup.
- `core/services.py`: a `Services` container (settings, DB engine, router, retriever, session store), built once in the app lifespan. Steps get it in their constructor (`BaseStep(services)`).
- 11 step modules registered under the config names:
  - **real:** `route`, `retrieve`, `record`;
  - **placeholders:** the other 8.
- `route`: target defaults to `local`. Score ≥ threshold → `cloud`, unless `force_local_if_not_cloud_safe` and `pii.cloud_safe` is False (a reason is added to `RouteScore.reasons`). The router runs in a worker thread. `retrieve` passes the sanitized question, `rag.k`, the `understanding.kc_ids` and the personalized `focus_level`.
- `record` writes `request_log` plus the student and tutor turns, with sanitized text only. The answer is re-redacted with the known PII entities first (`privacy/redact.py`), because a local model may repeat a name.
- Storage: `storage/{db,models}.py` (SQLModel; tables `request_log`, `session_turn`, JSON columns for timings, checks and warnings). Session store: `SessionStore` protocol + `SqliteSessionStore` (registry `session_stores`, config `sessions.store`).
- API: `POST /api/v1/ask`, `GET /api/v1/sessions/{id}`, `GET /api/v1/topics`, `GET /api/v1/health`, CORS for the Vite dev server. `app/export_openapi.py` writes `frontend/openapi.json`.
- Tests:
  - `conftest.py` gives every test its own SQLite file through an autouse `DATABASE_URL`, so `data/app.db` is never touched. The `make_client(overrides)` fixture starts the app with config overrides and an unreachable Ollama URL.
  - New tests: runner policies, config validation of the pipeline, the route and retrieve steps, the API, CORS, the OpenAPI export and redaction. **A DB-dump test asserts that a name, a student number and the question words never reach the database.**
- Manual check: `uvicorn` served `/docs` (200). `/api/v1/ask` returned timings for all 10 steps. `/health` showed Ollama reachable at 192.168.2.25 with `qwen3.5:9b` available.

Files: `backend/app/pipeline/{base,runner}.py`, `backend/app/pipeline/steps/*.py`, `backend/app/core/services.py`, `backend/app/storage/{db,models}.py`, `backend/app/sessions/{__init__,interface,sqlite}.py`, `backend/app/privacy/redact.py`, `backend/app/api/deps.py`, `backend/app/api/v1/{__init__,ask,sessions,topics,health}.py`, `backend/app/main.py`, `backend/app/export_openapi.py`, `backend/tests/{conftest,test_runner,test_steps_route_retrieve,test_api,test_redact}.py`.

Decisions:
- **The placeholder `privacy_filter` fails closed.** It sets `sanitized_text = "[question withheld: privacy filter not installed]"`, `cloud_safe=False` and `is_sensitive=True`. Until Step 4, nothing goes to the cloud, nothing raw is stored, and retrieval sees no question text. Step 4 replaces the step itself; the rest of the pipeline is unchanged.
- The placeholder `generate` echoes the **sanitized** question only. The placeholder `restore` just clears the PII mapping.
- Session history is loaded by the API (`sessions.history_turns`) before the pipeline runs, not by a step.
- A failing step answers **503** with a generic message, the step name and the request id. An unknown topic answers **422**. Neither response contains the question.
- Whether a topic is valid is checked against `config.courses[course_id].topics` in the API.
- `ask` responses take `kc_level` and `next_kc` only from a personalized `LearnerContext`.
- FastAPI dependencies use `Annotated` aliases (`ServicesDep`, `RunnerDep`).

Interface changes:
- New registry `session_stores` in `core/registry.py`. No schema changes.

Known gaps / TODO:
- 8 of the 10 pipeline steps, and the post-response step, are placeholders (filled in Steps 3, 4, 6, 7, 8, 11).
- `/api/v1/topics` returns `kc_count = 0` until Step 5.
- The app logger is not configured yet, so the startup "pipeline: …" INFO line is not printed under uvicorn's default log config.

How to try it:
```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m uvicorn app.main:app --reload     # then open http://127.0.0.1:8000/docs
```
```bash
curl -X POST http://127.0.0.1:8000/api/v1/ask -H "Content-Type: application/json" -d '{"student_id":"demo-1","topic":"high_blood_pressure","question":"What does the top number mean?"}'
```

## Step 2b — Accounts and authentication (2026-10-12)

Added on Oct 12, after the decision to give each student an account. The design (§2 principle 2, §7.5, §8.1, §8.3, §9) and the implementation prompts (new Step 2b; Steps 7, 9, 10, 13 and 14 now take identity from the session) were updated in a separate commit first.

Done:
- Tables:
  - `account`: username (lower-case, unique), display_name, role, argon2 password_hash, random `student_id` (students only), active, must_change_password, failed_logins, locked_until, timestamps.
  - `auth_session`: only the SHA-256 of the cookie token is stored.
  - `session_turn` has a `student_id` column for ownership checks.
- `app/auth/`:
  - `passwords.py`: argon2; temporary passwords with no look-alike characters; `burn_time` gives unknown usernames the same cost as real ones.
  - `sessions.py`: create, resolve (expired → deleted; inactive account → rejected), revoke, `revoke_all`.
  - `service.py` (`AccountService`): create student / instructor; login with lockout; change / set / reset password; update; delete; `bootstrap_instructor()` from `.env`.
  - `purge.py`: generic `purge_student` (see Decisions).
  - `deps.py`: `CurrentUser` and `AnyUser` / `Student` / `Instructor`. A pending password change blocks everything except `auth/*`.
  - `cli.py`: `create-instructor` and `set-password`.
- API:
  - `auth/login` (httpOnly, SameSite=Lax cookie), `auth/logout`, `auth/me`, `auth/change-password`.
  - `admin/students`: GET, POST, PATCH, DELETE, and POST `reset-password`. They are instructor-only, act on student accounts only, and send `Cache-Control: no-store` with temporary passwords.
- Changed Step 2 endpoints:
  - `/ask` requires a student. The body is `AskBody`, with no `student_id`; the server fills `AskRequest.student_id` from the session. A session owned by someone else → 404.
  - `/sessions/{id}` returns only the caller's own sessions.
  - `/topics` needs any login; `/health` stays public.
  - CORS allows credentials.
- The lifespan bootstraps the first instructor from `INSTRUCTOR_USERNAME` / `INSTRUCTOR_INITIAL_PASSWORD`.
- Tests (113 in total, all passing):
  - login, logout and me; generic errors; lockout; expiry; forced password change; other sessions ended on password change;
  - students cannot see or continue each other's sessions; a forged `student_id` in the body is ignored;
  - students get 403 on `admin/*`, anonymous callers get 401, the instructor gets 403 on `/ask`;
  - admin endpoints cannot touch the instructor;
  - reset and deactivate end live sessions;
  - delete purges the account, sessions, turns and a throw-away "future" table, keeps other students' rows and anonymizes `request_log`;
  - usernames and display names never appear in `request_log`, `session_turn` or `auth_session`;
  - env bootstrap without duplicates; CLI recovery from a lockout.
- Manual check with uvicorn and curl, all as expected:
  1. bootstrap instructor → login → 403 until the password is changed → change it;
  2. create a student → login with the temporary password → `/ask` blocked → change the password → `/ask` works;
  3. the student gets 403 on admin;
  4. delete the student → the student's cookie returns 401 → the list is empty.

Files: `backend/app/auth/*`, `backend/app/api/v1/{auth,admin_students,ask,sessions,topics,__init__}.py`, `backend/app/storage/models.py`, `backend/app/sessions/{interface,sqlite}.py`, `backend/app/pipeline/steps/record.py`, `backend/app/core/{config,services}.py`, `backend/app/main.py`, `config.yaml`, `.env.example`, `backend/pyproject.toml`, `backend/tests/{conftest,test_api,test_auth,test_admin_students}.py`, `README.md`, `docs/System_Design_v3.md`, `docs/IMPLEMENTATION_PROMPTS.md`, `docs/diagrams/architecture-v3.*`.

Decisions:
- **Server-side sessions, not JWT.** Deactivating, resetting or deleting a student must log them out immediately.
- **Deletion is generic.** `purge_student` deletes from every table that has a `student_id` column (found through `SQLModel.metadata`), so the learner tables of Steps 6 and 12 are covered automatically. `request_log` rows are anonymized to `student_id = "deleted"` instead.
- **Locked accounts answer 429** ("too many failed attempts"). All other failures answer the same 401 "invalid username or password". Deactivated accounts look like wrong credentials.
- **Errors return the same answer as "not found".** A session or account the caller may not see returns 404, so its existence is not revealed.
- The instructor's display name defaults to the username. Instructors have no `student_id` and cannot use student endpoints.
- `ADMIN_TOKEN` is removed; Step 13 uses `require_instructor`.
- Tests: `conftest.py` blanks `INSTRUCTOR_*` env vars, so a developer's `.env` cannot change test behaviour. The `api`, `student_client` and `instructor_client` fixtures log in through the real endpoint.

Interface changes:
- `SessionStore.append(session_id, student_id, turn)` (was `append(session_id, turn)`), plus a new `SessionStore.owner(session_id)`. This is internal; teammates do not implement session stores.
- `/api/v1/ask` request body: `AskBody` without `student_id`. `core/schemas.AskRequest` is **unchanged**, so routing and RAG are unaffected.
- `Services` gained `accounts`.

Known gaps / TODO:
- There are no DB migrations. A `data/app.db` created before this step must be deleted (done on this machine). Consider Alembic before real data exists.
- There is no rate limit per IP, only per-account lockout. That is acceptable on a closed LAN; revisit before any public deployment.
- The frontend login and student-management pages come in Steps 9 and 13.

How to try it:
```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
$env:INSTRUCTOR_USERNAME="prof"; $env:INSTRUCTOR_INITIAL_PASSWORD="initial-pass-123"
..\.venv\Scripts\python -m uvicorn app.main:app --reload      # then use /docs: auth/login, change-password, admin/students
```
