# v4 implementation guide (for coding agents and the team)

Updated 2026-11-04 · based on main `d774dfe` · owners: Z = Zhenyan Xing, T = Tongkai Liu, S = Siyun Tan

This file is the **single entry point** for the v4 work: background, rules that must not be broken, target
architecture, which files each task touches, when a task is done, and how to test. With a task ID (for
example `Z4`) you can start.

A Chinese companion for the team: [v4-implementation-guide_zh.md](v4-implementation-guide_zh.md) (the English
file is the one agents follow, rule 14).

Design documents that are part of this guide:
- [design/course-structure.md](design/course-structure.md): what a course is, accounts and roles,
  enrollment, learner data scope, settings per course, database, migration (task Z1, decided).
- [design/api-v2.md](design/api-v2.md): the HTTP API v2 and its versioning rules.

---

## 0. How to use this file

1. **Read sections 1–3 first**: background, rules, code map.
2. **Find your task** in section 7 and check that the tasks it depends on are merged.
3. **Branch, develop, test and open a PR as in section 8.** One task, one PR.
4. **Only change code in your own component** (section 5). If you need something from another component,
   use the interfaces in section 6. If an interface is missing, say so in the PR; the owner changes it.
5. **If this file or a design document does not answer a question**, do not guess: write the assumption in
   the PR description for the owner to confirm.

---

## 1. Background and goals

**Today (v3.1)**: a privacy-aware hybrid AI tutor for one class and five health topics.
- **Pipeline**: every question goes through the privacy filter; a router picks the local or the cloud model.
- **Retrieval**: MedlinePlus pages and instructor uploads.
- **Personalization**: BKT learner model.
- **Instructor side**: the dashboard shows class-level data only.
- **Deployment**: SQLite; Docker runs api + web.

**What the client asked for** (meeting of 3 Nov, client Prof. Abbas):
- **The prototype phase is over**: a beta for all his students in the winter term, linked from Brightspace;
  the interface must look like a real product.
- **Not only health**: any course, built around the **whole course material** (syllabus, project
  requirements, templates, lecture notes).
- **Instructors create their own courses.**
- **Instructor AI**: generate project directions, sample proposals and similar.
- **Per-student overview**: the instructor can see each student and set a learning plan.
- **Deployment** in the client's own environment.

**v4 goal**: **evolve** the current code (no rewrite) into a multi-course, multi-instructor course tutor:
- privacy rules per course type;
- instructor AI;
- one Docker Compose deployment.

**Demo and test courses**: eight open courses (MIT OpenCourseWare and Harvard CS50x, CC BY-NC-SA 4.0), two
each in medical science, life science, ECE and computer science, in `data/demo_courses/` (stored as zips:
run `python scripts/fetch_open_courses.py unpack` first; see its `README.md`). They include syllabi,
calendars, assignments and exams; solutions are in `instructor_only/` and are never course material.
**Every test, evaluation and demo uses them** (decided 2026-11-12, replacing ELG 5902). The
fictional "General Medical Knowledge" course stays for the v3 migration.

**Out of scope for now**:
- a Chinese interface or other Chinese features beyond handling Chinese input (rule 14);
- research ethics approval (we follow the professors' requirements);
- database backups and disk encryption;
- comparing cloud providers (later GPT, Claude or Cohere, chosen by the client).

---

## 2. Rules that must not be broken

Read before changing code. A PR that breaks any of these is not merged.

### 2.1 Privacy
1. **Never store question text**: `privacy.log_raw_text` must stay `false`; no student text or personal data
   in logs, the database, metrics or error messages.
2. **Original text only goes to a "trusted local" model**: only model connections marked trusted local (the
   default vLLM) may receive original text and the full learner profile. External models (cloud, an
   instructor's own API, web search) only receive what passed the cloud gate. In v4 the model gateway
   enforces this (Z6).
3. **The cloud gate applies to every router** (`backend/app/pipeline/steps/generate.py`): personal health
   questions follow `privacy.health_detail_policy`; the leak guard blocks any personal data, student ID,
   item ID or misconception text; a blocked or failing cloud call is answered locally and the student is told
   why.
4. **The learner profile never goes to the cloud**; the `profile_leak` and `pii_leak` checkers stay on.
5. **Any change to privacy rules re-runs E6** (`eval/privacy-filter/`) and must not make it worse. A PR that
   changes recognizers without the evaluation is not merged.
6. **Web search queries only come from the privacy module's `search_query()`** (Z11); search code never sees
   the original text.

### 2.2 Permissions
7. **The course is the permission boundary**: every endpoint first checks the caller's role in the course.
   Instructor A cannot see instructor B's course; a student cannot see another student's data. Every new
   endpoint has tests for this.
8. **The frontend never decides permissions**: it shows what the backend returns; what must not be shown is
   not returned.
9. **An instructor sees one student** only if the course uses visibility mode B and the student did not opt
   out, and only data since `visible_since`; every view is written to the audit log
   (course-structure.md 4.5).

### 2.3 Engineering
10. **No secrets in git**: API keys and passwords only in `.env` (git-ignored) or Docker secrets; never in
    code, tests, documents or commit messages.
11. **One owner per component** (section 5); do not change another component's code.
12. **CI must pass**: backend tests (twice: default BKT and `TEST_LEARNER_KNOWLEDGE=rule`), ruff, evaluation
    smoke tests, frontend build and tests, Docker build.
13. **Privacy constants are not configuration**: `log_raw_text`, the required checkers and recognizer
    internals stay in code or in the privacy profiles.
14. **Chinese only where code must handle Chinese input; never in comments.**
    - **Allowed**: Chinese literals that functional code needs to handle Chinese input (for example the
      patterns in `privacy/recognizers/zh_person.py`, the context words of `recognizers/student_id.py`,
      full-width punctuation in `routing/evidence.py`), and the Chinese test inputs and evaluation data
      that test this support. Write them as plain characters, not `\u` escapes.
    - **English input must not change**: a Chinese rule only matches Chinese text. A PR that adds or
      changes one shows that the English tests and the English E6 results are unchanged.
    - **English only**: comments and docstrings (describe a Chinese pattern in English, for example
      "Chinese self-introduction followed by a name"), identifiers, log and error messages, commit
      messages, PR descriptions and every `.md` file outside `docs/`.
    - **French**: only French UI strings (`frontend/src/i18n/fr.ts`) and French test text for French
      recognizers.
    - **`docs/` is exempt**: it may hold Chinese companion files named `<name>_zh.md` for the team. The
      English file is the one agents follow; whoever changes an English document updates its `_zh`
      companion in the same PR, or adds a line at the top of the companion saying it is out of date.
    - **Cleanup**: Chinese in comments and in Markdown outside `docs/` is removed by Z15 and T14.
15. **API v2 only** (design/api-v2.md): `/api/v1` is frozen; new endpoints and fields go to `/api/v2`.
    Within v2 only additive changes; a breaking change needs `/api/v3`, decided by Z.

---

## 3. Code map (main `d774dfe`)

| Part | Location | Notes |
|---|---|---|
| Config | `config.yaml`, `backend/app/core/config.py` | pydantic settings; env vars `SECTION__FIELD` override the yaml |
| Services | `backend/app/core/services.py` | `build_services()`; `reconfigure()` replaces global objects (removed in v4, section 4.4) |
| Registries | `backend/app/core/registry.py` | routers, retrievers, knowledge models, checkers, pipeline steps are registered by name and selected by config |
| Pipeline | `backend/app/pipeline/runner.py`, `steps/*.py` | step list in `config.yaml` `pipeline`; one shared `RequestContext` (`core/schemas.py`) |
| Privacy | `backend/app/privacy/` (`analyzer.py`, `recognizers/`, `generalize.py`, `llm_check.py`, `policy.py`, `session_health.py`) | Presidio + spaCy `en_core_web_lg` + custom recognizers |
| Cloud gate | `backend/app/pipeline/steps/generate.py`, `backend/app/llm/cloud_guard.py` | shared by all routers |
| Model clients | `backend/app/llm/` (`ollama_client.py`, `openai_compat.py`, `factory.py`, `fake.py`) | tests use `fake.py` |
| Routing | `backend/app/routing/` (`semantic.py`, `evidence.py`, `methods/`, `train.py`, `prepare.py`) | MiniLM + LR/SVM; model files in `data/routing/models` |
| Retrieval | `backend/app/rag/` (`medical_hybrid.py`, `documents.py`) | BM25 + TF-IDF; one index per topic; PDF pages since PR #16 |
| Learner | `backend/app/learner/` (`knowledge/`, `preference/`, `recommender.py`, `content.py`, `understand.py`) | `KnowledgeModel` interface in `knowledge/interface.py` |
| Checkers | `backend/app/verify/checkers/` (`grounding.py`, `medical_safety.py`, `leaks.py`) | `medical_safety` is required today (`REQUIRED_CHECKERS` in `admin/runtime_config.py`) |
| Storage | `backend/app/storage/` (`db.py`, `models.py`) | SQLModel + SQLite; no migrations |
| Accounts | `backend/app/auth/` | Argon2 hashes; server-side sessions; cookie `SameSite=lax`, `Secure` from `cookie_secure` |
| Instructor backend | `backend/app/admin/`, `backend/app/api/v1/admin*.py` | global settings, uploads, class summary, logs |
| Content | `content/topics/<topic>/{kcs,items,misconceptions}.yaml` | loaded at startup; `reviewed_by` (removed in v4) |
| Frontend | `frontend/src/` (`pages/`, `pages/admin/`, `components/`, `i18n/en.ts`, `i18n/fr.ts`, `api/schema.d.ts`) | React 18 + Vite + Tailwind 3 + TanStack Query; API types generated by `npm run gen:api` from `frontend/openapi.json` |
| Evaluation | `eval/` (`privacy-filter/` E6, `privacy-audit/` E4, `learner-sim/` E2, `personalization/` E3, `course_rag_benchmark.py`) | smoke mode in CI |
| Deployment | `docker-compose.yml`, `backend/Dockerfile`, `frontend/Dockerfile` | api + web today |
| CI | `.github/workflows/ci.yml` | backend, frontend and docker jobs |

**Known problems**:
- `**bold**` in answers shows as asterisks in the frontend (T3).
- Citation numbers `[i]` in answers count passages, while the Sources list counts files after removing
  duplicates, so they can disagree (S3).
- During screenshots `understand` timed out twice at 5 s (Z2/Z6 load tests set proper timeouts).
- A developer `.env` with `CONTENT__SERVE_UNREVIEWED=true` makes about 20 tests fail (removed by Z4).

---

## 4. Target architecture (v4)

### 4.1 Evolve, do not rewrite

Pipeline, registries, privacy, routing, model clients, checkers and the student frontend stay; most changes
pass one more argument (the course). These parts are rewritten or heavily changed because their assumptions
changed:

| Module | Change |
|---|---|
| `storage/` | rewrite: PostgreSQL + Alembic; course columns everywhere |
| `core/topics.py`, `learner/content.py` | rewrite as the **course catalog**: content in the database, created by instructors |
| `admin/runtime_config.py`, `services.reconfigure` | rewrite as **settings layers + per-request values** (4.4) |
| `rag/medical_hybrid.py` | evolve and rename into the course retriever: one index per course on disk, course-level and module-level material |
| instructor frontend pages | mostly new |

### 4.2 Deployment: one Docker Compose stack

```
browser ──HTTPS 443──► proxy (Caddy: automatic HTTPS, serves the frontend, forwards /api to api)
                        │
                        ├─ api     FastAPI
                        ├─ worker  same image, background jobs (indexing, instructor AI, evaluations, daily usage reset)
                        ├─ db      PostgreSQL (volume)
                        └─ monitoring  Prometheus + Grafana (optional compose profile)
api / worker ──► vLLM local model service (deployed separately, not in compose; OpenAI-compatible API + API key; trusted local)
api / worker ──► external model APIs (cloud model, an instructor's own OpenAI-compatible API; sanitized content only)
```

- **Two Docker networks**:
  - public network: proxy, api, worker;
  - internal network: `internal: true`; db is only here; api and worker are on both.
- **Ports**: only 443 is mapped (80 only redirects); db and monitoring are not mapped to the host.
- **vLLM**: API key; the vLLM host firewall only allows the app host; HTTPS if traffic crosses the internet.
- **Local development**: point the model URL at Ollama or any OpenAI-compatible URL.
- **App host**: no GPU needed.

### 4.3 Components

| Component | Responsibility |
|---|---|
| Identity and access | accounts, login identities (password; later Microsoft Entra ID / Brightspace LTI), sessions, system and course roles, access checks |
| Course catalog | courses, modules, KC graph, check items, misconceptions, materials, members, invitation codes |
| Settings | system settings + course settings + config file + hard caps → effective settings of the request |
| Ask pipeline | configured steps (4.5) |
| Learner service | course-level knowledge model, preferences, learning plans, visibility mode, opt-out |
| Privacy service | privacy profile registry, detection, redaction/restore, cloud gate, rewrite, `scan_document()`, `search_query()` |
| Model gateway | model connection registry (trusted local / external), queueing, timeouts, metering, token streaming, SSRF protection |
| Retrieval service | parsing (pdf, docx, pptx, html, md, txt), chunking, per-course index on disk |
| Checkers | enabled by the privacy profile |
| Instructor AI | four tiers; drafts → accepted |
| Web search | allow-listed sites, cleaned results; query only from `search_query()` |
| Observability | `/metrics`, structured logs without personal data, audit log |

### 4.4 Settings layers

| Layer | Content | Who changes it |
|---|---|---|
| 1. code constants | safety invariants (`log_raw_text=false`, required checkers, recognizer internals) | code only |
| 2. `config.yaml` | defaults and **hard caps** (new `limits` section, below) | whoever deploys |
| 3. env / `.env` / Docker secrets | database URL, API keys, session secret | whoever deploys |
| 4. `system_settings` table | default model connections, enabled course types, optional checkers, weak evidence, level thresholds | admin (web) |
| 5. `course_settings` table | fields listed in course-structure.md section 6.4, all nullable | course instructor (web) |

**Rule**: read values only through `effective_settings(course_id)`; the API layer puts the result on
`RequestContext.settings` and steps read only that. Look from layer 5 upwards for the first value that is
set, then clip to the layer-2 hard cap; layer 1 cannot be overridden.

**How it stays cheap and stable** (details in course-structure.md section 6):
- no setting on a settings page needs a restart: value changes apply on the next request; component
  changes (knowledge model, optional checkers, default routing method, default model endpoints) are built
  in the background in every process and swapped in, and the row stays locked (423) until every process
  runs the new version or the change is rolled back; `services.reconfigure` is removed;
- each table row has a `version`; writes use optimistic locking (409 on conflict), one transaction, a
  `config_history` row and an audit row; history can be restored;
- reads are one primary-key query per request plus a per-process cache keyed by the versions, so every
  process sees a change on its next request without timers or messages;
- the request (or job) keeps one snapshot from start to end.

**Usage limits**: config only for now; the `usage_*` course fields stay null and are not exposed. Counters
are stored per student + course + day from the start.

**Hard-coded values that move into `limits`** (Z5):

| Today | Constant |
|---|---|
| `admin/materials.py` | `MAX_BYTES` |
| `rag/documents.py` | `MAX_FILE_BYTES`, `MAX_TEXT_CHARS`, `MAX_PDF_PAGES` |
| `rag/medical_hybrid.py` | the 2,000,000-character budget per topic, `_MAX_CHARS` |
| `privacy/generalize.py` | `MAX_CHARS` |
| `learner/checks.py` | `DIAGNOSTIC_MAX` |
| `learner/misconceptions.py` | `MAX_IN_PROMPT` |
| `api/v1/survey.py` | `MIN_AGGREGATE_SIZE` |
| `admin/llm_server.py` | `TIMEOUT_S` |
| `admin/logs.py` | `MAX_PAGE_SIZE` |
| new | local model concurrency, queue limit, queue timeout; daily cloud calls and cost cap; per-student questions per minute and per day, cloud calls per day; login failure limit and lock time; allowed e-mail domains; export retention; invitation code expiry |

### 4.5 Ask pipeline (v4)

| # | Step | Change |
|---|---|---|
| 0 | API layer | login + **course role check** + **usage check**; builds `ctx.settings` and `ctx.profile` |
| 1 | `privacy_filter` | loads the **privacy profile** of the course type (base layer + subject profile) |
| 2 | `understand` | unchanged; "logistics vs concept" comes from the router's new output (T5) |
| 3 | `learner_context` | per course; adds the instructor's **learning plan**; skipped for logistics questions |
| 4 | `analyze_route` | one more output field, `question_kind` |
| 5 | `retrieve` | course-level material + the chosen module (or the whole course); logistics questions prefer the syllabus and project requirements |
| 6 | `route` | course settings: `local_only`, `routing_preference`, `routing_threshold` |
| 6a | `web_search` (new, optional) | only for cloud answers that need recent information; query from `search_query()`; allow-listed sites only |
| 7 | `generate` | models only through the **model gateway**, which checks the trust level; token streaming |
| 8 | `restore` | unchanged |
| 9 | `verify` | checkers from the privacy profile (`medical_safety` only for medical courses) |
| 10 | `attach_check` | no check item for logistics questions |
| 11 | `record` | also usage counters and metrics; still no question text |
| 12 | `update_learner` | course-level knowledge model; learner state per course |

### 4.6 Data model

Defined in [design/course-structure.md](design/course-structure.md) sections 3–11 (PostgreSQL only).
Highlights:
- system roles admin / instructor / student;
- one account per uOttawa e-mail;
- course → module (two levels);
- CSV import + invitation code;
- learner data keyed by `student_id` + `course_id`, preferences and consent global;
- end of term = export, then delete the course's student data.

### 4.7 Privacy profiles (per course type)

- **Base layer (every course)**:
  - names, student IDs, e-mails, phone numbers, addresses, dates of birth, ID numbers, grades;
  - a light detector for personal health and special circumstances ("I was sick, can I get an extension?"
    happens in any course).
- **First profiles**:

| Course type | Extra detection | Other differences |
|---|---|---|
| Medical science | the full v3 health rules (`health_detail`, `health_context`, readings, cross-message health, `generalize` rewrite) | `medical_safety` checker, "not medical advice" notice |
| Life science | research participant and sample IDs, personal data from labs; biology terms are not personal health | no medical safety checker |
| Electrical and computer engineering (ECE) | keys, tokens, passwords, private repository URLs, internal IPs, connection strings in code; MAC addresses, serial numbers; circuit and signal values (V, mA, kΩ, Hz, dB) are not personal readings | code snippets kept as they are |
| General (default) | base layer only | — |

- **Extending**: each profile is a config file (for example `backend/app/privacy/profiles/ece.yaml`) listing
  recognizers, word lists, policies, checkers and UI notices. New recognizers use the existing registration.
- **Test sets**: each profile ships a labelled test set and a set of other-subject terms to measure
  over-redaction.

### 4.8 Visibility modes (chosen per course by the instructor)

- **Mode A**: the instructor sees class-level data only (as in v3).
- **Mode B**: the instructor can see an individual overview:
  - KC mastery and trends, check-item history, misconceptions, preferences, activity;
  - question text is still never stored, so it cannot be shown;
  - the instructor can set a learning plan (focus KCs, goals, level, notes).
- **Transparency**: the student sees the current mode when joining, during onboarding and on "What I know",
  together with what the instructor sees and the plan.
- **Switching**:
  - B → A takes effect immediately;
  - A → B: students are told and the mode applies to a student only after he acknowledges it, and **only
    data after that** is shown.
- **Opt-out**: in mode B a student can hide his data. The instructor then sees "this student chose not to
  share"; his data only counts in class aggregates; no learning plan; automatic personalization continues.
- **Audit**: every view of an individual overview is logged.

### 4.9 Instructor AI (four tiers)

| Tier | Feature | Rule |
|---|---|---|
| 1 | From the course material: project directions and project lists (difficulty, KCs, deliverables), sample proposals or writing guides, FAQ (deadlines, grading) | drafts; students see them only after the instructor accepts |
| 2 | Draft KCs, prerequisites, check items and misconceptions from lecture notes | drafts → accepted into the normal tables |
| 3 | Class insights: which KCs students ask about most, most common misconceptions | labels and counts only, never question text |
| 4 | Can the local model handle this course? Generate test questions from the material (instructor can review), answer with the local and the cloud model (both with RAG), score with a judge model + instructor spot checks, report per module and question type with latency and cost | generated questions only, no student data; instructor consent before course material goes to the cloud |

Also:
- instructor questions do not go through learner personalization and are not written to the learner model;
- generation only through the model gateway;
- uploads go through `scan_document()` first (a file may contain a class list).

**"Data may be sent to the cloud" notices**:
- **students**: consent text, a permanent line in the chat, a local/cloud label on every answer;
- **instructors**: before using a generation feature;
- **course settings**: "this course uses the local model only".

### 4.10 Course-level knowledge model

- A layered model:
  - one **ability value** per student and course (Elo/IRT-like, updated online after each answer);
  - KC-level BKT or PFA on top of it;
  - propagation along the KC prerequisite graph (weak prerequisites lower the estimate of dependent KCs).
- The rule model is only a fallback on errors, not the main model.
- It implements the existing `KnowledgeModel` interface (`backend/app/learner/knowledge/interface.py`, gaining
  `course_id`), registered by name, so a deep knowledge-tracing model can replace it later.

### 4.11 Model connections

- **Default**: the system has one trusted local model (the vLLM configured at deployment).
- **Editable**: an instructor can switch to his own OpenAI-compatible API (URL, model name, API key); the
  same for the cloud model.
- **Privacy notice**: the settings page must warn that pointing the local model at someone else's service
  sends original student text there, and the instructor must confirm that he controls that service.
- **SSRF protection**:
  - reject link-local addresses (`169.254.0.0/16`, including cloud metadata);
  - reject the system's own service names and addresses (db, proxy, ...);
  - external connections also reject private address ranges.
- **API keys**: encrypted at rest, only the last characters shown, changes audited.
- **GPU size**: enough for a 9B model; compare a 27B model through OpenRouter (Z2). Only generated test
  questions go to OpenRouter.

---

## 5. Component owners

| Component | Owner |
|---|---|
| Platform (storage, course catalog, settings layers, accounts and login, course and member backend, usage, access checks, CSRF, login rate limits) | Z |
| Privacy (profiles, detection, cloud gate, rewrite, `scan_document()`, `search_query()`, consent text) | Z |
| LLM deployment and testing (model gateway, vLLM connection and load tests, streaming, 9B / 27B comparison, instructor AI tier 4) | Z |
| Docker deployment and operations (compose, proxy, monitoring, CI vulnerability scans, operations manual) | Z |
| Retrieval and course content (`.pptx`, citation numbers, course retriever, demo course material, retrieval evaluation) | S |
| Instructor AI tiers 1–3 (backend) | S |
| Learner (course-level knowledge model, learning plans, visibility modes, overview, opt-out, audit, backend) | S |
| Routing and web search (ECE routing evaluation and training, question type classifier, web search) | T |
| Frontend and UX (all pages, redesign, en/fr strings, renaming, accessibility, UI tests) | T |
| Demo material and user documentation (demo data scripts, manuals, video, Lavin's French review) | T |

**Why T has these components**:
- they do not decide permissions or privacy;
- right and wrong are easy to check;
- they are isolated from other code;
- they are easy to roll back.

Agents working for T must follow sections 2.1 and 2.2 closely; web search only uses `search_query()`.

---

## 6. Interface contract

The binding signatures are in [design/course-structure.md](design/course-structure.md) section 9; the HTTP
endpoints and their owners are in [design/api-v2.md](design/api-v2.md).

| Provider | Interface | Used by |
|---|---|---|
| Z | `effective_settings(course_id)` | everyone |
| Z | `require_course_role(...)`, `require_system_role(...)` (FastAPI dependencies) | every backend endpoint |
| Z | `check_usage(...)` / `record_usage(...)` | API layer, generate step |
| Z | model gateway `complete(role, messages, *, settings, trust_required, stream=False)`; roles `local`, `cloud`, `judge` | S (instructor AI), T (web search answers), pipeline |
| Z | `privacy_profile(course_type)`, `scan_document(text, profile)`, `search_query(ctx)` | pipeline, S (uploads), T (web search) |
| Z | course, module, KC, member, settings, usage endpoints + OpenAPI | T (frontend) |
| S | `CourseRetriever.retrieve(course_id, module_id, query, k)` | pipeline |
| S | `profile_for_instructor(viewer, student_id)` (checks mode, opt-out, `visible_since`) | instructor endpoints |
| S | retrieval, instructor AI and learner endpoints + OpenAPI | T (frontend) |
| T | `SemanticAnalysis.question_kind` (`"concept"` or `"logistics"`) | pipeline |
| T | `web_search(query, allowlist)` | pipeline |

**Working in parallel**: providers first merge the signatures with fake implementations (returning sample
data); users build against the fakes without waiting for the real implementation.

---

## 7. Tasks

| Sprint | Dates | Course milestone |
|---|---|---|
| S4 | Nov 4–10 | Beta Nov 11 |
| S5 | Nov 11–17 | |
| S6 | Nov 18–24 | video Nov 25 |
| S7 | Nov 25 – Dec 2 | Design Day Dec 3 |
| S8 | Dec 3–13 | Final Dec 13 |

"Independent" = does not depend on Z1 code and can start now.

### 7.1 Zhenyan Xing (Z)

| ID | Task | Sprint | Depends on | Main files | Done when |
|---|---|---|---|---|---|
| Z1 | Course structure and interface contract (design documents done) + interface signatures with fakes in code; `course_id`, `module_id`, `settings`, `profile` on `RequestContext` | S4, **by Nov 7** | — | `docs/design/`, `backend/app/core/schemas.py`, new `backend/app/platform/` | S and T confirmed; fakes merged |
| Z2 | 9B vs 27B: 27B through OpenRouter, same course questions, both with RAG; vLLM machine size and cost | S4–S5 | independent | new `eval/model-compare/` | comparison report |
| Z3 | PostgreSQL + Alembic; Postgres test fixture and CI service; drop SQLite | S5 | Z1 | `backend/app/storage/`, new `backend/alembic/`, `.github/workflows/ci.yml` | CI runs on Postgres |
| Z4 | Course catalog: tables of course-structure.md section 10; KCs, items, misconceptions from YAML into the database; v3 migration script (section 11); remove `serve_unreviewed` and `reviewed_by` | S5 | Z3 | `storage/models.py`, `core/topics.py`, `learner/content.py`, `scripts/` | existing tests pass against the migrated "General Medical Knowledge" course |
| Z5 | Settings layers (course-structure.md section 6): `system_settings`, `course_settings` with versions, optimistic locking, history and restore, version-keyed cache, `effective_settings()`, `limits` (table in 4.4); migrate the newest v3 `config_history` row; live component switch with apply state, lock and rollback (section 6.5) and `process_status` heartbeats; remove `services.reconfigure`; steps read `ctx.settings` | S5 | Z3 | `core/config.py`, `core/services.py`, `admin/runtime_config.py`, `pipeline/steps/*`, `config.yaml` | no direct reads of these constants; two courses do not affect each other |
| Z6 | Model gateway: connection registry, trust levels, instructor OpenAI-compatible APIs, encrypted API keys, SSRF protection, queueing and timeouts, token streaming; vLLM load test | S5–S6 | Z5 | `backend/app/llm/` (new `gateway.py`), `admin/llm_server.py` | internal addresses rejected; external connections never get original text (tests); load test report |
| Z7 | Privacy profile framework: base layer + profile files + recognizer registration; profile selected by course type | S5 | Z5 | `backend/app/privacy/` (new `profiles/`) | a new profile needs one config file; E6 not worse |
| Z8 | Docker Compose skeleton: proxy (Caddy), api, worker, db; two networks | S5 | — | `docker-compose.yml`, new `deploy/Caddyfile` | one command starts everything locally |
| Z9 | API v2: auth (join with invitation code), admin, courses, members (CSV import), invitation codes, end of term and export, modules, KCs, items, misconceptions, YAML import/export, settings; `login_identity` | S6 | Z4 | new `backend/app/api/v2/`, `backend/app/auth/` | OpenAPI handed to T; access tests |
| Z10 | Usage counters and limits; access tests for every endpoint; CSRF; login rate limits; password change and logout end all sessions | S6 | Z4 | `backend/app/auth/`, `backend/app/platform/` | access tests cover every endpoint |
| Z11 | Medical profile (v3 rules moved in) + ECE profile + ECE test set; `scan_document()`; `search_query()`; consent text | S6 | Z7 | `privacy/profiles/`, `eval/privacy-filter/` | E6 not worse; ECE results |
| Z12 | Instructor AI tier 4: local vs cloud evaluation | S7 | Z6, S4 | new `backend/app/instructor_ai/eval/` | per-module report for a course |
| Z13 | Deploy the whole stack to the test host; monitoring (app `/metrics`, vLLM metrics, Grafana, alerts); CI scans (`pip-audit`, `npm audit`, `bandit`, image scan) | S7 | Z8 | `docker-compose.yml`, `deploy/`, `.github/workflows/ci.yml` | the client and Lavin can try it; metrics visible |
| Z14 | Deployment and operations manual, handover documents, load test | S8 | — | `docs/` | a newcomer can deploy from it |
| Z15 | Rule 14 in Z code: English docstrings in `privacy/recognizers/zh_person.py` and `recognizers/grade.py` (the Chinese patterns stay); tests that the Chinese patterns leave English input unchanged; English `README.md` and `TEST_PLAN.md` in `eval/model-boundary-test/`; re-run E6 | S5 | — | listed files | no Chinese in comments, docstrings or Markdown outside `docs/`; English tests and English E6 results unchanged |

**If behind, postpone in this order**: Z12 → Grafana and alerts in Z13 → `login_identity`.

### 7.2 Siyun Tan (S), backend only

| ID | Task | Sprint | Depends on | Main files | Done when |
|---|---|---|---|---|---|
| S1 | PR #16 follow-up: the frontend translates the page label (backend returns the number only); relative paths in `docs/RAG_COURSE_BETA.md` | S4 | independent | `backend/app/api/v1/ask.py`, `docs/RAG_COURSE_BETA.md` | merged |
| S2 | `.pptx`: `python-pptx` reads slide text, tables and speaker notes; `slide N` per chunk; slide titles as section headings; unpacked size check; clear error when slides are images only; tests with a fictional 3-slide deck | S4–S5 | S1 | `backend/app/rag/documents.py`, `admin/materials.py` | tests pass; sources show slide N |
| S3 | Citation numbers match the Sources list | S5 | S1 | `backend/app/api/v1/ask.py`, `backend/app/prompts/render.py` | tests |
| S4 | Course retriever: course-level and module-level material; one index per course on disk with `index_version`; worker rebuild; uploads call `scan_document()` | S5–S6 | Z4, Z11 (fake first) | `backend/app/rag/` (`medical_hybrid.py` renamed and changed) | syllabus and project requirements are retrieved |
| S5 | Demo course material: the eight open course packs in `data/demo_courses/` (done by Z, see 7.5); remaining: check that each pack uploads and retrieves through the course retriever | S5 | independent | `data/` (layout from course-structure.md section 7) | all eight courses upload and retrieve |
| S6 | Instructor AI tier 1 backend, through the model gateway | S6 | S4, Z6 | new `backend/app/instructor_ai/` | drafts visible to students only after acceptance |
| S7 | Instructor AI tier 2 backend (KCs, check items, misconceptions; drafts → accepted); also used by the course diagnostic (D3) | S6–S7 | Z4, S4 | same | a new course can be drafted by AI and used for personalization after acceptance |
| S8 | Course-level knowledge model (4.10) | S6–S7 | Z4 | `backend/app/learner/knowledge/` | evaluation against the current BKT (`eval/learner-sim/`) |
| S9 | Visibility modes A/B, overview, learning plan, opt-out, audit; end-of-term export content | S6–S7 | Z4, Z10 | `backend/app/learner/`, `backend/app/api/v2/` | tests cover "what must not be seen is not returned" |
| S10 | Instructor AI tier 3: class insights backend | S7 | S8 | `backend/app/instructor_ai/` | never returns question text |
| S11 | Retrieval evaluation on the open course packs, at least one per area (`eval/course_rag_benchmark.py`) | S7 | S5 | `eval/` | results per area |
| S12 | Self-review and handover documents | S8 | — | `docs/` | checklist |

**If behind, postpone in this order**: S10 → the learning-plan part of S9.

### 7.3 Tongkai Liu (T)

| ID | Task | Sprint | Depends on | Main files | Done when |
|---|---|---|---|---|---|
| T1 | Beta routing evaluation (G1-105) and Beta report (G1-108) | S4 | — | `eval/` | delivered on time |
| T2 | Frontend redesign draft: a few versions with v0; choose AI Elements or assistant-ui (7.4) | S4–S5 | independent | design draft | Z, S and the client agree |
| T3 | Upgrade to Tailwind 4 and React 19, add shadcn/ui; restyle existing pages; render answers as Markdown (fixes bold) | S5 | T2 | `frontend/` | existing frontend tests pass; screenshots compared |
| T4 | ECE and computer science routing evaluation: write and label questions from the ECE and computer science packs in `data/demo_courses/`; evaluate; add training data and retrain if needed | S5–S6 | S5 | `backend/app/routing/`, `data/routing/`, `eval/` | report; engineering questions are not all sent to the cloud |
| T5 | Question type classifier (concept / logistics): labelled data, one more output of the routing model | S6 | T4 | `backend/app/routing/` | accuracy report |
| T6 | New pages: course picker, join page (invitation code), course management, member import, course settings | S6 | Z9 OpenAPI | `frontend/src/pages/` | UI tests for the main flows |
| T7 | New pages: instructor AI (four tiers), overview, learning plan, visibility mode and opt-out | S6–S7 | S6–S10, Z12 OpenAPI | `frontend/src/pages/` | same |
| T8 | "Data may be sent to the cloud" notices (text from Z); en/fr strings of all new pages | S6–S7 | Z11 | `frontend/src/i18n/` | notices in all three places |
| T9 | Demo accounts and sample data scripts (through the API only); demo flow for both courses | S6 | Z9, S5 | `scripts/` | one command builds the demo |
| T10 | Video (Nov 25); send French UI screenshots to Lavin and apply her corrections | S6 | T3 | — | delivered on time |
| T11 | Renaming (once the name is chosen); accessibility self-check (keyboard, screen reader, contrast, zoom) | S7 | name | `frontend/` | checklist |
| T12 | Student manual, instructor manual (including the TA note in course-structure.md 3.4); routing, frontend and web search handover | S8 | — | `docs/` | a new instructor can use it |
| T13 | Web search (G1-92) + evaluation (G1-106): search API, allow-list, cleaning, results as passages for generation; query only from `search_query()`; outbound calls only through the single outbound helper | S7 | Z11, Z6 | new `backend/app/websearch/`, `config.yaml` pipeline | E4 audit: no personal data in search requests; evaluation report |
| T14 | Remove Chinese from Markdown outside `docs/` (rule 14): rewrite `TODO.md` in English from section 7; move the Chinese copy of `GETTING_STARTED.md` from the repository root to `docs/GETTING_STARTED_zh.md` and fix its links; remove the Chinese lines of `README.md` and `GETTING_STARTED.md`. The Chinese test text in `frontend/src/test/Routing.test.tsx` stays (it tests Chinese input) | S5 | — | listed files | no Chinese in Markdown outside `docs/` |

### 7.4 Frontend stack (T)

**Keep** React + Vite + TypeScript + Tailwind + TanStack Query + React Router; do not move to Next.js. **Add**:

| Purpose | Library |
|---|---|
| Base components | **shadcn/ui** (Radix UI + Tailwind; components are copied into the project; accessible) |
| Chat components | **AI Elements** (Vercel, built on shadcn) or **assistant-ui**; must work with our own SSE backend |
| Answer rendering | **react-markdown + remark-gfm** or **Streamdown**; **KaTeX** (math), **Shiki** (code highlighting) |
| Icons / motion / toasts | **lucide-react** / **Motion** / **sonner** |
| Tables / charts / forms | **TanStack Table** / **Recharts** / **react-hook-form + zod** |
| Font | Inter or Geist |
| Design drafts | **v0** |

**Interface**:
- **Layout**: left sidebar with courses, modules and conversations; centred chat column; rounded composer
  with suggested questions; dark mode.
- **Answers**:
  - streamed token by token (after Z6; until then shown at once);
  - routing steps as a collapsible "thinking" panel, collapsed by default;
  - sources as small cards (file name and page or slide; hover shows the passage);
  - a local/cloud label with a privacy icon on every answer.
- **Instructor side**: shadcn dashboard style (sidebar, stat cards, data tables, charts).
- **Notes**:
  - current shadcn and AI Elements need Tailwind 4 (most components assume React 19): upgrade first; follow
    the official documentation for versions;
  - the frontend never decides permissions (rule 8).

---

### 7.5 Work done by Z for other owners

Z did these with the decision of Z as team lead (2026-11-08), each as its own PR **for the owner's review**: the
owner reviews and approves the PR, and the area stays the owner's afterwards (rule 11 is otherwise unchanged).

| Task | Owner | What Z did | PR | Owner's step |
|---|---|---|---|---|
| T14 | T | `TODO.md` in English from section 7; the Chinese guide moved to `docs/GETTING_STARTED_zh.md`; no Chinese left in `README.md` and `GETTING_STARTED.md` | #54 | review the wording |
| part of T (bandit B615, found by the Z13 scans) | T | the routing and evidence models pinned to Hugging Face commits (`app/routing/revisions.py`, also used by the Docker build) | #56 | review; move to `transformers` 5 together with Z |
| part of S4 (follow-up of Z11) | S | indexing accepts a document unless its scan found student data (`ScanResult.blocking`): course material that names its instructor is no longer refused | #55 | review |
| part of S (bandit B314, found by the Z13 scans) | S | PubMed responses parsed with `defusedxml` | #55 | review |
| learner data per course (course-structure.md 4.1, 4.4) | S | `course_id` on `learner_kc_state`, `learner_topic_level`, `evidence_log` and `learner_misconception` (existing rows go to the demo course); one `LearnerRepository` per course; `app/learner/course_data.py` exports and deletes one course's learner data | #60 | review |
| part of S5 (advisor meeting 2026-11-12) | S | eight open course packs (lectures, syllabi, calendars, assignments, exams; solutions kept instructor-only) as zips in `data/demo_courses/archives/` with manifests, attribution and license; `scripts/fetch_open_courses.py` to unpack and rebuild them; `tests/test_open_course_packs.py` | this PR | review; S5, S11 and T4 use the packs |

From 2026-11-11, by the same decision, Z also works on the remaining S and T tasks of sections 7.2 and 7.3 in
this way (one PR per task, listed in the table above when it is opened). Not started yet: the API v2
endpoints of S4, S6, S7, S9 and S10; T3 to T13; the `react-router` 7 and `vite`/`vitest` updates reported by
the CI scans.

## 8. Workflow

### 8.1 Branches and PRs
- **Branch from `main`**: `<type>/<task-id>-<short-name>`, e.g. `feature/z4-course-catalog`,
  `fix/s3-citation-numbers`, `docs/t12-user-manual`.
- **One task, one PR.** The description states:
  - the task ID;
  - what changed;
  - how it was tested (paste the results);
  - the effect on privacy or permissions ("none" if none).
- **Commit messages** follow the current style: `<scope>: <what>`, e.g. `privacy: ...`, `feat(rag): ...`,
  `docs: ...`. English only (rule 14).
- **Before merging**: CI green and every review comment resolved (both enforced on `main`). A review by
  another member is welcome but not required.

### 8.2 Running and testing
- **Install** (first time):

  ```bash
  python -m venv .venv && .venv/Scripts/python -m pip install -e "backend[dev]"
  ```

  ```bash
  .venv/Scripts/python -m spacy download en_core_web_sm
  ```

  The full system also needs `en_core_web_lg` and the routing models (`python -m app.routing.prepare` in
  `backend/`).
- **Database**: until Z3 is merged, tests use SQLite as today. After Z3, tests need PostgreSQL: start it with
  `docker compose up -d db` and set `TEST_DATABASE_URL` (see `.env.example` after Z3); the test fixture
  creates and drops a temporary database.
- **Backend tests** in `backend/`. **Keep a developer `.env` out of the tests** (for example
  `CONTENT__SERVE_UNREVIEWED=true` breaks about 20 tests until Z4 removes that setting): rename `.env` or run
  in a worktree without it.

  ```bash
  python -m pytest -q
  ```

  ```bash
  TEST_LEARNER_KNOWLEDGE=rule python -m pytest -q
  ```

  ```bash
  python -m ruff check . ../scripts
  ```

  Line length is 110 (`backend/pyproject.toml`).
- **Evaluation smoke tests** (as in CI):

  ```bash
  python ../eval/privacy-audit/run.py --smoke --out ../eval-out/e4
  ```

  ```bash
  python ../eval/privacy-filter/run.py --smoke --out ../eval-out/e6
  ```

  A privacy rule change also needs the full E6 (`eval/privacy-filter/README.md`).
- **Frontend** in `frontend/`. After an API change, run `python -m app.export_openapi` in `backend/`
  (updates `frontend/openapi.json`), then `npm run gen:api` in `frontend/`.

  ```bash
  npm ci
  ```

  ```bash
  npm run build && npm test
  ```

- **Whole system**:

  ```bash
  docker compose up --build
  ```

  The model URL is set in `.env` (see `.env.example`).
- **Models for development**: every developer uses **his own** OpenAI-compatible API (local Ollama,
  OpenRouter or another provider), configured only in his own `.env`. The team's GPU server is not
  reachable from outside. Rules:
  - never commit a key or paste it into an issue, a PR, a log or a test;
  - send only fictional test data to a hosted API, never real student data;
  - unit tests and CI never call a real model (they use `backend/app/llm/fake.py`); a test that needs a
    real model belongs under `eval/` and is skipped when no key is configured.

### 8.3 Test requirements
- **New endpoints**: normal flow + access tests (another course's instructor, another student, logged out).
- **Privacy**: fictional data only; never real student data in tests, evaluation sets or commits.
- **Models**: unit tests use the fake model (`backend/app/llm/fake.py`); evaluations that need real models
  live under `eval/` and run separately.

---

## 9. Decided / open / not now

**Decided**:

| Topic | Decision |
|---|---|
| Course structure, accounts, enrollment, data scope, settings, database, migration, API version | [design/course-structure.md](design/course-structure.md) section 1, [design/api-v2.md](design/api-v2.md) |
| Demo and test courses | eight open courses in `data/demo_courses/` (two each: medical science, life science, ECE, computer science); "General Medical Knowledge" only for the v3 migration |
| First privacy profiles | medical science, life science, ECE |
| Deployment | one Docker Compose stack; vLLM deployed separately and reached by API |
| Database | PostgreSQL only |
| Usage limits | config file for now; course-level fields prepared |
| Visibility | mode per course; students can opt out; data before the switch is not shown |
| Login | own accounts now; `login_identity` prepared for OAuth |
| Instructor AI | all four tiers |
| Knowledge model | course-level layered model; rule model only as fallback |
| Web search | owned by T, following rule 6 |
| Language | Chinese only in functional code and test data that handle Chinese input, without changing English behaviour; never in comments or in Markdown outside `docs/`; `*_zh.md` companions allowed in `docs/` (rule 14) |
| Future maintainers | the student team that takes over the project |

**Open**:
- project name: candidates HALO (Hybrid Adaptive Learning Orchestrator), COMPASS, CAIRN, MAPLE;
- whether the vLLM machine runs all the time or only during class hours;
- scope for this term (to confirm with Prof. Ismaeel and Prof. Abbas).

**Not now**: a Chinese interface, ethics approval, backups and disk encryption, comparing cloud providers.
