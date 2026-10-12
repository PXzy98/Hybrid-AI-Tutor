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
