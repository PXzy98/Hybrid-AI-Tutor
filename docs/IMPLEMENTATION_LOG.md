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

## Step 3 — LLM layer: local client, cloud guard, generate (2026-10-12)

Done:
- `llm/base.py`: the `LLMClient` protocol (`async complete(messages, *, json_schema, max_tokens) -> LLMResult`), `LLMError` / `LLMUnavailable`, and `strip_think()`. Error messages never contain prompt text.
- `llm/ollama_client.py`: native `POST /api/chat` with `stream: false` and **`think: false` always**.
  - Options: `temperature`, `num_ctx`, `num_predict` (`llm.local.max_tokens`, new, default 1024). `json_schema` is sent as Ollama `format`.
  - Retries once on connection errors only; a timeout is not retried.
  - HTTP errors, invalid JSON or an empty reply → `LLMError`.
  - An httpx transport can be injected for tests.
- `llm/openai_compat.py`: OpenAI-compatible client (`openai` SDK, `max_retries=1`). Connection, timeout, rate-limit and auth errors → `LLMUnavailable`; other API errors → `LLMError`. A JSON schema becomes `response_format: json_object`.
- `llm/cloud_guard.py`:
  - `build_cloud_request(ctx)`: the allow-list is sanitized question, topic, passage texts, `to_cloud_labels()` (default labels when unpersonalized) and language.
  - `CloudClient.complete(req)` is the **only** way to the cloud. It rejects anything that is not a `CloudRequest` (`TypeError`), re-validates the request (so `model_construct` cannot smuggle extra fields), and builds messages with `render_cloud(req)`. `available` is False when `CLOUD_API_KEY` / `CLOUD_MODEL` are missing.
- `llm/fake.py`: `FakeLLMClient`. Replies can be scripted as text, a callable or an exception; it records calls and has `sent_text()` for leak assertions.
- `llm/__init__.py`: `build_llm_clients(settings)`. `Services` gained `local_llm` and `cloud_llm`.
- `prompts/` (now a package):
  - `base_system.md` holds the safety rules: general knowledge only, no diagnosis, no medication or dose changes, refer personal situations to a clinician, emergency signs → urgent care, cite material as [n] and say so when it does not cover the question, no invented facts. They are identical for every level and both routes.
  - `render_local(ctx)` may use the raw question, the sanitized history, the passages and a one-line level.
  - `render_cloud(req)` takes only a `CloudRequest` and adds the rule to keep placeholders such as `<PERSON_1>`.
- The real `generate` step:
  - local route → `render_local` + Ollama;
  - cloud route → `build_cloud_request` (stored in `ctx.cloud_request`) → `CloudClient`;
  - cloud not configured or failing → local fallback (`fell_back=True`, user-visible warning) if `llm.cloud.fallback_to_local`, otherwise the request fails (503).
- `core/topics.py`: `topic_name()`, shared by the API and the prompts.
- Tests (142 offline, plus 1 marked `ollama`):
  - Ollama client: body (think off), schema, retry, timeout, bad replies; OpenAI client: request and errors;
  - guard: exact allow-list dump; none of 10 secrets (name, student number, health detail, student_id, history, misconception text, KC IDs, mastery, item ID) reach the request or the cloud messages; `TypeError` for non-`CloudRequest`; a `model_construct` smuggling attempt is stripped; `render_cloud` signature;
  - generate: local, cloud, fallback (not configured / error), no-fallback, local failure;
  - API: Ollama down → generic 503; **an answer that repeats the student's name is not stored**.
- Manual check: `pytest -m ollama` passed against 192.168.2.25. Through the API as a logged-in student (scratch DB), qwen3.5:9b answered in about 2.4 s ("what do the two numbers mean") and about 3.2 s (a personal medication question). It referred the student to a clinician and said not to stop medication. Stored turns stayed withheld.

Files: `backend/app/llm/{__init__,base,ollama_client,openai_compat,cloud_guard,fake}.py`, `backend/app/prompts/{__init__,render}.py`, `backend/app/prompts/base_system.md`, `backend/app/pipeline/steps/{generate,record,privacy_filter}.py`, `backend/app/privacy/redact.py`, `backend/app/core/{topics,services,config}.py`, `backend/app/api/v1/topics.py`, `config.yaml`, `backend/tests/{conftest,test_api,test_llm_clients,test_cloud_guard,test_generate}.py`.

Decisions:
- **Until Step 4, answers are withheld from storage.** While the placeholder privacy filter withholds the question, `record` also stores the answer as `[withheld: not sanitized]`: nothing is known about which PII the local model might repeat. The student still sees the real answer. As a side effect, the local model's history consists of withheld placeholders until Step 4.
- `CloudClient` wraps a transport instead of extending `OpenAICompatClient`. This keeps the "CloudRequest only" check in one place and makes the cloud path testable with `FakeLLMClient`.
- The cloud prompt never includes history (`CloudRequest` has no field for it); `llm.cloud.history_turns` stays 0.
- A fallback adds the warning "The cloud model was unavailable, so the local model answered."
- The test `Api` helper installs `FakeLLMClient("Fake local answer.")` as the local model, so API tests never need Ollama.

Interface changes:
- `Services` gained `local_llm` and `cloud_llm`.
- Config: `llm.local.max_tokens` (default 1024). No schema changes.

Known gaps / TODO:
- **Prompt tuning (for Step 8 / E3).** For "150 over 95, should I stop my pills?" the model correctly refused, but it opened with "indicates high blood pressure (hypertension)". That reads like a diagnosis from one reading. The Step 8 `medical_safety` checker and the prompt wording should catch this ("a single reading cannot tell…").
- `OpenAICompatClient` sends `max_tokens`. Some newer OpenAI models require `max_completion_tokens`; check this when the cloud provider is chosen.
- One `httpx.AsyncClient` is created per call. That is fine at this scale; a shared client is an easy optimisation later.

How to try it:
```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m pytest -m ollama -q        # needs the GPU server
..\.venv\Scripts\python -m uvicorn app.main:app --reload   # log in, then POST /api/v1/ask → real qwen3.5:9b answer
```

## Step 4 — Privacy filter, anonymization, restore (2026-10-12)

Done:
- `privacy/analyzer.py`: Presidio `AnalyzerEngine`, built once per spaCy model (`privacy.spacy_model`), with Presidio's predefined English recognizers plus every recognizer registered in `pii_recognizers` (new registry).
  - Only `privacy.entities` are reported: PERSON, EMAIL_ADDRESS, PHONE_NUMBER, STUDENT_ID, GRADE, HEALTH_DETAIL.
  - **A missing model raises `PrivacyFilterUnavailable` at startup**, with the download command. Presidio itself would otherwise try to download the model, so `spacy.util.is_package` is checked first.
  - Post-processing:
    - an allow-list (`privacy.allow_list: [Abbas]`; titles such as Dr./Prof. and a trailing 's are ignored);
    - `clean_person()`, which fixes common English-NER mistakes: cut at the first digit ("Tom Becker 300477120"); drop spans without a capitalised name word ("FN=", "−") and spans containing an all-caps acronym ("DICOM metadata"); drop eponyms followed by a statistics, unit or disease noun ("Cohen's kappa", "Brier score", "Hounsfield units"). Chinese names skip these Latin-script rules;
    - overlap resolution: longer span first, then higher score.
- Recognizers in `privacy/recognizers/` (auto-registered):
  - `student_id`: 9 digits (0.6; context words such as "student", "id", 学号 raise it). The spaced form 3-3-3 counts only with context.
  - `grade`: "I got 58/100", "I got an A-", "my GPA dropped to 2.9", "I failed the midterm", "61 分". Letter grades are case-sensitive, so "I got a lot" does not match.
  - `health_detail`: a custom recognizer. A condition, symptom or medicine term counts only when it is
    - attributed to the student or a relative (subject + verb within the sentence, with "blocker" words such as about/question/studying/exam in between cancelling the match), or
    - owned ("my inhaler", "my therapist", "my pills"), or
    - a BP-style reading in a first-person sentence.
  - `zh_person`: Chinese self-introductions (我是/我叫 + 2–4 characters).
  - `phone_na`: North-American numbers **with separators** (0.6). Presidio's phone recognizer needs a context word and missed "Call me at …".
- `privacy/anonymizer.py`: `anonymize()` gives numbered placeholders per type (`<PERSON_1>`); the same value (case and whitespace-insensitive) always gets the same placeholder. `restore()` tolerates `<person_1>`, `< PERSON_1 >` and `[PERSON_1]`, and leaves unknown placeholders alone.
- Steps:
  - the real `privacy_filter` (stop): `is_sensitive = bool(entities)`, `cloud_safe = no entity in privacy.local_only_types`; the mapping goes only to the private context attribute; no logging of text;
  - the real `restore`: placeholders → values, then the mapping is cleared.
- The Step 3 "withheld" workaround is removed. The DB now stores sanitized questions and answers; `record` re-redacts known PII values in answers.
- `AskResponse.route_target` now reports the backend that actually answered (`ctx.llm.backend`), so a cloud→local fallback shows as `local` together with the warning.
- Tests (171 offline):
  - **ai-tutor-bench PII items: recall 28/28 = 1.00 on the covered types**, and every `non_pii_terms` entry survives. Out of scope for the MVP: ACADEMIC_STATUS, ACCOMMODATION, ADDRESS, AGE, FINANCIAL, MEDICAL_RECORD_NUMBER, PERSONAL_CIRCUMSTANCE.
  - 15 health cases (8 personal / 7 general, `data/synthetic/pii_health_cases.jsonl`) are all correct.
  - Also: 18 recognizer cases, overlap and anonymize/restore unit tests, the Done-when example at step level, the restore step, and refusal to start without the model.
- Manual check (uvicorn with `en_core_web_sm`; the production config without `en_core_web_lg` refused to start with the download hint):
  - "My student ID is 300418277 and I have asthma. Why does my inhaler make my hands shake?" → `cloud_safe=false`, routed local; the filter took 22 ms.
  - qwen3.5:9b answered with a clinician referral plus general information about beta-agonist tremor.
  - The DB holds only "My student ID is <STUDENT_ID_1> and I have <HEALTH_DETAIL_1>. Why does <HEALTH_DETAIL_2> make my hands shake?"; neither the student number nor "I have asthma" occurs anywhere in it.

Files: `backend/app/privacy/{analyzer,anonymizer,redact}.py`, `backend/app/privacy/recognizers/{student_id,grade,health_detail,zh_person,phone_na}.py`, `backend/app/pipeline/steps/{privacy_filter,restore,record}.py`, `backend/app/api/v1/ask.py`, `backend/app/core/{config,registry}.py`, `config.yaml`, `data/synthetic/pii_health_cases.jsonl`, `backend/tests/{conftest,test_privacy,test_api}.py`, `README.md`.

Decisions:
- **Tests always use `en_core_web_sm`.** `conftest.py` writes every test's config with `TEST_BASE` on top of `config.yaml`. Production keeps `en_core_web_lg`. The large model is **not installed on this machine yet** (about 400 MB; not downloaded without asking).
- `score_threshold` stays 0.5. Lowering it to 0.4 let Presidio's phone recognizer tag "0.300418277".
- HEALTH_DETAIL redacts the **term** ("asthma", "my inhaler"), not the whole clause, so the sanitized question keeps its structure.
- A first-person how-to such as "How do I use an inhaler?" counts as personal ("I use … inhaler") and stays local. This is deliberately conservative: a false positive only costs the cloud route; a false negative would leak.
- Repeated values reuse one placeholder; the first spelling is restored.
- The file-writing tool turns `一-鿿` into the literal characters; `zh_person.py` keeps them in a named `CJK` constant with a comment.

Interface changes:
- New registry `pii_recognizers` in `core/registry.py`. A new PII type is one file with `@pii_recognizers.register(...)`, plus its entity name in `privacy.entities`.
- Config: `privacy.allow_list` (new). No schema changes.

Known gaps / TODO:
- `record` replaces every occurrence of a detected value in the answer, so a stored answer also loses general uses of the word ("<HEALTH_DETAIL_1> inhalers contain…"). This is privacy-safe but lowers the quality of the history. A per-entity approach could replace only the student's own phrasing.
- Chinese coverage is limited to self-introductions, student numbers and "分" grades; there is no Chinese NER.
- The MVP does not detect addresses, MRNs, ages, financial or academic situations, or accommodations (all labelled in the bench set). The routing owner may want `local_only` heuristics for them.
- `en_core_web_lg` must be installed before running the server with the default config.
- In this run qwen3.5:9b took about 9.9 s for a long, safety-heavy answer (2.4–3.2 s in Step 3).

How to try it:
```powershell
.venv\Scripts\python -m spacy download en_core_web_lg      # once, ~400 MB (or use a config copy with en_core_web_sm)
cd backend
..\.venv\Scripts\python -m pytest -q
..\.venv\Scripts\python -m pytest tests/test_privacy.py -s -q   # prints the bench recall
```

## Step 5 — Domain content: format, loader, High Blood Pressure draft (2026-10-12)

Done:
- `backend/app/learner/content.py`:
  - Pydantic models `KC`, `Option`, `Item`, `Misconception`, `TopicContent`, all with `extra="forbid"`. An option may be written as a plain string or as `{text, misconception}`.
  - The loader reads `content/topics/<topic>/{kcs,items,misconceptions}.yaml`.
  - `validate()` collects **every** problem with a readable message:
    - duplicate IDs (across KCs, items and misconceptions);
    - unknown prerequisites; prerequisite cycles (reported as a path, e.g. `A.1 -> A.2 -> A.1`);
    - an item that does not have exactly A–D, or whose answer is not an option, or whose correct answer is tagged as a misconception;
    - an unknown misconception tag; an item or misconception that refers to an unknown KC;
    - a topic without KCs; unknown YAML fields.
- `ContentStore`: `topics()`, `topic()`, `kcs()`, `kc()`, `topic_of()`, `prerequisites()`, `items(kc_id, reviewed_only=None)`, `item()`, `reviewed_item_count()`, `misconception()`, `misconceptions(kc_id)`.
  - `items()` serves unreviewed items only when `content.serve_unreviewed` is true.
  - `Item.public()` → `CheckItemPublic`, without the key, explanation or misconception tags.
- `Services.content` is built at startup, so **invalid content stops the app**.
- **The High Blood Pressure draft** (every file starts with `# DRAFT — generated, not medically reviewed…`, and every `reviewed_by` is null):
  - 6 KCs with definitions and prerequisites, as in design §4.1.
  - 24 MCQs, 4 per KC. Each KC has basic, intermediate and advanced items. Every one of the 12 misconceptions (HBP.MC1–MC12) is the tag of at least one distractor.
  - 12 misconceptions with corrections.
  - No drug names or doses, no numeric thresholds. The guideline is "TBD", and one reading example ("120 over 80") was removed so that it cannot be read as a threshold.
- **Option positions were shuffled.** The first draft had the correct answer at A in 23 of 24 items, so a student could guess. A deterministic shuffle seeded by the item ID moved them to A 4 / B 5 / C 7 / D 8; stems, option texts, tags and explanations were verified unchanged. A test now fails if any letter holds more than 40% of a topic's answers.
- Skeletons for type2_diabetes, asthma, migraine and pneumonia: one placeholder KC each (T2D.1, AST.1, MIG.1, PNA.1) and empty items and misconceptions.
- `scripts/export_content_review.py <topic> | --all` writes `docs/review/<topic>_review.csv` (UTF-8 with BOM for Excel): one row per topic, KC, item and misconception, with options, answer, explanation or correction, distractor tags, `reviewed_by` and an empty `reviewer_comment` column. **`docs/review/high_blood_pressure_review.csv` is generated and ready to send to Dr. Abbas.**
- `GET /api/v1/topics` now returns the topic names from the content, plus `kc_count` and `reviewed_item_count`.
- CI also lints `scripts/`.
- Tests (193 offline):
  - all topics load, and the HBP draft has the expected shape; answer positions are spread;
  - authoring rules: DRAFT header, no dose patterns, no BP readings;
  - reviewed-only serving; the public item hides the key; lookups;
  - **each of the 10 validation rules** has its own broken fixture, and `find_cycle` has its own tests;
  - invalid content stops startup; the topics endpoint counts; the review export.

Files: `backend/app/learner/content.py`, `backend/app/core/services.py`, `backend/app/api/v1/topics.py`, `content/topics/*/{kcs,items,misconceptions}.yaml`, `content/topics/README.md`, `scripts/export_content_review.py`, `docs/review/high_blood_pressure_review.csv`, `backend/tests/test_content.py`, `.github/workflows/ci.yml`.

Decisions:
- Items use `level` (basic / intermediate / advanced, like chunks); KCs use `difficulty`.
- An item ID is `<KC>-q<n>` (e.g. `HBP.6-q1`). The Step 8 profile-leak checker relies on this pattern.
- Prerequisites may only point within the same topic.
- The topic display name comes from `kcs.yaml` (`name`); `core/topics.py` remains the fallback.
- Item `explanation` texts are part of the review as well: Step 7 shows them after a check answer.

Interface changes:
- `Services` gained `content`. No schema changes.

Known gaps / TODO:
- **Nothing is reviewed yet.** With the default `content.serve_unreviewed: false`, the app serves no check questions. Development and the MVP demo need `serve_unreviewed: true` until Dr. Abbas approves items (then set `reviewed_by`).
- The other four topics are placeholders (Beta: 4–6 KCs each, items, misconceptions).
- Siyun's RAG chunks must use these KC IDs (`HBP.1` … `HBP.6`) in `kc_ids`.

How to try it:
```powershell
.venv\Scripts\python scripts\export_content_review.py high_blood_pressure   # -> docs\review\high_blood_pressure_review.csv
cd backend
..\.venv\Scripts\python -m pytest tests/test_content.py -q
```

## Step 6 — Learner model core (2026-10-12)

Done:
- `learner/knowledge/bkt_math.py` (pure functions): `posterior`, `learn`, `weak_update`, `level_with_hysteresis`.
  - Probabilities are clamped to [1e-4, 1−1e-4], so later evidence can always move them.
  - Hysteresis moves the band boundaries by ±h against the direction of change. For example, from `basic` the level rises only above 0.45; from `intermediate` it falls only below 0.35.
- Tables in `storage/models.py`: `learner_kc_state`, `learner_topic_level`, `learner_preference` (with implicit streak counters), `evidence_log` (IDs, flags, weight; **no free-text column**) and `consent`. All are keyed by `student_id`, so the Step 2b account purge covers them automatically; a test checks this.
- `learner/repository.py`: all learner DB access. `reset()` clears state, topic level, preferences and evidence, and keeps consent.
- Knowledge models (`learner.knowledge`):
  - A shared `BaseKnowledgeModel` handles the prior for unseen KCs, hysteresis, validation (unknown KC; graded evidence without `correct`), evidence logging and persistence.
  - **`bkt`**:
    - strong → posterior + learning step;
    - diagnostic → posterior only;
    - weak → `weak_update` (likelihoods 0.30/0.60), no learning step.
    - Parameters come from `bkt_defaults`, overridden per **item level** by the new `learner.bkt_by_level`.
  - **`rule`**: `(correct+1)/(n+2)` over the last N graded answers (strong + diagnostic), minus `weak_penalty` for each weak signal since the last graded answer, clipped to [0, 1]. It is recomputed from the evidence log.
  - `n_obs` counts graded answers only. Weak evidence is logged with weight = likelihood ratio (2.0).
- Preference model `simple`: explicit signals apply at once (source onboarding or feedback). Implicit signals need a streak of 3 consistent signals, and an explicit choice resets the streak. `PreferenceSignal(dimension, value, explicit, source)` validates its values.
- `learner/recommender.py`: candidates are KCs whose prerequisites are all ≥ 0.70 and whose own mastery is < 0.90. They are ordered by lowest p, then fewest observations. The current topic is searched first, and other topics only when it has no candidate.
- `learner/facade.py` (`LearnerModel`, built into `Services.learner`):
  - `context()`, `observe()`, `observe_request()` (at most one weak update per KC per request), `update_preferences()`, `set_consent()` (withdrawing consent resets the profile), `has_consent()`, `reset()`.
  - **No consent → `LearnerContext(personalized=False)`, and nothing is read or written.**
  - Focus level: the lowest level among the question's KCs when they are known; otherwise (temporary, until Step 11) the hysteresis level of the topic's mean mastery, stored in `learner_topic_level`.
- The real `learner_context` step (skip on error). `/ask` now returns `kc_level` and `next_kc` for students who consented, and the local prompt carries their level.
- Tests: 229 offline (36 new). They cover:
  - the math against hand-computed values;
  - hysteresis at 0.40 ± 0.03 and at 0.70;
  - both models move up and down, and weak evidence moves less than strong (both models);
  - no learning step for diagnostics; per-level overrides; the exact rule formula; invalid evidence;
  - evidence columns; the weak cap; consent, withdrawal and reset; the account purge;
  - preferences (explicit, implicit streak, reset of the streak);
  - recommender order, prerequisites and topic switching; focus level by KCs and by topic mean;
  - the step, and the API with and without consent.
- **Swap check (Done when): the whole suite passes with `TEST_LEARNER_KNOWLEDGE=rule` (229/229).** CI now runs the suite twice, once with BKT and once with the rule model.

Files: `backend/app/learner/{facade,recommender,repository}.py`, `backend/app/learner/knowledge/{__init__,interface,bkt,rule,bkt_math}.py`, `backend/app/learner/preference/{__init__,interface,simple}.py`, `backend/app/pipeline/steps/learner_context.py`, `backend/app/storage/models.py`, `backend/app/core/{config,services}.py`, `config.yaml`, `backend/tests/{conftest,test_bkt_math,test_learner}.py`, `.github/workflows/ci.yml`.

Decisions:
- **The recommender restricts itself to the current topic** and moves to another topic only when nothing in the current one qualifies. The design says "current topic breaks ties", but the four placeholder topics all sit at the prior (0.20). With pure tie-breaking, a student who made any progress in High Blood Pressure would be sent to Asthma.
- **The design's "weakest prerequisite" fallback was removed as unreachable.** In a DAG, following unready prerequisites always ends at a KC whose prerequisites are ready, and that KC is a candidate. So `None` means everything is mastered.
- In the rule model, a KC without graded answers starts at the prior (0.20), not at (0+1)/(0+2) = 0.5, so that both models agree on new students.
- Diagnostic answers count as graded answers in the rule model.
- `PreferenceSignal` lives in `learner/preference/interface.py`, not in `core/schemas.py`, because it is internal.
- `context()` writes `learner_topic_level` only when the level changes.
- `TEST_LEARNER_KNOWLEDGE` (environment variable) selects the knowledge model for the whole test suite.

Interface changes:
- `Services` gained `learner`.
- Config: `learner.bkt_by_level` (new, default `{}`).
- New tables: `learner_kc_state`, `learner_topic_level`, `learner_preference`, `evidence_log`, `consent`. No schema changes.

Known gaps / TODO:
- There is no API for consent or preferences yet: until the Step 7 onboarding, every student is unpersonalized in the running app (`kc_level: null`).
- `LearnerContext.misconceptions` stays empty until Step 12, although the evidence log already records misconception IDs.
- The focus level uses the topic mean until the understand step (Step 11) provides KC IDs.
- The full test suite now takes about 45 s, mostly argon2 hashing and app startups. It could be parallelised later.

How to try it:
```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/test_learner.py tests/test_bkt_math.py -q
$env:TEST_LEARNER_KNOWLEDGE="rule"; ..\.venv\Scripts\python -m pytest -q; Remove-Item Env:TEST_LEARNER_KNOWLEDGE
```

## Step 7 — Adaptive flow: onboarding, check questions, level-aware prompts (2026-10-12)

Done:
- Prompt partials: `prompts/levels/{basic,intermediate,advanced}.md` and `prompts/style/{example_first,concept_first}.{concise,detailed}.md`.
  - `system_prompt(level, sequencing, detail)` = base (safety) + level + style.
  - `render_local` uses the learner's level and preferences, and only the base prompt when unpersonalized. `render_cloud` uses the `CloudLabels`.
  - The safety text exists only in `base_system.md`. Tests check that all 12 combinations start with the unchanged base block, and that no partial mentions diagnosis, doses, medication, rules or overrides.
- `learner/checks.py`:
  - `grade()` uses the key only; a wrong choice reports its distractor's misconception ID.
  - `diagnostic_items()`: one item per KC, prerequisites first (`topological()`), preferring the KC's basic item, at most 10.
  - `choose_item()`: unseen items first, never an item answered in the last 24 h, then the item whose level matches the KC's level; None when every item was used recently.
- Facade: `apply_diagnostic()` grades onboarding answers in prerequisite order. **A KC whose prerequisite was missed (or itself skipped) is not assessed and keeps its prior (transitively)**. `band()` gives basic / intermediate / advanced / mastered (≥ 0.90).
- API, every route for logged-in students only:
  - `GET /api/v1/onboarding?topic=` returns the consent text, 2 preference questions and the public diagnostic items (no key).
  - `POST /api/v1/onboarding` takes `{topic, consent, preferences, answers}`, and every part is optional. Without consent it stores nothing and returns `personalized: false`.
  - `POST /api/v1/check` takes `{session_id, item_id, choice}`. It grades by key and applies **strong** evidence, with the item ID and the distractor's misconception ID in the evidence log. It returns `{correct, correct_choice, explanation, kc_id, kc_level, kc_band, next_kc}`. An unknown or unservable (unreviewed) item → 404. Without consent it grades but records nothing.
  - `GET /api/v1/learner/me[?topic=]` returns the bands per KC and the preferences, **never probabilities**.
  - `DELETE /api/v1/learner/me` resets the learning profile; consent and the account stay.
  - `POST /api/v1/learner/me/preferences` takes `{action: more_detail | shorter | example_first | concept_first}`; without consent → 409.
- The real `attach_check` step (skip). KC: the question's first KC (Step 11), else the recommended next KC **of the same topic**, else the topic's lowest-mastery KC (the first KC when unpersonalized). `/ask` now returns `check_item`.
- **Fixed a latent import cycle.** Importing `app.prompts` before `app.llm` failed, because `app/llm/__init__.py` imported `cloud_guard`, which imports `app.prompts`. `build_llm_clients` moved to `app/llm/factory.py`, and the package `__init__` imports nothing.
- Tests: **260 offline, passing with both BKT and the rule model**. They cover:
  - prompt partials (12 combinations, content rules, local and cloud use);
  - grading; the diagnostic order; item choice (level match, no repeat within 24 h, return after a day);
  - onboarding: info, no consent, the transitive skip, topic validation;
  - check: evidence and misconception, no consent, errors, unreviewed items not served;
  - learner/me: bands only, reset, feedback, 401;
  - **the end-to-end flow** onboarding → ask (check attached, intermediate partial) → wrong answers until every KC is basic (written to hold for both models) → the next ask uses the basic partial.
- Manual check (uvicorn, `en_core_web_sm`, `serve_unreviewed: true`, real qwen3.5:9b):
  1. onboarding with 6 correct diagnostic answers → all KCs intermediate;
  2. "Why does eating less salt help?" → answered in 8.2 s in the example-first, concise style ("think of your blood vessels like garden hoses…"), with check item HBP.1-q3;
  3. a wrong answer → key C, explanation shown, **HBP.1 band intermediate → basic in `/learner/me`**;
  4. the next ask got another HBP.1 item (q2).

Files: `backend/app/prompts/{render,__init__}.py`, `backend/app/prompts/levels/*.md`, `backend/app/prompts/style/*.md`, `backend/app/learner/{checks,facade,repository}.py`, `backend/app/pipeline/steps/attach_check.py`, `backend/app/api/v1/{onboarding,check,learner_me,__init__}.py`, `backend/app/llm/{__init__,factory}.py`, `backend/app/core/services.py`, `backend/tests/{test_prompt_partials,test_adaptive_flow}.py`.

Decisions:
- The level partials keep the first line "Teaching level for this student: <level>." (the Step 3 one-liner), so earlier tests and logs stay comparable.
- An unpersonalized local prompt is the base only. A cloud prompt always has partials, because a `CloudRequest` always carries labels (defaults for unpersonalized students).
- The diagnostic prefers basic items: it places students and should not test details.
- A check question that was shown but not answered can be offered again. Only answered items count for the 24 h rule.
- `/check` accepts only items the content store may serve, so students cannot answer unreviewed items in production.

Interface changes:
- `app.llm` package: import `build_llm_clients` from `app.llm.factory` (previously from `app.llm`).
- New API routes as listed above. No schema changes.

Known gaps / TODO:
- **Until the understand step (Step 11) tags questions with KCs, the focus level is the topic mean**, so one wrong answer on HBP.1 lowers HBP.1's band and its next check item, but not the level of the next free answer (it stayed intermediate in the manual run). Step 11 fixes this by using the question's KC.
- Content quality, for E3 and the review: one generated answer used a loose analogy ("salt is like pouring extra weight on the hose"). The level and style partials could ask for medically accurate analogies only.
- Content is unreviewed, so the demo needs `content.serve_unreviewed: true` (Step 10 should document this in the demo config).

How to try it (development config: small spaCy model, unreviewed content served):
```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/test_adaptive_flow.py tests/test_prompt_partials.py -q
# run uvicorn with APP_CONFIG pointing at a config copy with en_core_web_sm and serve_unreviewed: true, then:
# log in → GET /api/v1/onboarding?topic=high_blood_pressure → POST /api/v1/onboarding → POST /api/v1/ask
# → POST /api/v1/check → GET /api/v1/learner/me
```

## Step 8 — Verification, end-to-end hardening (2026-10-12)

Done:
- Checkers in `verify/checkers/`, registered and selected by `verify.checkers`:
  - **`medical_safety`** (rule-based; failures are reported as short labels and never quote the answer).
    - **fail** on: a dosing instruction (an amount with a unit and a dosing verb in the same sentence); advice to start, stop or change a medicine ("you can stop…", "it is fine to skip your inhaler…"; negations such as "you should not stop" are excluded); a diagnosis of the student ("you have hypertension", unless it is conditional: "if you have…"); a diagnosis from the student's own reading ("your reading shows…", "a reading of 150/95 indicates high blood pressure"). The last rule closes the Step 3 gap.
    - **warn** when the question had a HEALTH_DETAIL (or, from Step 11, `question_type == self_management`) and the answer does not refer to a clinician.
  - **`grounding`**: a sentence counts as supported when ≥ 20% of its content words appear in one passage; if fewer than 50% of the sentences (with ≥ 4 content words) are supported → warn. Without passages → pass with "no material".
  - **`pii_leak`**: runs the analyzer again on the **sanitized question** of `ctx.cloud_request` (placeholders blanked).
  - **`profile_leak`**: fails on the student_id anywhere in the request, a check-item ID (`X.n-qn`), or a catalog misconception statement in the question that the student did not write.
- `verify/leaks.py`: the detection functions plus `CloudLeakGuard`. **The generate step now runs the same checks BEFORE sending**: a finding blocks the request, logs the kinds as an error, adds a warning, and lets the local model answer. `ctx.cloud_request` is set only when something was actually sent.
- The real `verify` step (warn):
  - It runs all checkers; a crashing checker becomes `warn: checker error`.
  - medical_safety **fail** → regenerate once on the same route with `safety_retry=True`, then restore placeholders and re-check. `safety_retry` adds the fixed `SAFETY_RETRY_INSTRUCTION` constant; for the cloud it is only a boolean on `CloudClient.complete`, so no free text can travel.
  - Still failing → the safe fallback message (+ "course material listed below" when there are passages) and a warning; the sources are still returned.
  - medical_safety **warn** → a referral sentence is appended to the answer.
  - grounding warn → a warning. Leak failures → a warning and an error log (kinds only).
- **The PII mapping lifetime changed.** `restore` no longer clears it, because `verify` may need it for a regenerated cloud answer. `record` clears it as the last step, and `/ask` also clears it after the pipeline (including after errors). The mapping still never leaves the in-memory context.
- `CloudClient.complete(req, *, safety_retry=False)` and `render_cloud(req, *, safety_retry=False)`. The signature test now allows only keyword-only boolean switches besides the `CloudRequest`.
- `ContentStore.all_misconceptions()`.
- Tests: **287 offline, passing with both BKT and the rule model**. The new ones cover:
  - 8 failing and 8 passing medical-safety sentences; the referral warning;
  - grounding (no material / supported / off-topic);
  - pii_leak and profile_leak (including "the student wrote it themselves");
  - regenerate-once; fallback after two failures; the appended referral; a broken checker and grounding warnings;
  - the pipeline and failure-policy table of design §7.1;
  - the pre-send guard blocking a request whose "sanitized" text still contains a name;
  - **the full privacy E2E**: a student with consent, preferences, a diagnostic and a misconception, asking with a name and a student number, forced to the cloud (stub score 1.0, fake cloud transport). It checks route = cloud, the answer restored to "Hello Alice Tremblay!", pii_leak and profile_leak pass, the cloud saw only placeholders and labels (no name, number, student_id, item ID, misconception statement or preference words), and the DB holds only the sanitized answer. It runs in the default suite, so it is in CI.
- Manual check with the real qwen3.5:9b (in-process, dev config):
  - "My reading today was 150 over 95. Should I stop taking my pills?" → the model said "higher than the target range", not a diagnosis, advised against stopping and referred to a doctor or pharmacist. medical_safety passed.
  - The checkers took about 0.1 ms per request.

Files: `backend/app/verify/leaks.py`, `backend/app/verify/checkers/{medical_safety,grounding,leaks}.py`, `backend/app/pipeline/steps/{verify,generate,restore,record}.py`, `backend/app/llm/cloud_guard.py`, `backend/app/prompts/render.py`, `backend/app/learner/content.py`, `backend/app/api/v1/ask.py`, `backend/tests/{test_verification,test_cloud_guard,test_privacy}.py`.

Decisions:
- **pii_leak scans the sanitized question only, not the passages.** Passages are course material, which legitimately contains names (authors, eponyms); scanning them would make the check fail on clean requests. Likewise, profile_leak checks misconception statements only in the question, and only if the student did not type them.
- **The pre-send block always falls back to local**, even if `fallback_to_local` is false: privacy comes before availability.
- The "diagnosis from a reading" rule needs "your/this … reading" or an actual BP-style number in the sentence, so general teaching sentences ("several readings over time are needed before hypertension is diagnosed") pass.
- Regeneration uses the same route; the cloud gets the same `CloudRequest` plus the fixed retry flag.
- Design §7.1 says `restore` "discards the mapping". It now does so in `record` and in the API (documented above).

Interface changes:
- `CloudClient.complete(req, *, safety_retry=False)`, `render_cloud(req, *, safety_retry=False)`, `render_local(ctx, *, safety_retry=False)`.
- `GenerateStep.produce(ctx, *, safety_retry=False)` is reused by `verify`. No schema changes.

Known gaps / TODO:
- The safety rules are English-only regex. Chinese answers are only covered by the prompt.
- Grounding is lexical; paraphrased support can be under-counted (it only warns). An embedding-based check could replace it later (Siyun's embeddings).
- In the manual run the model wrote "[No course material was provided for this topic.]" in brackets. The prompt wording of the material block could be refined (E3).

How to try it:
```powershell
cd backend
..\.venv\Scripts\python -m pytest tests/test_verification.py -q
..\.venv\Scripts\python -m pytest tests/test_verification.py -q -k privacy_end_to_end
```

## Step 9 — Frontend MVP (2026-10-12)

Done:
- `frontend/`: Vite 5 + React 18 + TypeScript (strict), Tailwind 3, React Router 6, TanStack Query 5, Vitest 2 + Testing Library.
  - `npm run gen:api` runs openapi-typescript on `openapi.json` (written by `python -m app.export_openapi`) and produces `src/api/schema.d.ts`. Both files are committed, so the frontend builds without the backend.
- API layer:
  - `src/api/client.ts`: a typed `request()` with `credentials: "include"` that maps FastAPI `detail` errors to `ApiError(status, message)`.
  - `src/api/endpoints.ts`: one function per endpoint, using the generated types.
- **Identity**: only the httpOnly session cookie; nothing in `localStorage`.
  - `useMe()` (`GET /auth/me`; 401 → null) drives a route guard: not logged in → `/login`; must change password → `/change-password`; wrong role → home of the role (students `/chat`, instructor `/admin`).
  - Logout clears the query cache.
- Pages:
  - `/login`.
  - `/change-password` (forced; a student then goes to `/start`).
  - `/start` (onboarding): topic picker; consent text and checkbox; 2 preference questions; the diagnostic MCQs; "Skip" per section and "Skip all"; a result screen with the band per KC.
  - `/chat`: topic picker, per-topic conversations (`session_id` kept per topic), tutor messages with sources, warnings, "Suggested next" and a check-question card; a level badge; presentation-feedback buttons (shown when personalized); a banner linking to `/start` when not personalized.
  - `/me` ("What I know"): bands per KC for every topic, the current preferences, "Reset my learning data" with an inline confirmation.
  - `/admin`: a placeholder until Step 13.
  - A fixed footer: "For learning only — not medical advice…".
- `CheckCard`: options A–D in order, never an answer key. "Check answer" is enabled only after a choice. It posts `{item_id, choice, session_id}`, then shows correct / not quite (with the key), the explanation, the KC band and the suggested next KC, and locks the options.
- Accessibility: labelled inputs; fieldset and legend for option groups; `role="status"` / `role="alert"` for results and errors; `aria-live` on the conversation; visible focus rings; bands carry text, not only colour.
- `ErrorBoundary` around every page: a crash shows a message instead of a blank page.
- Vitest (`src/test/CheckCard.test.tsx`), 2 tests: options render in order without a key, and the button is disabled until a choice; the chosen option is posted with credentials and the server's verdict is shown.
- **The CI frontend job is enabled**: `npm ci`, `npm run build`, `npm test` on Node 20.
- **Manual check (Done when), in the desktop app's browser pane** (backend on :8000 with dev config and real qwen3.5:9b; Vite on :5173; throw-away student in a scratch DB):
  1. Login with the temporary password → forced to `/change-password` → `/start`.
  2. Onboarding: consent, "example first" and "short", 6 answers with Q2 wrong → result HBP.1/3/5 intermediate; HBP.2 basic (missed); **HBP.4 and HBP.6 basic (skipped: they depend on HBP.2)**.
  3. Chat: "Why is high blood pressure dangerous if I feel fine?" → an example-first, short answer, the badge "Explained at level: basic", "Suggested next: What blood pressure numbers mean", and check question HBP.1-q3.
  4. Wrong answer B → "Not quite. The answer is C." + explanation + "This topic part: basic".
  5. **What I know: "What blood pressure numbers mean" went intermediate → basic**, with preferences "Example first, short answers".
- **Bug found and fixed during the manual check**: the chat page went blank. `useEffect(() => ref.scrollIntoView(...))` returned the call's result, and in this browser `scrollIntoView` returns a Promise, which React then called as a cleanup function. The effect now uses a block body, and the ErrorBoundary was added so such a crash cannot blank the page again.

Files: `frontend/{package.json,package-lock.json,vite.config.ts,tsconfig.json,tailwind.config.js,postcss.config.js,index.html,openapi.json,README.md}`, `frontend/src/**` (`api/`, `components/{Layout,Band,CheckCard,TopicPicker,ErrorBoundary}.tsx`, `pages/{Login,ChangePassword,Onboarding,Chat,WhatIKnow,Admin}.tsx`, `auth.ts`, `App.tsx`, `main.tsx`, `index.css`, `test/`), `.github/workflows/ci.yml`, `.gitignore`.

Decisions:
- **The API base defaults to "" (same origin), not `/api`.** The schema's paths already start with `/api/v1`; the Vite dev proxy forwards `/api` to `localhost:8000`, and in Step 10 nginx does the same. `VITE_API_URL` is only for a cross-origin API.
- Conversations are kept in page state per topic (not persisted in the browser); the server keeps the sanitized history.
- Presentation-feedback buttons appear only for personalized students (the API answers 409 otherwise).
- The diagnostic radio groups use the item ID as the group name; only the server knows the keys.

Interface changes: none in the backend.

Known gaps / TODO:
- The instructor UI (students, class summary, settings, logs) is Step 13. Until then, use `/docs` or the API.
- Chat history is not reloaded after a page refresh (`GET /sessions/{id}` exists; the UI could use it later).
- React Router prints v7 "future flag" warnings in the console (harmless).
- Interaction note for agents: the browser pane needs the desktop app window to be visible for clicks; when it was minimized, `form_input` and `get_page_text` still worked.

How to try it:
```powershell
# terminal 1 (backend; dev config copy with en_core_web_sm and serve_unreviewed: true)
cd backend; $env:APP_CONFIG="<path to dev config>"; ..\.venv\Scripts\python -m uvicorn app.main:app --reload
# terminal 2
cd frontend; npm install; npm run dev     # open http://localhost:5173
npm test; npm run build
```

## Step 10 — Packaging and MVP demo (2026-10-12)

Done:
- **Nested environment overrides.** `Settings` now has `env_nested_delimiter="__"`, so `SECTION__FIELD=value` overrides one `config.yaml` value (deep-merged; sibling values stay), e.g. `CONTENT__SERVE_UNREVIEWED=true`, `PRIVACY__SPACY_MODEL=…`, `ROUTING__STUB_SCORE=1.0`. Type-enforced invariants still hold (`LLM__LOCAL__THINK=true` is rejected; tested). This replaces the copied dev config files used in Steps 4–9.
- `backend/Dockerfile` (build context: the repository root): python:3.12-slim.
  - The repository layout is kept (`/app/backend`, `/app/content`, `/app/config.yaml`), so `REPO_ROOT` and the content directory resolve.
  - The package is installed **editable** from `/app/backend`. Dependencies and the spaCy model are installed in their own cached layer.
  - Build arg `SPACY_MODEL` (default `en_core_web_lg`) sets `PRIVACY__SPACY_MODEL` as well, so the image and the privacy filter always agree.
  - The container runs as a non-root user, with a `HEALTHCHECK` on `/api/v1/health` and `DATABASE_URL=sqlite:////app/data/app.db`.
- `frontend/Dockerfile`: node:20-slim build → nginx:1.27-alpine. `frontend/nginx.conf`:
  - serves the SPA (`try_files … /index.html`) and proxies `/api/` to `api:8000` with 180 s timeouts (for slow local answers);
  - long cache for the hashed `/assets/`;
  - `nosniff` and a same-origin referrer policy, repeated per location because a location's `add_header` replaces the server-level ones.
- `docker-compose.yml`:
  - `api`: `env_file: .env` (optional) and the named volume `tutor-data`.
  - `web`: `${WEB_PORT:-8080}:80`; waits for `api` to become healthy.
  - Ollama stays external (`OLLAMA_URL`). `.dockerignore` files keep `.venv`, `node_modules`, `data`, `eval`, `docs` and `.env` out of the build contexts.
- `scripts/demo_seed.py` works only through the public API. As the instructor it creates (or, when they exist, reactivates and resets) three demo students; then, as each student, it sets the demo password, resets the profile and completes onboarding:
  - `demo.novice` misses the first diagnostic question → all basic (the dependents are not assessed);
  - `demo.intermediate` answers the diagnostic correctly → all intermediate;
  - `demo.advanced` answers the diagnostic plus one correct check answer per KC → all advanced.

  Answer keys are read from `content/` only to simulate students. The script fails with clear messages when the server is unreachable, when the instructor still has to change the password, or when unreviewed content is not served. It can be re-run.
- `docs/DEMO.md`: preparation (`.env`, compose, first instructor login, seeding, warming up the model) and a 5-minute table of what to do and what to say:
  1. novice: basic, example first, check question;
  2. a wrong and then a right check answer → the band changes;
  3. advanced: same question, advanced and concept-first;
  4. a privacy question (name, student number, health detail) → local;
  5. what was stored (a `docker compose exec` one-liner);
  6. local vs cloud via `ROUTING__STUB_SCORE`.
- `docs/MVP_CHECKLIST.md`: the 16 MVP deliverables of design §12 with their code, tests and status. 12 are ✅. 4 are 🟡 because of open items outside the code: the cloud provider, the content review, and the real router and RAG from teammates.
- README: Docker quick start, `SECTION__FIELD` overrides, and development mode with two terminals. `.env.example`: Compose variables and override examples (with the warning to use `SPACY_MODEL`, not `PRIVACY__SPACY_MODEL`, with Docker).

Verification (Done when):
- `docker compose up --build` built and started both images (test project `tutortest`, port 8081, `SPACY_MODEL=en_core_web_sm`, demo overrides in a scratch override file). `api` became healthy and `web` waited for it. Image sizes: api 815 MB (with the small spaCy model), web 74 MB.
- **One port serves everything**:
  - `/api/v1/health` through nginx → ok, **Ollama reachable from the container, `qwen3.5:9b` available**;
  - `/`, `/login`, `/chat`, `/me` → 200 text/html (SPA fallback);
  - `X-Content-Type-Options` and `Referrer-Policy` present.
- The instructor's first login and password change worked. **`demo_seed.py` against the Docker deployment** gave novice: all basic (5 not assessed), intermediate: all intermediate, advanced: all advanced. Re-running works (also checked against uvicorn).
- Real model through Docker: "My name is Alice Tremblay, student 300418277, and I have asthma…" → `route=local`, all four checks passed, 1.8 s. The `docker compose exec` command from DEMO.md showed only `My name is <PERSON_1>, student <STUDENT_ID_1>, and I have <HEALTH_DETAIL_1>…`, and none of the raw values occur anywhere in the DB.
- Before Docker, against uvicorn with the real model, the same question showed the contrast for the demo: demo.novice → basic, example first, short (7.9 s, basic check item); demo.advanced → advanced, concept first, precise terms (4.0 s, advanced check item).
- The test stack was removed afterwards (`down -v --rmi local`); the build cache was kept. Backend: 289 tests pass (including 2 new tests for the nested overrides).

Files: `backend/Dockerfile`, `frontend/{Dockerfile,nginx.conf,.dockerignore}`, `docker-compose.yml`, `.dockerignore`, `scripts/demo_seed.py`, `docs/{DEMO,MVP_CHECKLIST}.md`, `README.md`, `.env.example`, `backend/app/core/config.py`, `backend/tests/test_config.py`.

Decisions:
- The SQLite database lives in a **named volume**, not a bind mount, so file permissions work the same on Windows, macOS and Linux hosts. `docker compose down -v` deletes it.
- The demo student password is a fixed demo value (`demo-student-2026`, overridable with `DEMO_STUDENT_PASSWORD`), written down in `docs/DEMO.md`. It is only for demo accounts.
- The image keeps the default `en_core_web_lg`. The verification build used `SPACY_MODEL=en_core_web_sm`, so that the 400 MB model was not downloaded without asking.
- `api` gets `DATABASE_URL` from `environment:`, which takes precedence over `.env`, so a developer's local `DATABASE_URL` cannot point the container elsewhere.

Interface changes:
- Settings: `SECTION__FIELD` environment variables override config values. No API or schema changes.

Known gaps / TODO:
- The default `en_core_web_lg` image has not been built on this machine yet; only the `en_core_web_sm` variant was.
- No TLS in the compose setup. Behind HTTPS, set `AUTH__COOKIE_SECURE=true`.
- Alembic migrations are still missing; recreate the volume after schema changes until they exist.

How to try it:
```powershell
Copy-Item .env.example .env   # OLLAMA_URL, INSTRUCTOR_USERNAME, INSTRUCTOR_INITIAL_PASSWORD, CONTENT__SERVE_UNREVIEWED=true
docker compose up --build -d  # http://localhost:8080
# log in as the instructor once and change the password, then:
$env:DEMO_INSTRUCTOR_PASSWORD="<new password>"; .venv\Scripts\python scripts\demo_seed.py
```


## Step 11 — Understand step and weak evidence (+ E1 harness) — 2026-10-12

Branch `feature/understand` (stacked on `feature/packaging`).

What was built:
- `app/learner/understand.py`: prompt, JSON schema and parser for the `understand` step.
  - The schema enums are the topic's own KC IDs and catalog misconception IDs (`maxItems` 2 / 3), so the model can only choose from the catalog.
  - The prompt lists KC id + name + definition and the catalog statements, followed by 4 few-shot examples (HBP only): confusion, a stated misconception, a *question* about a misconception (→ none), and off-topic.
  - The wire format uses one-letter keys (`k`, `t`, `c`, `m`). The reply is generated token by token, so short keys cut the latency of the step roughly in half.
  - `parse` rejects bad JSON and unknown IDs (`ValueError` → the step is skipped), removes duplicates and keeps at most 2 KCs.
  - **Misconception gate:** misconception IDs are kept only when the question type is `check_my_answer` or `self_management` **and** the student states a belief. A plain question ("Does…?", "Is…?", "Why…?") without an assertion marker (", right?", "isn't it", "I think", "so my…") does not count. This raised precision from 50% to 88% on qwen3.5:9b.
- The `understand` step (`on_error: skip`) uses `services.understand_llm`, built by `llm/factory.py`: an `OllamaClient` with `llm.understand.model`, temperature 0, the same `num_ctx` as the local model (no reload) and the `llm.understand.timeout_s` timeout.
- **Pipeline reorder:** `[privacy_filter, understand, learner_context, retrieve, …]`. `learner_context` needs the question's KC IDs for the focus level (lowest level among them), so `understand` must run first. `retrieve` gets `kc_ids` and the level, and `attach_check` uses the first understood KC. Design §7.1 is updated to match.
- The `update_learner` post-response step:
  - weak evidence (design §5.1), only when `learner.weak_evidence` is true: `confusion` → one weak update per understood KC; a stated misconception → one weak update on its KC. The facade caps this at one weak update per KC per request.
  - implicit preference hints from the student's wording ("example", "the idea", "step by step", "briefly", …). They go through the simple preference model, so a preference changes only after 3 consistent hints. Both parts are no-ops without consent.
- Tests: the `Api` helper installs a fake `understand_llm` (default reply: no KC), so API tests never wait for Ollama. `tests/test_understand.py` has 14 tests:
  - the schema enums and the prompt;
  - bad JSON and unknown IDs are rejected, and the step is skipped while the answer still comes;
  - deduplication and the 2-KC cap;
  - the misconception gate, checked against every E1 case;
  - the check question follows the understood KC;
  - weak evidence is off by default, capped at one per KC, and absent without consent;
  - preference hints and the streak of 3.
- `eval/understand-tagging/`: `cases.jsonl` (40 DRAFT HBP cases U01–U40: paraphrases, 7 stated misconceptions, 6 questions *about* a misconception, 2 confusion cases, 3 off-topic) and `run.py` (the real prompt, schema and client; `--model`, `--repeat`; writes `results/report.md` and `predictions.jsonl`).

Verification (Done when), against the real Ollama server, 40 cases × 2:

| Model | KC top-1 | No-KC | MC precision | MC recall | Confusion | Q-type | p50 / p95 |
|---|---|---|---|---|---|---|---|
| qwen3.5:9b (config default) | 92% ✅ | 6/6 | 88% ✅ | 100% | 88% | 70% | 1.05 s / 1.14 s ❌ |
| gemma4:e4b | 100% ✅ | 6/6 | 100% ✅ | 100% | 99% | 80% | 0.35 s / 0.41 s ✅ |

Reports: `eval/understand-tagging/results/report.md` (qwen3.5:9b) and `report_gemma4-e4b.md`. Before the gate, qwen3.5:9b had 50% misconception precision: all 7 false positives were questions about a misconception ("Is high blood pressure caused only by stress?").

Both suites pass: 303 tests with BKT and 303 with `TEST_LEARNER_KNOWLEDGE=rule`. Ruff is clean.

Decisions:
- **E1 accuracy is "ideal" for both models**, so the design's decision rule does not turn weak evidence off. `learner.weak_evidence` stays **false** for now. Design §11 E2 decides whether to keep it ("keep it only if it lowers MAE"), and E2 is Step 14. The code path is tested and can be turned on with `LEARNER__WEAK_EVIDENCE=true`.
- **Latency:** qwen3.5:9b is above the p50 ≤ 0.6 s target (a 9B model writing about 35 tokens). gemma4:e4b meets every target. The design says the understand step "uses the already-loaded local model", so the default stays `qwen3.5:9b`, and the switch is a user decision (open question below). Switching is a single config value; gemma4:e4b is already on the server, so nothing has to be pulled.
- Few-shot examples are used only for HBP, because they contain HBP IDs. Other topics rely on the instructions plus the schema.

Interface changes:
- None in `schemas.py`: `Understanding` and `RequestContext.understanding` already existed. `Services` gained `understand_llm`.
- The pipeline order in `config.yaml` and design §7.1 changed: `understand` now comes before `learner_context`.

Open questions for the user:
- Use `gemma4:e4b` for the understand step (`llm.understand.model`)? It is faster (0.35 s vs 1.05 s) and more accurate, but it keeps a second model in VRAM (~5.5 GB for qwen plus several GB more).

Known gaps / TODO:
- `cases.jsonl` is a DRAFT with 40 HBP cases. The team should extend it to 120–150 cases across all five topics (design §11) and re-run E1.
- Misconception IDs from `understand` are used only as weak evidence for now. Tracking (suspected / confirmed / resolved) is Step 12.

How to try it:
```powershell
.venv\Scripts\python eval\understand-tagging\run.py                          # model from config.yaml
.venv\Scripts\python eval\understand-tagging\run.py --model gemma4:e4b --repeat 2
```


## Step 12 — Misconception tracking and corrections — 2026-10-12

Branch `feature/misconceptions` (stacked on `feature/understand`).

What was built:
- New table `learner_misconception` (student_id, misconception_id, kc_id, status, evidence_count, updated_at). It holds IDs and counts only, never text.
  - It is part of `LEARNING_TABLES`, so "reset my learning data" and withdrawing consent clear it.
  - The generic purge in `auth/purge.py` covers it when a student is deleted (every table with `student_id`).
- `app/learner/misconceptions.py`, `MisconceptionTracker`, with the status rules of design §5.1:

  | Signal | none / resolved | suspected | confirmed |
  |---|---|---|---|
  | understand step tagged it (weak) | suspected | confirmed | confirmed |
  | a tagged distractor was chosen | confirmed | confirmed | confirmed |
  | correct answer on an item that targets it | – | resolved | resolved |

  A resolved misconception that comes up again is reopened as suspected and counted from 1.
- `LearnerModel` facade (consent checked everywhere):
  - `misconception_stated`, `check_answered`, `open_misconceptions`;
  - `context()` fills `LearnerContext.misconceptions` with the open misconceptions of the question's KCs (the whole topic when the understand step found none). At most 2, confirmed first, then the most recent.
- `/check`: a tagged distractor → confirmed. A correct answer resolves every open misconception the item's distractors target, across KCs (for example, MC3 is targeted by items of HBP.1, HBP.2 and HBP.3).
- `update_learner`: misconception IDs from the understand step → `misconception_stated`. This does **not** depend on `learner.weak_evidence`, which only gates the knowledge-model update. Tracking is separate, and the Step 11 gate already requires a stated belief.
- Local prompt (`render_local`): one block "Known misunderstandings", with one line per misconception: "Address this misunderstanding the student may have: "<statement>" Correct it gently with this reviewed correction: <correction>". `render_cloud` has no access to the learner context, so the cloud prompt cannot contain it.
- Cloud route: `append_corrections` in the `restore` step adds "A common misunderstanding to watch for: <correction>" when the answer does not already address it.
  - The keyword check: the answer must contain at least 50% of the correction's key words (words of 5+ letters, minus a stoplist).
  - `verify` calls it again after a safety regeneration.
  - The `grounding` checker ignores the appended note, because it is catalog text, not generated text.
  - Every catalog correction passes `medical_safety` (test).
- `attach_check` / `choose_item`: within the chosen KC, an unseen item comes first, then an item whose distractors target one of the student's open misconceptions, then the level match.
- `GET /learner/me`: each topic has `misconceptions: [{kc_id, statement, correction, status}]`. Only open ones are listed, and there are no catalog IDs.
  - "What I know" shows them under "Ideas we are working on". The plain-language source is "seen in your answers" (confirmed) or "may have come up in a question" (suspected).
  - `openapi.json` and `schema.d.ts` are regenerated.
- **Review gate:** statements and corrections reach students and the local prompt only when `content.servable(mc)` allows it (reviewed, or `content.serve_unreviewed`), the same rule as items. Tracking by ID happens either way.

Tests:
- `tests/test_misconceptions.py` has 15 tests:
  - the transitions, including reopening;
  - only IDs and counts are stored;
  - no consent → nothing tracked; reset clears;
  - the full /check → What I know → resolve flow;
  - stated twice → suspected then confirmed, with weak evidence off;
  - unreviewed content is tracked but not shown;
  - the local prompt has exactly one "address" line;
  - prompt scope (the question's KCs, at most 2) and order (confirmed first);
  - the cloud note is appended only when needed and only on the cloud route;
  - the keyword check; medical safety of every correction;
  - item preference, in `choose_item` and through `/ask`.
- The privacy E2E test (forced cloud, rich profile) now also asserts:
  - the transport got no misconception ID, statement or correction;
  - the student's answer ends with the confirmed misconception's correction.
- Frontend: Vitest `WhatIKnow.test.tsx` checks that misconceptions are listed in plain language, with no IDs. `npm run build` passes.
- Backend: 318 tests pass with BKT and 318 with `rule`. Ruff is clean.

Verification (Done when), with the real local model (scratch DB, `serve_unreviewed`):
1. A wrong check answer on HBP.1-q2 (the distractor tagged MC5) → "What I know" shows "The bottom number is the pressure when the heart stops." (confirmed) with its correction.
2. The next question, "What does the bottom number of a reading mean?", got an answer containing "…while your heart rests and refills between beats. It does not mean your heart has stopped…". The attached check item was HBP.1-q4, which targets MC5.
3. "My blood pressure is normal now, so I can stop my medication, right?" → the real understand step tagged MC2 → "What I know" lists it as suspected. The answer said not to stop without a doctor or pharmacist.
4. The cloud payload stays clean: covered by the E2E test.

Decisions:
- The prompt includes at most 2 misconceptions, so the local prompt stays short.
- With no understood KC, the topic's open misconceptions are used, so a misconception is still addressed when the understand step is skipped.
- The keyword threshold of 50% is a heuristic. A false "already addressed" only means the note is not appended to that answer.

Interface changes:
- `schemas.py`: none. `LearnerContext.misconceptions` and `MisconceptionRef` already existed.
- New table `learner_misconception`. API: `TopicProfile.misconceptions` in `GET /learner/me`. `choose_item(..., open_misconceptions=...)` has a new optional parameter.

Known gaps / TODO:
- On the first request after the Ollama server has unloaded the model, the understand step can hit its 5 s timeout and is skipped (seen once in the real-model run). Warming up the model at start-up, or using a small dedicated understand model (Step 11 open question), would avoid this.
- All corrections are still DRAFT and unreviewed. Without `serve_unreviewed` nothing is shown until Dr. Abbas reviews them.

How to try it:
```powershell
# backend + frontend as in DEMO.md, with CONTENT__SERVE_UNREVIEWED=true
# Chat: answer a check question with a wrong option -> "What I know" lists the misunderstanding
```


## Step 13 — Admin service and instructor dashboard — 2026-10-12

Branch `feature/dashboard` (stacked on `feature/misconceptions`).

What was built (backend, `app/admin/` + `app/api/v1/admin.py`; every route requires the instructor):
- **Runtime config** (`GET/PUT /admin/config`). The editable subset: `routing.threshold`, `verify.checkers`, `learner.knowledge`, `learner.weak_evidence`, `learner.levels`.
  - A PUT is validated against the registries and the section validators. It then replaces the settings object (`Services.reconfigure`), rebuilds the learner model and the pipeline runner, and stores a row in the new `config_history` table: values before and after, plus the instructor's `account_id` (no username).
  - The next `/ask` uses the new values; requests already running keep the old ones. A PUT without changes adds no history row.
  - The newest history row is applied again at startup, so a change survives a restart.
  - `medical_safety`, `pii_leak` and `profile_leak` cannot be switched off (422). Only `grounding`, and later non-safety checkers, are optional.
- **Class summary** (`GET /admin/class-summary?topic=`):
  - The population is the students with consent.
  - For each KC, it counts students per band: `not_assessed` (no graded answer yet), basic, intermediate, advanced, mastered.
  - The top misconceptions are counted as students with that misconception open.
  - **Suppression** uses `learner.class_summary_min_group` (5):
    - population < 5 → only `suppressed: true`;
    - a band count of 1–4 → `null` (0 is shown);
    - if a row then has exactly one hidden cell, the next smallest non-zero cell is hidden too, so the hidden one cannot be computed from the total;
    - misconceptions held by fewer than 5 students are not listed, only counted (`misconceptions_hidden`).
  - No student IDs are returned (test).
- **Logs** (`GET /admin/logs?page=&page_size=&topic=`):
  - entries hold the sanitized question, route and score, model, latency (sum of step timings), check statuses and warnings. There is no student or session ID.
  - stats: the number of requests, local/cloud counts, the cloud share, and latency p50/p95.
- **Materials** (`POST /admin/topics/{topic}/materials`, multipart): the file goes to `<rag.materials_dir>/<topic>/` (new setting, default `data/topics`, git-ignored).
  - The file name is cleaned, so the path part is dropped. Allowed types: `.md .txt .pdf .html .htm .docx`, up to 20 MB, not empty.
  - An existing file returns 409 unless `replace=true`.
  - If the retriever has `ingest(topic, path)` (Siyun's part, as documented in `rag/interface.py`), it is called; an ingest error is reported, and the file stays.
  - New dependency: `python-multipart`.
- **Content status** (`GET /admin/content`): per topic, the KC count, items reviewed of total, corrections reviewed of total, and the uploaded materials, plus the `serve_unreviewed` flag.

Frontend `/admin/*` (tabs):
- **Students:**
  - add a student, with the hint "Do not use real student numbers as usernames";
  - the temporary password is shown once with a Copy button;
  - reset password (shown once), activate/deactivate;
  - delete with a typed-username confirmation that lists what is deleted.
- **Class summary:** a topic picker and one stacked bar per KC. Hidden groups are pooled in one hatched "<5" segment, and the screen-reader label says "fewer than 5". The suppression notice appears for small classes, followed by the misconception list and the hidden count.
- **Settings:** the form for the runtime subset (required checkers are checked and disabled), "Save and apply", and the change history.
- **Logs:** stat cards (questions, routed to cloud, p50, p95), a paginated table with "answered by <model>", so a cloud route with local fallback is visible.
- **Content:** a review status per topic, a development-mode warning while `serve_unreviewed` is on, and a materials list with upload.

Tests:
- `tests/test_admin_dashboard.py` has 14 tests:
  - every `/admin/*` route returns 403 for a student and 401 without a login, read from the OpenAPI paths;
  - config contents; a threshold change takes effect on the next `/ask` (local → cloud);
  - checkers and the knowledge model are swapped live;
  - invalid changes are rejected (required checker, unknown checker or model, bad levels, threshold > 1);
  - history, the no-op PUT, and a restart restoring the value;
  - the suppression rules, full suppression for 3 students, and counts for 7 students (one misconception listed, one hidden, no IDs);
  - logs are sanitized ("Alice" → `<PERSON_1>`), paginated, with stats;
  - uploads: stored, listed, the rules (type, empty, 409, replace, path traversal, unknown topic), and `ingest` is called.
- Vitest `Admin.test.tsx` has 4 tests:
  - adding a student shows the temporary password once;
  - delete stays disabled until the username is typed;
  - the suppression message;
  - bars with the hidden segment and its accessible label.
- Backend: 332 tests pass with BKT and 332 with `rule`. Ruff is clean. Frontend: 7 Vitest tests pass and `npm run build` succeeds.

Verification (Done when), with uvicorn and Vite on a scratch DB (`serve_unreviewed`, `ROUTING__STUB_SCORE=0.5`) and the real local model, in the built-in browser:
1. `scripts/demo_seed.py` seeded the 3 demo students → the Class summary tab showed "Fewer than 5 students have a learning profile… hidden to protect their privacy".
2. After adding 6 simulated students (9 in total), the tab showed bars per KC with exact counts (for example, 7 basic) and hatched "<5" segments for the small groups.
3. Settings: the threshold went from 0.6 to 0.4 with "Save and apply" ("Saved. The next question uses the new settings."; the history shows `routing_threshold`).
   - Before the change: demo.novice's question → `local (0.50)`.
   - After it, without a restart: the router chose `cloud (0.50)`. No cloud key is configured on this machine, so the answer fell back to the local model with the warning "The cloud model was unavailable…". The Logs tab shows both rows, "routed to cloud 50%", and "answered by qwen3.5:9b".
4. The Students, Logs and Content tabs rendered as described.

Decisions:
- The safety and privacy checkers are locked on in the dashboard. Design §2 says the safety and privacy rules never depend on configuration.
- A dashboard change is stored in the DB and wins over `config.yaml` after a restart. To go back to the file values, save them again in Settings. A "reset to config.yaml" button can be added if wanted.
- The class-summary population is students with consent (only they have a profile). `not_assessed` is shown separately, so a prior estimate is not shown as "basic".
- Secondary suppression was added on top of the design's n < 5 rule, so a hidden count cannot be worked out from the total.

Interface changes:
- New tables: `config_history`, plus `learner_misconception` from Step 12.
- New setting: `rag.materials_dir`.
- New API routes: `/admin/config`, `/admin/class-summary`, `/admin/logs`, `/admin/content`, `/admin/topics/{topic}/materials`.
- `Services.reconfigure()`. The optional `Retriever.ingest(topic, path)` is now called.
- New dependency: `python-multipart`.

Known gaps / TODO:
- Uploads are stored but not indexed until Siyun's retriever implements `ingest`.
- There is no route to delete an uploaded material yet; remove files from `data/topics/<topic>/` by hand.
- The runtime config is per process. With several API workers, each worker applies the change only on restart (the compose setup runs one worker).

How to try it:
```powershell
# backend + frontend (DEMO.md), log in as the instructor -> /admin
# Settings: change the threshold; Class summary: needs >= 5 students with consent
```


## Step 14 — Evaluation harnesses (E2, E3, E4) — 2026-10-12

Branch `feature/evaluation` (stacked on `feature/dashboard`).

What was built:
- **E2, `eval/learner-sim/`** (`sim.py` + `run.py`). Simulated students go through the **real** `LearnerModel`: an in-memory SQLite database, the real `apply_diagnostic`, `next_kc`, `choose_item`, `observe` and `check_answered`.
  - The student model: a hidden true mastery per KC (Beta draw, capped at prerequisite + 0.2); learning in [0.05, 0.20]; forgetting 0.02 per step on every KC (multiplicative); slip in [0.10, 0.25] and guess in [0.20, 0.40], away from the BKT defaults.
  - Weak confusion signals are drawn from the true mastery and mis-tagged at the E1 error rate. It is read from the E1 report (8%).
  - Runs: bkt and rule, each with weak evidence off and on, on the same students (same seed); then a one-at-a-time sweep of the BKT parameters.
  - Metrics: MAE, next-answer AUC (with an **oracle AUC** from the true P(correct) as the ceiling), and level-band accuracy.
  - The report applies the pre-registered rule, prints the recommended `learner.knowledge`, and includes 3 SVG charts. They are written by hand: no matplotlib dependency.
- **E4, `eval/privacy-audit/`** (`audit.py` + `run.py` + `pii_questions.jsonl`).
  - The recording cloud client is installed **through config**: `llm.cloud.audit_log` (JSONL of every CloudRequest plus the exact messages) and `llm.cloud.audit_echo` (a local echo instead of a provider; nothing leaves the machine). See `app/llm/audit.py`; the factory installs it only when configured.
  - The scripted run creates the personas through `admin/students`, onboards them, and asks the E3 questions, the E1 cases and the planted-PII questions, all forced to the cloud route.
  - The audit checks:
    - fields outside the allow-list, and messages that are not exactly `render_cloud(request)`;
    - identity values (usernames, display names, surnames);
    - profile data (student IDs, item and misconception IDs, misconception texts);
    - typed PII values, plus an analyzer re-scan;
    - identity and raw typed PII in the database (outside `account`) and in the logs.
  - **Exit 1 on any leak.**
- **E3, `eval/personalization/`** (`run.py` + `questions.jsonl` with 20 HBP questions).
  - Four personas (`eval/common/harness.py`) are created through `admin/students` with onboarding, preferences and scripted check answers: novice; intermediate with MC5; advanced; mixed prerequisites.
  - Personalization on and off uses the new switch `learner.personalize` (false → `LearnerContext(personalized=False)` in `learner_context`). The run uses the local route, and post-response learning is off, so on and off see the same profile.
  - A blind pairwise judge compares the answers in random A/B order. It can be any OpenAI-compatible API (`JUDGE_BASE_URL`, `JUDGE_MODEL`, `JUDGE_API_KEY`); the default is Ollama `/v1` with `gemma4:e4b`, a different model from the one that answers. Judge token limit: 4000, because gemma4 reasons first on that endpoint.
  - Metrics and targets follow design §11 E3, with its decision.
  - `abbas_sample.csv` holds 30 blind pairs with empty rating columns, plus `abbas_key.csv`.
- `eval/common/harness.py`: the in-process app on its own temporary database, configured through `SECTION__FIELD` variables. It provides the instructor, the personas, the fake models for smoke mode, and log capture.
- CI: the backend job also runs the three harnesses in smoke mode. E4 fails the build on any leak.
- `eval/README.md`: how to run each harness, its options, and where the reports go.

**Privacy fix found by E4:**
- The first smoke audit found real leaks. With `en_core_web_sm`, NER missed the student's own name in "Hi, I'm Lucas Bergeron…" and "This is Maya Okafor…", and a typed username can never be found by NER. These values reached the cloud payload, and they were also stored in `request_log` as "sanitized" text.
- Fix: `AccountService.identity_terms(student_id)` returns the student's display name, its parts (3+ letters) and the username. They are read per request and kept in memory only. The privacy filter passes them to `PIIAnalyzer.analyze(text, names, usernames)`, which always marks whole-word occurrences as `PERSON` / `USERNAME`.
- After the fix, the smoke audit is clean. New tests in `test_privacy.py` cover the analyzer, the stored sanitized text, and the whole-word rule ("Tom" ≠ "symptoms").

Tests:
- `tests/test_eval_tools.py` has 16 tests:
  - the auditor finds each planted leak class, a clean request passes, a typed own name counts as PII rather than identity, and storage matching is whole-word;
  - AUC;
  - a tiny simulation through the real learner model, for bkt and rule;
  - the recording client is installed through config and captures exactly the allow-listed request, and is absent otherwise;
  - the personalization switch.
- `tests/test_privacy.py`: 2 new tests.
- Backend: 350 tests pass with BKT and 350 with `rule`. Ruff is clean. All three smoke runs pass from `backend/`, as in CI.

Full runs, against the real servers (reports in each `results/`):

- **E2** (200 students × 40 interactions, HBP; the other topics have no item bank yet, so they are skipped):

  | Config | MAE | AUC (oracle) | Band accuracy |
  |---|---|---|---|
  | bkt | 0.260 | 0.522 (0.621) | 43.3% |
  | rule | 0.203 | 0.551 (0.628) | 61.2% |
  | bkt+weak | 0.242 | 0.524 | 46.5% |
  | rule+weak | 0.196 | 0.541 | 63.1% |

  - BKT − rule MAE per student: **+0.057 (95% CI ± 0.006)**. BKT's AUC is also lower.
  - **Pre-registered decision: switch to `learner.knowledge: rule`. Weak evidence: keep (it lowers MAE for rule, 0.203 → 0.196).**
  - Sweep: BKT's MAE ranges from 0.210 to 0.324. It is best with guess = 0.35 and learn = 0.05, which are closer to the simulated students.
  - The rule method copes better with forgetting, which BKT does not model.
  - The low AUCs are expected: the oracle ceiling is only about 0.62, because of slip and guess.
- **E3** (4 personas × 20 questions × on/off = 160 answers from qwen3.5:9b; judge gemma4:e4b, 80 of 80 judged):
  - level-fit win rate **85%** ✅ (novice 20/20, intermediate 19/20, advanced 20/20, mixed 9/20);
  - known misconception addressed **100%** (75% without personalization) ✅;
  - preference respected **90%** ✅;
  - critical errors 0 vs 0 ✅;
  - **correct 98% vs 100% ❌**. Two personalized answers were judged `minor_error`: intermediate_mc Q05 got the **safe fallback message** (the medical-safety check rejected both attempts at a general question, so it over-blocked), and mixed Q05 is borderline.
  - Following the design rule (all metrics above marginal), the decision is to keep personalization as designed. The correctness miss is flagged in the report for review.
  - `abbas_sample.csv`: 30 blind pairs are ready for Dr. Abbas.
- **E4** (4 personas × 70 questions = 280 asks forced to the cloud; local echo provider):
  - 260 cloud requests recorded. 20 asks stayed local because of personal health details (local-only by design).
  - Fields outside the allow-list 0, identity 0, profile 0, PII 0 (0.0%), and nothing in the DB or logs. **Verdict: no leak.**
  - This is after the fix above. The run used `en_core_web_sm`; production uses `en_core_web_lg`.

Decisions:
- **E2's recommendation has not been applied to `config.yaml`**: it is a design default. The user decides, either via the dashboard (Settings → knowledge model) or in `config.yaml`.
- E2 has no simulated time, so the 24-hour no-repeat rule runs out of items after a few interactions per KC. The least recently answered item is reused, and the report counts how often.
- E3 runs on the local route with post-response learning off, so the "on" and "off" answers see the same profile. The E3 judge is a local model, a different model from the one that answers.
- The own-identity redaction is a strengthening inside the privacy filter. No design decision changes, and the values never leave memory.

Interface changes:
- Config: `llm.cloud.audit_log`, `llm.cloud.audit_echo`, `learner.personalize`.
- Code: `PIIAnalyzer.analyze(text, names=(), usernames=())` and `AccountService.identity_terms()`.
- New placeholder type `<USERNAME_n>`.
- No change to `schemas.py`.

Known gaps / TODO:
- E1/E3/E4 cover HBP only, until the other four topics have KCs, items and catalogs.
- E3's correctness criterion missed: look into medical-safety over-blocking on "How do doctors decide that someone has high blood pressure?" (personalized intermediate answer).
- Run E4 with `en_core_web_lg`, and with `--real-cloud` once a provider is configured.
- Dr. Abbas still has to rate `abbas_sample.csv`.

How to try it: see `eval/README.md`.


## 2026-10-17 — Complete main/RAG/semantic integration

Sources: main@4cf64d7bea85e249592961649289720e30782cfb;
feature/rag-siyun-clean@2ca304ffb0ea27e8a6b3dc1cf855af0fa5aa60d7;
semantic-routing-tongkai@090803b73e5d11881232c44e34ff1dc588782921.

Retain the entire main-branch instructor dashboard, account management, class summary,
course-material upload, configuration history, request logs and learner/understand pipeline.
Merge real medical_hybrid retrieval and its bundled sources, PubMed helper and tests.
Merge 500-question LR/SVM semantic routing, evidence checks, SSE progress/timings, teacher display
toggle and per-question student method choice. No privacy-condition branch is added inside
semantic routing; teammate-owned upstream privacy filter and response checks are preserved.

Interface changes: additive Chunk.metadata; AskRequest.routing_method; RouteInput contextual
passages/method/status; RouteScore analysis/evidence/accepted_indices; response routing diagnostics;
POST ask/stream; GET routing/options; persistent RuntimeConfig.show_routing_progress.
See ROUTING_PATCH.md and INTEGRATION.md for behavior, provenance and validation limits.


## 2026-10-22 — G1-56: the Docker image carries the routing and evidence models

The API image now contains every local model the app uses, so the container answers offline and never
downloads a model while a student asks:
- CPU-only torch (the default wheel bundles CUDA that the encoders do not need).
- The routing encoder (`all-MiniLM-L6-v2`) and both evidence cross-encoders are cached in `/opt/hf` at build
  time (build args, defaults match `config.yaml`); `HF_HUB_OFFLINE=1` from then on.
- The trained LR/SVM weights are copied from `data/routing/models` to `/app/models/routing`
  (`ROUTING__MODEL_DIR`), outside the `/app/data` volume so a rebuild is not hidden by an old volume.
- `python -m app.routing.prepare --check` (new) loads every configured asset without downloading and fails
  the build, naming the missing model, if one is absent or the weights do not match the encoder.
- `scripts/demo_seed.py` is in the image: `docker compose exec api python /app/scripts/demo_seed.py`.

CI gains a `docker` job: compose build (with `en_core_web_sm`), start and wait for health through the web
proxy, `prepare --check` inside the container, and the demo seed script end to end (no Ollama in CI).

Not verified locally (no Docker on the development machine): the first CI run is the build test.
