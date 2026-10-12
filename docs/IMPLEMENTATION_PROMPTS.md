# Implementation Prompts: Privacy-Aware Hybrid AI Tutor (v3)

> **用法（给你自己看的）**
> 每次开一个新的 agent 会话，只发这一句（把 N 换成步骤号）：
>
> ```
> Read docs/IMPLEMENTATION_PROMPTS.md. Follow "Global rules" and do Step N only. Stop when Step N's "Done when" checks pass and report back.
> ```
>
> - 按顺序做：Step 0 → 10 是 MVP（10/21），Step 11 → 14 是 Beta（11/11）。
> - 每一步结束后，agent 会更新 `docs/IMPLEMENTATION_LOG.md`。下一个会话靠这个文件了解上一步做了什么，所以每步都可以开新会话。
> - 每一步做完先自己运行一遍，再进入下一步。
> - 路由（Tongkai）和 RAG（Siyun）只做接口和 stub，不实现内部逻辑。

---

## Global rules (read before every step)

You are implementing the system specified in **`docs/System_Design_v3.md`** (the design). Read the sections listed in your step before writing code. The design is the source of truth. If the design and a step disagree, follow the step and record the difference in the log.

### Project facts
- Repository root = this repo. Layout follows design §10: `backend/`, `frontend/`, `content/`, `eval/`, `data/`, `docs/`, `config.yaml`, `docker-compose.yml`.
- Dev machine: **Windows 11**, Python 3.12, Node 20+. Every command you document must work in PowerShell; use `python -m ...` forms. Paths in code use `pathlib`.
- Local LLM: Ollama at `http://192.168.2.25:11434` (env `OLLAMA_URL`), model `qwen3.5:9b`, **thinking always off** (`"think": false`). Use Ollama's native `/api/chat`, because the boundary test showed thinking must be disabled explicitly.
- Cloud LLM: any OpenAI-compatible API via the `openai` SDK. The key comes from `.env` and may be missing; the system must still work local-only.
- Backend stack: FastAPI, Pydantic v2, pydantic-settings, SQLModel + SQLite, httpx, openai, presidio-analyzer, presidio-anonymizer, spaCy, PyYAML. Dev tools: pytest, pytest-asyncio, ruff. **No LangChain.**
- Frontend stack: React + TypeScript + Vite, React Router, TanStack Query, Tailwind CSS, openapi-typescript.

### Ownership boundaries
- **Do not implement** the routing score (Tongkai) or RAG retrieval/indexing (Siyun). Only their interfaces, stubs and contract tests live here. Their code plugs in through `config.yaml` (`routing.impl`, `rag.impl`).
- `backend/app/core/schemas.py` is a contract shared with teammates. If you add or change a field there, list it under **"Interface changes"** in the log. Never rename or remove a field without asking the user.

### Privacy invariants (must hold after every step; add tests when a step touches them)
1. Raw question text is never written to the database, logs or session history. Only sanitized text is stored.
2. The cloud client accepts **only** a `CloudRequest` (allow-list schema, `extra="forbid"`). Nothing else reaches the cloud.
3. A `CloudRequest` never contains a student ID, answer history, item IDs or misconception text. Its only labels are `level`, `sequencing` and `detail`.
4. The learner profile is read and written only by backend code. The frontend gets bands and plain-language summaries, never raw probabilities.
5. A failure in `privacy_filter` stops the request. It is never skipped.

### Engineering rules
- Small modules, type hints everywhere, short docstrings. Match the existing code style once it exists.
- Use registries, not if/else chains: steps, checkers, knowledge models and preference models are registered by name and selected in `config.yaml`.
- **Tests must run offline.**
  - Use `FakeLLMClient` (Step 3) instead of real models.
  - Mark tests that need the network with `@pytest.mark.ollama` or `@pytest.mark.cloud`. They are skipped by default and run with `-m ollama`.
  - Tests that need a spaCy model use `en_core_web_sm`.
- Never commit secrets. `.env` is git-ignored; `.env.example` documents every variable.
- Do not pull, delete or change models on the Ollama server. Do not change design decisions. Do not delete user files. **Ask the user first** in all three cases.
- If something is ambiguous, choose the simplest option consistent with the design, and note it in the log under "Decisions".

### End of every step
1. Run the step's **Done when** checks, plus `python -m ruff check backend` and `python -m pytest -q` from `backend/`.
2. Append to `docs/IMPLEMENTATION_LOG.md`:
   ```
   ## Step N — <title> (<date>)
   Done: <bullets>
   Files: <main files added/changed>
   Decisions: <bullets>
   Interface changes: <bullets or "none">
   Known gaps / TODO: <bullets>
   How to try it: <commands>
   ```
3. Commit with the message `step N: <title>`. Do not push.
4. Reply with a short summary and the "How to try it" commands.

---

## Step 0 — Repository bootstrap

**Read:** design §10.

**Tasks**
1. Create the folder layout from design §10. Use empty `__init__.py` files where Python packages are needed, and placeholder `README.md` files only where a folder would otherwise be empty.
2. Create `backend/pyproject.toml` (package name `app`, Python ≥ 3.12):
   - runtime dependencies from Global rules;
   - `dev` extras: pytest, pytest-asyncio, ruff, httpx;
   - ruff config: line length 110, rules `E,F,I,UP,B`;
   - pytest config: `asyncio_mode = "auto"`, markers `ollama`, `cloud`, `presidio`, default `-m "not ollama and not cloud"`.
3. Create `.gitignore` for Python, Node, `.env`, `data/*.db`, `.venv`, `node_modules`, `dist`, `__pycache__`.
4. Create `.env.example` with `OLLAMA_URL`, `CLOUD_BASE_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL`, `ADMIN_TOKEN`, `DATABASE_URL`.
5. Create `config.yaml` with the full structure from design §9 (pipeline, post_response, verify, learner, llm, content). Add:
   ```yaml
   routing: { impl: stub, threshold: 0.6 }
   rag: { impl: stub, k: 4 }
   privacy: { spacy_model: en_core_web_lg, score_threshold: 0.5, local_only_types: [HEALTH_DETAIL], log_raw_text: false }
   courses: { default: { topics: [high_blood_pressure, type2_diabetes, asthma, migraine, pneumonia] } }
   ```
6. Create `backend/app/core/config.py`:
   - a pydantic-settings `Settings` that loads `config.yaml` (path from env `APP_CONFIG`, default repo-root `config.yaml`) plus `.env`;
   - typed sub-models for every section;
   - `get_settings()` cached with `lru_cache`;
   - tests can override it through a fixture.
7. Add `.github/workflows/ci.yml`: Python 3.12, install `backend[dev]`, `python -m spacy download en_core_web_sm`, then `ruff check` and `pytest`. Leave a commented-out frontend job for Step 9.
8. Copy reference material into `eval/`. Skip `__pycache__`. Do not modify the copied files.
   - `C:\Users\xzy19\OneDrive\Courses\Code\elg 5902\model-boundary-test` → `eval/model-boundary-test`
   - `...\ai-tutor-bench\data\testset.jsonl` → `data/synthetic/ai_tutor_bench_testset.jsonl` (used by Step 4)
9. Update the root `README.md`: one paragraph on what the project is, links to the design and to this file, and a "Development setup" section (venv, `pip install -e backend[dev]`, spaCy model, run tests).
10. Create `docs/IMPLEMENTATION_LOG.md` with a header and the Step 0 entry.

**Done when**
- `python -m pip install -e "backend[dev]"` succeeds.
- `python -m pytest -q` runs (zero tests is fine), and `ruff check` is clean.
- A test proves `get_settings()` loads `config.yaml` and reads `routing.threshold == 0.6`.

---

## Step 1 — Contracts: schemas, registries, black-box stubs

**Read:** design §3, §7.1, §8.2, §9.

This step fixes the interfaces that teammates code against. Be exact.

**Tasks**
1. `backend/app/core/schemas.py`: Pydantic v2 models. Field names exactly as below.

   ```python
   Level = Literal["basic", "intermediate", "advanced"]

   class AskRequest:      session_id: str = ""; course_id: str = "default"; student_id: str; topic: str;
                          question: str; language: str = "en"
   class PIIEntity:       type: str; text: str; start: int; end: int; score: float; placeholder: str
   class PIIResult:       entities: list[PIIEntity] = []; is_sensitive: bool = False; cloud_safe: bool = True;
                          sanitized_text: str
   class Chunk:           text: str; source: str; topic: str; score: float; kc_ids: list[str] = [];
                          level: Level | None = None
   class RouteInput:      sanitized_question: str; topic: str; pii: PIIResult; passage_count: int;
                          level: Level | None = None; kc_ids: list[str] = []
   class RouteScore:      score: float (0..1, validated); reasons: list[str] = []
   class LLMResult:       text: str; model: str; backend: Literal["local","cloud"]; prompt_tokens: int | None;
                          completion_tokens: int | None; latency_ms: float; fell_back: bool = False
   class CheckResult:     name: str; status: Literal["pass","warn","fail"]; detail: str = ""
   class Turn:            role: Literal["student","tutor"]; text: str  # sanitized only
                          created_at: datetime
   class Preferences:     sequencing: Literal["example_first","concept_first"] = "example_first";
                          detail: Literal["concise","detailed"] = "concise";
                          source: Literal["default","onboarding","feedback"] = "default"
   class KcState:         kc_id: str; p_mastery: float; level: Level; n_obs: int = 0; last_seen: datetime | None = None
   class MisconceptionRef: id: str; kc_id: str; statement: str; correction: str;
                          status: Literal["suspected","confirmed","resolved"]
   class KcRecommendation: kc_id: str; name: str; reason: str
   class CloudLabels:     (extra="forbid") level: Level; sequencing: ...; detail: ...
   class LearnerContext:  kc_states: dict[str, KcState] = {}; focus_level: Level = "intermediate";
                          misconceptions: list[MisconceptionRef] = []; preferences: Preferences = Preferences();
                          next_kc: KcRecommendation | None = None; personalized: bool = True
                          def to_cloud_labels(self) -> CloudLabels
   class Evidence:        kc_id: str; kind: Literal["strong","weak","diagnostic"]; correct: bool | None = None;
                          signal: Literal["confusion","misconception"] | None = None; misconception_id: str | None = None;
                          item_id: str | None = None; source: Literal["check","understand","onboarding"]
   class Understanding:   kc_ids: list[str] = []; question_type: Literal["definition","how_why","self_management",
                          "check_my_answer","other"] = "other"; confusion: bool = False; misconception_ids: list[str] = []
   class CheckItemPublic: id: str; kc_id: str; stem: str; options: dict[str, str]   # NO answer key
   class CloudRequest:    (extra="forbid") sanitized_question: str; topic: str; passages: list[str] = [];
                          labels: CloudLabels; language: str = "en"
   class Source:          title: str; source: str; kc_ids: list[str] = []
   class AskResponse:     session_id: str; answer: str; sources: list[Source] = []; model_used: str;
                          route_target: Literal["local","cloud"]; route_score: float | None;
                          check_item: CheckItemPublic | None = None; kc_level: Level | None = None;
                          next_kc: KcRecommendation | None = None; checks: list[CheckResult] = [];
                          warnings: list[str] = []; timings_ms: dict[str, float] = {}
   class RequestContext:  request_id: str; request: AskRequest; learner: LearnerContext | None = None;
                          understanding: Understanding | None = None; pii: PIIResult | None = None;
                          history: list[Turn] = []; passages: list[Chunk] = []; route: RouteScore | None = None;
                          target: Literal["local","cloud"] | None = None; cloud_request: CloudRequest | None = None;
                          llm: LLMResult | None = None; answer: str | None = None;
                          check_item: CheckItemPublic | None = None; checks: list[CheckResult] = [];
                          warnings: list[str] = []; timings_ms: dict[str, float] = {}
                          # private, never serialized or logged:
                          _pii_mapping: dict[str, str]  (PrivateAttr)
   ```

   `to_cloud_labels()` returns only `focus_level` and the two preference values.

2. `backend/app/core/registry.py`: a generic `Registry[T]` with `register(name)` used as a decorator, `get(name)` and `names()`. Create instances `steps`, `checkers`, `knowledge_models`, `preference_models`, `routers`, `retrievers`.

3. `backend/app/pipeline/base.py`:
   - `Step` protocol: `name: str`, `on_error: Literal["stop","skip","warn"]`, `async def run(self, ctx) -> RequestContext`;
   - `Checker` protocol: `name`, `def check(self, ctx) -> CheckResult`.

4. Black boxes. Their functions are **sync**, which is simpler for teammates.
   - `backend/app/routing/interface.py`: `RouteScorer` protocol with `route_score(x: RouteInput) -> RouteScore`.
   - `backend/app/routing/stub.py`: registered as `stub`; returns a fixed score from config, default 0.0 (always local).
   - `backend/app/rag/interface.py`: `Retriever` protocol with `retrieve(query, topic, k=4, kc_ids=None, level=None) -> list[Chunk]`.
   - `backend/app/rag/stub.py`: registered as `stub`; returns `[]`. Also add a `fixture` retriever that returns chunks from `data/synthetic/rag_fixture.jsonl` (create 6 short HBP chunks with kc_ids/level, written by you, marked "synthetic placeholder").
5. Contract tests in `backend/tests/contracts/`:
   - **routing:** score in [0, 1]; deterministic for the same input; never raises on an empty question; runs in < 1 s.
   - **rag:** returns `list[Chunk]`; respects `k`; when `kc_ids`/`level` are given, results are a subset or fall back to the topic; never raises on an unknown KC.
   - The tests are parametrized over every registered implementation, so teammates' implementations are tested automatically.
6. `backend/tests/test_schemas.py`:
   - `CloudRequest` and `CloudLabels` reject extra fields;
   - `CheckItemPublic` has no answer field;
   - `RequestContext.model_dump()` does not contain `_pii_mapping`.
7. `docs/INTERFACES.md` (short, for teammates):
   - the two black-box signatures and the related schemas;
   - how to add an implementation (one file + `@routers.register("name")` or `@retrievers.register("name")` + set `routing.impl`/`rag.impl` in config);
   - how to run the contract tests.

**Done when:** all tests pass, and `docs/INTERFACES.md` is ready to send to Tongkai and Siyun.

---

## Step 2 — Pipeline runner, API skeleton, storage

**Read:** design §3, §7.1, §9 (REST API, config), §8.1.

**Tasks**
1. `backend/app/pipeline/runner.py`: `PipelineRunner(step_names, post_response_names)`.
   - It builds the steps from the registry using config.
   - `async run(ctx)` times each step into `ctx.timings_ms[name]` and applies the failure policy:
     - `stop` re-raises as `PipelineError(step, reason)`;
     - `skip` logs and continues;
     - `warn` appends to `ctx.warnings` and continues.
   - Post-response steps run after the response through FastAPI `BackgroundTasks`. Their errors are only logged.
2. Placeholder steps, each in its own file under `pipeline/steps/`, registered under the names in `config.yaml`.
   - Real steps for `route` and `retrieve` now:
     - `retrieve` calls the configured retriever via `asyncio.to_thread`;
     - `route` builds `RouteInput`, calls the router, sets `ctx.target = "cloud"` if score ≥ threshold, and forces `local` when `pii.cloud_safe` is false (configurable `routing.force_local_if_not_cloud_safe: true`).
   - Placeholders until later steps: `privacy_filter`, `learner_context`, `understand`, `generate` (echo), `restore`, `verify`, `attach_check`, `record`, `update_learner`.
3. Storage (`backend/app/storage/`):
   - SQLModel engine from `DATABASE_URL` (default `sqlite:///data/app.db`) and `init_db()`.
   - Tables now: `request_log` (request_id, created_at, session_id, student_id, topic, sanitized_question, target, route_score, model, timings JSON, tokens, checks JSON, warnings JSON) and `session_turn` (session_id, role, text, created_at).
   - Tests use a temp-file DB.
4. Session store: `SessionStore` protocol plus a `SqliteSessionStore` (`history(session_id, last=6)`, `append(session_id, turn)`), registered and selected by config.
5. Implement the real `record` step: it writes `request_log` and appends **sanitized** student and tutor turns.
6. API (`backend/app/main.py`, `backend/app/api/v1/`):
   - `POST /api/v1/ask` creates a `RequestContext` (new `session_id` if empty, `request_id` uuid4), runs the pipeline and returns `AskResponse`. A `PipelineError` returns 422 or 503 with a safe message, never the raw question.
   - `GET /api/v1/sessions/{id}`
   - `GET /api/v1/topics` (topics from config; KC counts come later)
   - `GET /api/v1/health` reports config loaded, DB OK, and Ollama reachable (short timeout; reported, not fatal).
   - CORS for `http://localhost:5173`.
7. `backend/app/export_openapi.py`: writes `frontend/openapi.json` (used in Step 9).
8. Tests:
   - a runner unit test with fake steps covers stop, skip and warn;
   - an API test: `/ask` with stubs returns 200 and an echo answer;
   - a session round-trip test.

**Done when:** `python -m uvicorn app.main:app --reload` (from `backend/`) serves `/docs`, and `/api/v1/ask` returns a response with timings for every step.

---

## Step 3 — LLM layer: local client, cloud guard, generate

**Read:** design §6 (prompt templates, safety), §7.1 (generate, latency), §8.

**Tasks**
1. `backend/app/llm/base.py`: `LLMClient` protocol with `async complete(messages, *, json_schema=None, max_tokens=None) -> LLMResult`.
2. `llm/ollama_client.py`: native `POST {OLLAMA_URL}/api/chat` with `stream: false` and `think: false` (always). Options: `temperature` from config (default 0.2), `num_ctx` (default 8192). When `json_schema` is given, pass it as `format`. Read tokens and durations from the response. Use a timeout from config, retry once on connection errors, and raise `LLMUnavailable` otherwise.
3. `llm/cloud_guard.py` + `llm/cloud_client.py`:
   - `build_cloud_request(ctx) -> CloudRequest`: uses only `pii.sanitized_text`, `topic`, passage texts and `learner.to_cloud_labels()` (default labels if there is no learner).
   - `CloudClient.complete(req: CloudRequest) -> LLMResult` is the **only** public method. It builds the messages itself from the `CloudRequest` using the cloud prompt builder, and calls the `openai` SDK with `base_url`/`api_key`/`model` from settings.
   - If no key is configured, `CloudClient.available` is False.
4. `llm/fake.py`: `FakeLLMClient` with scripted responses for tests. It records every call, so tests can assert what was sent.
5. Prompts (`backend/app/prompts/`):
   - `base_system.md` holds the safety rules. They are identical at every level: health education only; no personal diagnosis, dosing or treatment changes; suggest a clinician for personal situations; use only the provided material when it is given, and say so when the material does not cover the question; answer in the question's language; cite passages as [1], [2].
   - `render_local(ctx) -> messages` may use the full `LearnerContext`, history and passages.
   - `render_cloud(req: CloudRequest) -> messages` may use **only** the `CloudRequest`. Enforce this by its signature.
   - Level and preference partials come in Step 7. For now, include `focus_level` as one line.
6. The real `generate` step:
   - local target → `render_local` + Ollama;
   - cloud target → `build_cloud_request`, store it in `ctx.cloud_request`, then `CloudClient`;
   - if the cloud is unavailable or fails, fall back to local (`fell_back=True`, add a warning);
   - set `ctx.llm` and `ctx.answer`.
7. Tests:
   - local and cloud paths with fakes; the fallback path;
   - **privacy test:** with a context full of learner data, PII mapping and history, the recorded cloud call contains only `CloudRequest` fields; the serialized messages contain no student_id and no raw question;
   - an `@pytest.mark.ollama` smoke test against the real server.

**Done when:** with Ollama reachable, `/api/v1/ask` returns a real answer from qwen3.5:9b, and all offline tests pass.

---

## Step 4 — Privacy filter, anonymization, restore

**Read:** design §2, §7.1 (steps 1 and 7), §8; v2 privacy targets in design §11.

**Tasks**
1. `backend/app/privacy/analyzer.py`: build a Presidio `AnalyzerEngine` once, with the spaCy model from config (`en_core_web_lg`; tests use `en_core_web_sm` through a config override).
   - Built-in entities: PERSON, EMAIL_ADDRESS, PHONE_NUMBER.
   - Leave out DATE_TIME and LOCATION by default; they over-redact health questions. Make the entity list configurable.
2. Custom recognizers, one file each in `privacy/recognizers/`, auto-registered:
   - `student_id.py`: 9-digit student numbers, plus "student number/ID" context words.
   - `grade.py`: personal grades ("I got 62%", "my grade is C+", "I failed the midterm").
   - `health_detail.py`: personal health statements. A first-person or family-member pattern plus a condition, medication or symptom term, e.g. "I have asthma", "my father takes metformin". General questions such as "What is asthma?" must **not** match.
3. `privacy/anonymizer.py`: reversible replacement with numbered placeholders (`<PERSON_1>`, `<STUDENT_ID_1>`). The same value gets the same placeholder within a request. Returns the sanitized text and the mapping.
4. The `privacy_filter` step (`on_error: stop`): sets `ctx.pii` and stores the mapping in `ctx._pii_mapping`.
   - `is_sensitive = bool(entities)`.
   - `cloud_safe = not any(type in privacy.local_only_types)`.
   - It never logs raw text.
5. The `restore` step: for cloud answers, replaces placeholders with the original values, then clears the mapping.
6. Tests:
   - Use `data/synthetic/ai_tutor_bench_testset.jsonl`, items with `category == "pii"`. These have labelled `pii_entities` and `non_pii_terms`. Report recall on the labelled entities (assert ≥ 0.85 with the small model; log the per-type misses). Assert every `non_pii_terms` item survives sanitization.
   - Add 15 health-specific cases of your own (personal vs general phrasing) in `data/synthetic/pii_health_cases.jsonl`.
   - Round trip: anonymize → restore gives back the original values.
   - **DB test:** after an `/ask` containing a name and a student number, the `request_log` and `session_turn` tables do not contain either string.
   - `@pytest.mark.presidio` on tests that need the spaCy model.

**Done when:** all of the above pass, and a request with "My student ID is 300418277 and I have asthma" is routed local (`cloud_safe=false`) and logged only in sanitized form.

---

## Step 5 — Domain content: format, loader, High Blood Pressure draft

**Read:** design §4 (all), §2 principle 6.

**Tasks**
1. Pydantic models plus a loader in `backend/app/learner/content.py` for `content/topics/<topic>/kcs.yaml`, `items.yaml` and `misconceptions.yaml`, using the formats in design §4.1–4.4. Validation:
   - unique IDs;
   - prerequisites exist and form a DAG (report the cycle);
   - every item has 4 options and an `answer` key that exists;
   - every distractor `misconception` ID exists;
   - every misconception's `kc` exists.
   - `ContentStore` API: `topics()`, `kcs(topic)`, `kc(id)`, `prerequisites(id)`, `items(kc_id, reviewed_only)`, `item(id)`, `misconception(id)`, `misconceptions(kc_id)`.
   - `content.serve_unreviewed` controls whether items with `reviewed_by: null` are served.
2. Write a **draft** of the High Blood Pressure content:
   - 6 KCs as in the design example;
   - 4 items per KC (24), at least one per level, with distractors tagged where they reveal a misconception;
   - 10–12 misconceptions with corrections.
   - Rules:
     - general education only; no drug doses; no specific numeric diagnostic thresholds — write `"TBD: guideline"` where a threshold would be needed;
     - every file starts with a comment: `# DRAFT — generated, not medically reviewed. Do not use with students before review.`;
     - `reviewed_by: null` everywhere.
3. Create empty skeleton folders and files for the other four topics, with one placeholder KC each, so the loader and API work.
4. `scripts/export_content_review.py`: exports all KCs, items and misconceptions of a topic to `docs/review/<topic>_review.csv` (one row per item/misconception, with an empty `reviewer_comment` column) for Dr. Abbas.
5. `GET /api/v1/topics` now returns KC counts and the reviewed-item count per topic.
6. Tests: the loader accepts the HBP content; each validation error is caught (one small broken fixture per rule).

**Done when:** the loader validates HBP content, the review CSV is generated, and the user has a file to send to Dr. Abbas.

---

## Step 6 — Learner model core

**Read:** design §5 (all), §8.1, §9 (config `learner`).

**Tasks**
1. Pure functions in `learner/knowledge/bkt_math.py` (no I/O, fully unit-tested):
   - `posterior(p, correct, slip, guess)`
   - `learn(p, T)`
   - `weak_update(p, p_signal_given_L, p_signal_given_notL)`
   - `level_with_hysteresis(p, previous_level, basic_below, advanced_above, h)`
2. Persistence in `learner/repository.py` + SQLModel tables:
   - `learner_kc_state` (student_id, kc_id, p_mastery, level, n_obs, last_seen)
   - `learner_preference`
   - `evidence_log` (student_id, kc_id, kind, item_id, correct, signal, misconception_id, weight, created_at). **No free-text columns.**
   - `consent` (student_id, given, created_at)
3. `KnowledgeModel` implementations, registered as `bkt` and `rule`. Both use the repository.
   - **bkt:**
     - strong evidence → posterior + learn;
     - diagnostic → posterior, no learn;
     - weak → `weak_update` (only `confusion`/`misconception` signals lower mastery), with no learn and at most one weak update per KC per request;
     - parameters from `learner.bkt_defaults` (allow per-level overrides).
   - **rule:** `(correct + 1) / (n + 2)` over the last N strong answers, minus `weak_penalty` per weak signal since the last strong answer, with a floor of 0.
   - Both return `KcState` with the hysteresis level, and log every `Evidence` to `evidence_log`.
4. `PreferenceModel` registered as `simple`: get/update. Explicit feedback applies immediately. Implicit signals apply after 3 consistent signals; keep a counter.
5. `Recommender` (design §5.3): ready ≥ 0.70, mastered ≥ 0.90, order by lowest p, ties prefer the current topic, then lower `n_obs`. When nothing qualifies, return the weakest prerequisite, or None.
6. The `LearnerModel` facade in `learner/facade.py`:
   - `context(student_id, topic, kc_ids=None) -> LearnerContext`;
   - `observe(student_id, evidence)`;
   - `reset(student_id)`.
   - **MVP rule for `focus_level`:** if `kc_ids` is given, use the lowest level among them (design §6). Otherwise use the hysteresis level of the topic's mean mastery. Document this as temporary until Step 11.
   - If consent is missing or false, return `LearnerContext(personalized=False)` and store nothing.
7. The real `learner_context` step (`on_error: skip`, which falls back to an unpersonalized context).
8. Tests:
   - math against hand-computed values;
   - BKT moves up after correct answers and down after wrong ones; weak evidence moves less than strong;
   - hysteresis prevents flip-flop at 0.40 ± 0.03;
   - rule and BKT can be swapped by config with the same downstream behaviour;
   - recommender cases on the HBP graph;
   - no-consent → nothing written.

**Done when:** all learner tests pass, and switching `learner.knowledge: rule` makes no other test fail.

---

## Step 7 — Adaptive flow: onboarding, check questions, level-aware prompts

**Read:** design §5.5, §6, §7.2–7.4.

**Tasks**
1. Prompt partials in `prompts/levels/{basic,intermediate,advanced}.md` and `prompts/style/{example_first,concept_first}.{concise,detailed}.md`.
   - `render_local` and `render_cloud` compose base + level + style.
   - Safety text lives only in the base template and is never overridden.
   - Add a test that every one of the 12 combinations contains the base safety block.
2. Onboarding API:
   - `GET /api/v1/onboarding?topic=` returns the consent text, 2 preference questions and the diagnostic items. Diagnostic: one item per KC, prerequisite-free KCs first, `CheckItemPublic` only, max 10.
   - `POST /api/v1/onboarding` takes `{student_id, topic, consent, preferences, answers:[{item_id, choice}]}`.
     - It stores consent and preferences.
     - It grades answers by key and applies `diagnostic` evidence.
     - If a prerequisite is wrong, its dependents keep `p_init`.
     - Every part is optional.
3. `POST /api/v1/check` takes `{student_id, session_id, item_id, choice}`.
   - It grades by key, applies `strong` evidence, and records the chosen distractor's misconception ID in the evidence log (tracking comes in Step 12).
   - It returns `{correct, correct_choice, explanation, kc_id, kc_level, next_kc}`.
   - Unknown item → 404. No LLM call.
4. The `attach_check` step (`on_error: skip`):
   - KC = the first of `understanding.kc_ids` if present, else the recommender's `next_kc`, else the topic's lowest-mastery KC.
   - It picks an unseen item for that KC, avoids items answered in the last 24 h (from the evidence log), and prefers the item level that matches the KC level.
   - It sets `ctx.check_item`.
5. `GET /api/v1/learner/me?student_id=&topic=` returns per KC: name and band (`basic`/`intermediate`/`advanced`/`mastered` when ≥ 0.90). No probabilities.
   - `DELETE /api/v1/learner/me?student_id=` resets the profile.
   - `POST /api/v1/learner/me/preferences` takes explicit feedback (`more_detail`, `shorter`, `example_first`, `concept_first`).
6. `AskResponse` now fills `check_item`, `kc_level` and `next_kc`.
7. Tests: an end-to-end flow with fakes — onboarding → ask (check attached) → wrong check answer lowers the level → the next ask uses a basic-level prompt (assert on the recorded fake LLM messages).

**Done when:** with curl or `/docs`, one can complete onboarding, ask, answer a check question, and see the band change in `/learner/me`.

---

## Step 8 — Verification, end-to-end hardening

**Read:** design §2 principle 7, §7.1 (verify), §8.2, §13.

**Tasks**
1. Checkers in `verify/checkers/`, registered by name:
   - **medical_safety:** rule-based. **fail** on dosing instructions (number + mg/ml/units + take/dose), instructions to start, stop or change medication, or second-person diagnosis ("you have …"). **warn** if the answer lacks the clinician-referral sentence when the question has `question_type == "self_management"` or the PII result contains HEALTH_DETAIL.
   - **grounding:** heuristic. If passages exist, the share of answer sentences with lexical overlap ≥ 0.2 with some passage must be ≥ 0.5, else warn. With no passages, pass with the detail "no material".
   - **pii_leak:** if `ctx.cloud_request` exists, run the analyzer on its serialized JSON; any entity → fail.
   - **profile_leak:** if `ctx.cloud_request` exists, fail when it contains the student_id, any item ID pattern (`\w+\.\d-q\d`), or any misconception statement from the catalog.
2. The `verify` step (`on_error: warn`) runs the configured checkers and sets `ctx.checks`.
   - On a medical_safety **fail**, regenerate once with an added instruction. If it still fails, replace the answer with a safe fallback message plus the retrieved sources.
   - Other failures add warnings.
3. Wire the final MVP pipeline from `config.yaml` (`understand` stays a no-op until Step 11). Check that every step's `on_error` matches design §7.1.
4. Tests:
   - each checker with positive and negative cases;
   - the regenerate-then-fallback path;
   - **a full privacy E2E test:** an `/ask` with PII and a rich learner profile, forced to cloud via a stub router returning 1.0. Assert that the recorded `CloudRequest` passes both leak checkers, the DB has no raw PII, and the answer has its placeholders restored.

**Done when:** the full offline suite passes, and the privacy E2E test is in CI.

---

## Step 9 — Frontend MVP

**Read:** design §3 (client), §7.2–7.4, §8.3.

**Tasks**
1. `frontend/`: Vite React TS, Tailwind, React Router, TanStack Query.
   - `npm run gen:api` runs openapi-typescript on `openapi.json` (exported by `python -m app.export_openapi`) and writes `src/api/schema.d.ts`.
   - A typed fetch wrapper in `src/api/client.ts`. Base URL from `VITE_API_URL`, default `/api`, with a Vite dev proxy to `http://localhost:8000`.
2. Identity: generate a random `student_id` (uuid) on first visit and store it in `localStorage` (pseudonymous; there is no login in the MVP). Show a small "Reset my data" link that calls DELETE `/learner/me`.
3. Pages:
   - **Onboarding** (`/start`): consent text with an explicit checkbox; 2 preference questions; diagnostic MCQs; a "Skip" button on each part.
   - **Chat** (`/chat`):
     - a topic picker and the message list with sources;
     - a level badge for the current KC band;
     - a check-question card under the tutor answer (radio options → POST `/check` → correct/incorrect + explanation + "Suggested next");
     - feedback buttons "More detail", "Shorter", "Example first", "Idea first";
     - a fixed notice "For learning only — not medical advice";
     - warnings from `AskResponse.warnings` shown subtly.
   - **What I know** (`/me`): KC list with bands per topic, and a reset button with confirmation.
4. Basic accessibility: labelled inputs, keyboard-usable options, visible focus.
5. Vitest: the check card renders options without any answer key and submits the chosen option.
6. Enable the frontend CI job: `npm ci`, `npm run build`, `npm test`.

**Done when:** `npm run dev` plus the backend gives a working onboarding → chat → check → "What I know" loop in the browser.

---

## Step 10 — Packaging and MVP demo

**Read:** design §9 (deployment in v2 §9, unchanged), §12 (MVP row).

**Tasks**
1. `backend/Dockerfile`: python:3.12-slim; installs the package and `en_core_web_lg` (build arg to switch to `sm`); runs uvicorn.
2. `frontend/Dockerfile`: multi-stage Node build → nginx. Its `nginx.conf` serves the SPA and proxies `/api` to `api:8000`.
3. `docker-compose.yml`: services `api` and `web`, with a `data/` volume for SQLite and `env_file: .env`. Ollama stays external (`OLLAMA_URL`).
4. `scripts/demo_seed.py` creates 3 demo students (novice, intermediate, advanced) via the onboarding API. `docs/DEMO.md` gives a 5-minute demo script that shows the level change, a check question, local vs cloud routing (by temporarily setting the stub router score) and the privacy guarantees.
5. `docs/MVP_CHECKLIST.md` maps each MVP deliverable in design §12 to where it is implemented and tested, with status.
6. Update the README: quick start with docker compose, and dev mode.

**Done when:** `docker compose up --build` serves the app on one port, the demo script works end to end against the real Ollama server, and the checklist is complete.

---

# Beta steps (after the MVP)

## Step 11 — Understand step and weak evidence (+ E1 harness)

**Read:** design §0.1 #2–3, §5.1, §7.1 (understand, latency), §11 E1.

1. The `understand` step (`on_error: skip`) calls the local LLM with `json_schema` (Ollama `format`):
   - `kc_ids` items are an enum of the topic's KC IDs;
   - `misconception_ids` are an enum of the topic's catalog IDs;
   - the prompt lists KC id + name + definition and the catalog statements, with 3 few-shot examples;
   - timeout `llm.understand.timeout_s`;
   - invalid JSON or unknown IDs → skip.
2. Pass `understanding.kc_ids` and the level into `retrieve`. `learner_context` now uses `kc_ids` for `focus_level` (lowest level among them).
3. The `update_learner` post-response step applies weak evidence per design §5.1, but only when `learner.weak_evidence` is true. It also turns `question_type`-based preference hints into implicit signals.
4. `eval/understand-tagging/`:
   - `cases.jsonl`: draft 40 HBP student-style questions with gold labels, including paraphrases, off-topic questions and questions with no KC. Mark the file as a draft for the team to extend to 120–150.
   - `run.py` prints KC top-1 accuracy, misconception precision and recall, and p50/p95 latency, and writes `results/report.md`.
   - Thresholds from design §11 E1.
5. Tests with a fake LLM: the schema enum is built correctly; unknown IDs are rejected; weak evidence is capped at one update per KC per request.

**Done when:** the E1 harness runs against the real server (`-m ollama` or a script), and the report shows accuracy and latency.

## Step 12 — Misconception tracking and corrections

**Read:** design §0.1 #2 and #4, §5.1 (misconception table), §6, §8.1.

1. Table `learner_misconception` (student_id, misconception_id, status, evidence_count, updated_at). Status transitions follow design §5.1: suspected / confirmed / resolved.
2. `/check`:
   - a chosen tagged distractor → confirmed;
   - a correct answer on an item whose distractors target an open misconception → resolved.
3. The `understand` misconception IDs → suspected (or confirmed on the second signal), applied in `update_learner`.
4. `LearnerContext.misconceptions` is filled with open misconceptions for the relevant KCs. Local prompt: one "address this misunderstanding" line with the reviewed correction.
5. The `restore` step appends the reviewed correction as a short note to cloud-route answers when a relevant misconception is open and the answer does not already address it (keyword check). The cloud request is unchanged; extend the profile-leak test to confirm this.
6. `attach_check` prefers items whose distractors target an open misconception.
7. `/learner/me` and the "What I know" page list open misconceptions in plain language, with their corrections.

**Done when:** a wrong answer on a tagged distractor shows up in "What I know", the next answer addresses it, and the cloud payload stays clean (test).

## Step 13 — Admin service and instructor dashboard

**Read:** design §3, §8.3, §9 (REST API admin rows), §12 Beta.

1. Admin auth: a bearer token from `ADMIN_TOKEN`, as a FastAPI dependency on `/api/v1/admin/*`.
2. Config endpoints:
   - `GET/PUT /api/v1/admin/config` covers a runtime-editable subset: routing threshold, enabled checkers, `learner.knowledge`, `learner.weak_evidence`, level thresholds.
   - Store changes in a `config_history` table and apply them without a restart.
3. `GET /api/v1/admin/class-summary?topic=`:
   - per KC, the count of students in each band;
   - the top misconceptions with counts;
   - **suppress any count or group < `learner.class_summary_min_group`** (5).
4. `GET /api/v1/admin/logs` returns paginated sanitized request logs, latency percentiles and the local/cloud share.
5. `POST /api/v1/admin/topics/{topic}/materials` stores uploads in `data/topics/<topic>/` and calls an optional `ingest()` on the retriever if it implements one (Siyun's part).
6. Frontend `/admin`:
   - token entry (kept in sessionStorage);
   - pages: Settings, Class summary (bar charts per KC), Logs, Content (review status per topic from the content store).

**Done when:** the dashboard shows the class summary for the seeded demo students (with suppression visible when n < 5), and changing the threshold takes effect on the next `/ask`.

## Step 14 — Evaluation harnesses (E2, E3, E4)

**Read:** design §11 (all), §0.1 #7.

1. `eval/learner-sim/` (E2):
   - The simulator has a hidden true mastery per KC, with learning drawn from [0.05, 0.2], forgetting of 0.02 per step, and slip/guess drawn **differently** from the BKT defaults. Students follow the real recommender and item selection.
   - Weak signals are generated with a noise rate taken from the E1 report (configurable).
   - Run bkt vs rule, and weak evidence on vs off, for 200 students × 40 interactions per topic.
   - Metrics: MAE, next-answer AUC, level-band accuracy.
   - Add a parameter sensitivity sweep.
   - Write `results/report.md` with plots, and apply the pre-registered decision rule from design §11. Print the recommended `learner.knowledge` value.
2. `eval/privacy-audit/` (E4): a recording cloud client (installed through config) captures every `CloudRequest` during a scripted run of all test questions and personas. It reports any field outside the allow-list, PII hits and profile hits. **Exit non-zero on any leak** so it can gate CI.
3. `eval/personalization/` (E3):
   - personas as onboarding answers + scripted check answers;
   - 20 questions;
   - personalization on/off (`personalized=False` override);
   - blind pairwise judging with a configurable OpenAI-compatible judge (random A/B order);
   - a CSV sample of 30 pairs for Dr. Abbas;
   - a report with the metrics and targets from design §11 E3.
4. A short `eval/README.md` that explains how to run each harness and where the reports go.

**Done when:** each harness runs with the fake LLM in CI (smoke mode, small N), and in full mode against the real servers on request.

---

## Integration with teammates (reference for every step)

- **Tongkai (routing):** adds `backend/app/routing/<name>.py` with a class registered via `@routers.register("<name>")` that implements `route_score(x: RouteInput) -> RouteScore`. He sets `routing.impl: <name>` and runs `python -m pytest tests/contracts -k routing`. He must not read anything outside `RouteInput`.
- **Siyun (RAG):** adds `backend/app/rag/<name>.py` registered via `@retrievers.register("<name>")` that implements `retrieve(...)` with KC/level filtering and topic fallback, plus an optional `ingest(topic, path)`. She tags chunks with `kc_ids` and `level` using the KC IDs in `content/topics/*/kcs.yaml`, and runs `python -m pytest tests/contracts -k rag`.
- Integration happens only through `config.yaml`. If a teammate needs a schema change, it goes through `core/schemas.py` and the "Interface changes" log.
