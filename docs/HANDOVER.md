# Handover (task Z14)

State of the v4 work on 2026-11-15, for whoever continues it. The rules, owners and task list are in
[v4-implementation-guide.md](v4-implementation-guide.md) (the source of truth); this page says where things
stand and where to look. Running the system: [OPERATIONS.md](OPERATIONS.md).

## 1. Where to read what

| Topic | Document |
|---|---|
| Rules, owners, tasks, workflow | [v4-implementation-guide.md](v4-implementation-guide.md), `AGENTS.md` |
| Courses, roles, enrollment, settings, data model | [design/course-structure.md](design/course-structure.md) |
| HTTP API v2 (the contract) | [design/api-v2.md](design/api-v2.md), `frontend/openapi.json` |
| Database, migrations, the demo course | [DATABASE.md](DATABASE.md) |
| Model connections and the gateway | [MODEL_CONNECTIONS.md](MODEL_CONNECTIONS.md) |
| Privacy profiles, document scanning, web search queries | [PRIVACY_PROFILES.md](PRIVACY_PROFILES.md) |
| Containers, proxy, metrics, CI scans | [../deploy/README.md](../deploy/README.md) |
| Deploying and running | [OPERATIONS.md](OPERATIONS.md) |
| Using the app (students) | [STUDENT_MANUAL.md](STUDENT_MANUAL.md) |
| Using the app (instructors, TA note) | [INSTRUCTOR_MANUAL.md](INSTRUCTOR_MANUAL.md) |
| How the code came about | [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) |

## 2. State per area

| Task | State | Where |
|---|---|---|
| Z1 interface contract | merged | `backend/app/platform/`, `core/schemas.py` |
| Z2 9B vs 27B | merged (#51); local speed on the vLLM server not measured | `eval/model-compare/` (judged in both orders: 27B 6, 9B 2, 12 ties; 9B stays the default; both fit one 24 GB GPU in 4-bit) |
| Z3 PostgreSQL + Alembic | merged | `backend/alembic/`, `app/storage/` |
| Z4 course catalog | merged | `app/catalog/` |
| Z5 settings layers, live component switch | merged | `app/platform/settings.py`, `components.py` |
| Z6 model gateway | merged; real vLLM load test not run (server unreachable) | `app/llm/`, `eval/load-test/` |
| Z7 privacy profiles | merged | `app/privacy/profiles/` |
| Z8 Docker Compose | merged | `docker-compose.yml`, `deploy/` |
| Z9 API v2 (accounts, courses, members, invitations, content, settings, admin) | merged (#42–#45); main fix #47; viewable invitation code #52; v2 ask #61; end of term and export #63 (`app/platform/end_of_term.py`) | `app/api/v2/`, `app/platform/courses.py`, `app/catalog/editor.py` |
| Z10 usage, CSRF, login limits, access tests | merged (#46) | `app/platform/usage.py`, `app/auth/csrf.py`, `tests/test_access_every_endpoint.py` |
| Z11 ECE profile, `scan_document`, `search_query`, consent text | merged (#48) | `app/privacy/recognizers/engineering.py`, `eval/privacy-filter/ece*.py` |
| Z12 instructor AI tier 4 | merged (#53); background jobs in the `job` table, run by the worker | `app/instructor_ai/eval/`, `app/platform/jobs.py` |
| Z13 CI scans, `/metrics`, Prometheus, alerts, Grafana | merged (#49, #58); not deployed on the test host, no alert receiver chosen yet | `.github/workflows/ci.yml`, `app/platform/metrics.py`, `deploy/monitoring/` |
| Z14 manual and handover | merged (#50; this page, OPERATIONS.md); load test on the server outstanding | `docs/` |
| Z15 rule 14 in Z code | merged | `app/privacy/recognizers/` |
| Q1 quizzes and the end-of-term survey (decided 2026-11-12) | merged (#66): quizzes (multiple choice and true/false, local-model drafts reviewed by the instructor, auto-grading, results under the visibility rules, `final` = post-test against the diagnostic), the end-of-term survey (window, anonymous ratings, minimum group of 3), both exported as aggregates and deleted at the end of term; migration 0013 | `app/learner/quizzes.py`, `app/api/v2/quizzes.py`, `app/api/v2/survey.py`, `app/instructor_ai/quiz_drafts.py`, `tests/test_quizzes_v2.py`; api-v2.md 3.9, 3.10; course-structure.md 4.6, 4.7 |
| S (learner data per course, S9) | merged (#60, #62, #77): learner tables per course, export and delete one course, visibility choices, overview, learning plan, answer style in the overview | `app/learner/course_data.py`, `course_views.py`, `visibility_policy.py`, `app/api/v2/learner.py` |
| S4 materials on API v2 | merged (#67): upload scanned before storing, delete, index rebuild job | `app/api/v2/`, `app/rag/index_jobs.py` |
| S5 open course packs | merged (#64, #65 for the scan false positives) | `data/demo_courses/`, `scripts/fetch_open_courses.py` |
| S6, S7, S10 instructor AI tiers 1 to 3 on API v2 | merged (#70): drafts as background jobs, accept into course content, class insights | `app/instructor_ai/draft_jobs.py`, `insights_source.py`, `app/api/v2/` |
| S8 course-level knowledge model | core and simulated evaluation merged; **not registered as a knowledge model**, so the app still runs BKT | `app/learner/knowledge/course_core.py`, `eval/learner-sim/results/course_model.md` |
| S11 retrieval evaluation | merged (#72): all eight packs | `eval/course-rag-packs/` |
| T4 ECE and CS routing evaluation | merged (#75); retrained candidates not adopted | `eval/routing-ece/` |
| T5 question type (concept / logistics) | merged (#80): own weight file, set by the route step; logistics questions search course-level files first | `app/routing/question_type.py`, `app/rag/course_retriever.py` |
| T9 demo build | merged (#69): the demo courses from the packs through API v2 | `scripts/build_demo.py`, `docs/DEMO.md` |
| F1 frontend on API v2 (carries T6, T7, T8) | merged (#71, #78; UI upgrade #81 to #85): student and instructor dashboards, admin, model connections, quizzes, survey, materials | `frontend/`, `docs/design/ui-upgrade.md` |
| T11 accessibility, T12 manuals | merged (#74, #73); renaming waits for the project name; routing, frontend and web search handover notes still open | `docs/ACCESSIBILITY.md`, `docs/STUDENT_MANUAL.md`, `docs/INSTRUCTOR_MANUAL.md` |
| T13 web search | **not started**: `app/websearch/` returns no passages | `app/websearch/` |

## 3. Decisions taken during the work (not obvious from the code)

- **First account is the admin**: the account from `INSTRUCTOR_*` in `.env` gets the system role `admin`. API v1
  shows an admin as `instructor`.
- **Identity data only in `account`**: privacy invariant 6, checked by E4. A membership keeps an e-mail only
  while pending. Login identities hold `account:<id>`.
- **Invitation codes**: 10 characters, 120 days. Join checks the hash; the code is also stored encrypted with
  `SETTINGS_ENCRYPTION_KEY`, so instructors can see it again (Z, 2026-11-08; #52).
- **Content codes never change** (KC, item, misconception, module): learner data refers to them by code.
  Every edit is checked with the seed checks on the whole course. Edits bump `course.content_version`, and
  running processes reload the served course's content.
- **Course types are the privacy profile files**: a new `profiles/<name>.yaml` is a new course type. The API
  validates against the files, not a fixed list (#47).
- **Usage limits**: config only for now (`limits.usage`); the `usage_*` course settings stay null and are not
  exposed (guide 4.4). The v2 ask endpoints check and count them; API v1 has no limits.
- **One pipeline for every course**: API v2 ask runs the same runner inside a course scope
  (`app/platform/course_scope.py`), which gives the steps the course's content, learner model, retriever and
  conversations. A question without a module uses the topic `general`.
- **CSRF**: on API v2 only; API v1 is frozen and its frontend predates it. The session token is derived from
  the HttpOnly session cookie; before login a double-submit cookie is used.
- **Evaluation is only the end-of-term survey** (advisor meeting 2026-11-12): the rating after each answer and the
  answer-style buttons are removed from the new frontend; `/api/v1/survey` stays (API v1 is frozen) but nothing in
  v2 uses it. Survey answers carry no student ID and no time; a separate row only records that a student answered
  (course-structure.md 4.7).
- **Quizzes are progress, not grades**: multiple choice and true/false, one attempt, graded automatically; AI
  drafts come from the local model only and cannot be published unreviewed; results follow the visibility rules
  (guide 4.8). Targeted material for single students is next term; this term only the learning plan with notes.
- **Tests and demos use the eight open course packs** in `data/demo_courses/`.
- **Credentials are redacted in every course** (`secret_token` in the base profile); lab addresses and
  repository URLs only in ECE.
- **Known scan findings** are listed with their reason in `backend/.pip-audit-ignore` (the bandit baseline
  is empty since #55 and #56); anything new fails CI.

## 4. Open work by owner

What Z did in other owners' areas (for their review): guide section 7.5.

| Owner | Task | Why it matters |
|---|---|---|
| S | register the course-level knowledge model (S8) and make it the default, as decided in guide 4.10 | the app still runs plain BKT |
| T | web search (T13) and its evaluation | the only feature of the plan not started |
| T | video (T10, Nov 25); French UI screenshots to Lavin | course deliverable |
| T | renaming (T11), once the project name is chosen | open decision |
| T | routing, frontend and web search handover notes (T12) | handover |
| T, Z | `transformers` 5 (6 pip-audit advisories ignored with reason), `react-router` 7 and `vite`/`vitest` (CI advisories) | CI reports them |
| Z | deploy on the test host with the monitoring profile, the vLLM load test, Z2 local speed | needs access to the test host and the vLLM server |
| Z | choose the alert receiver (`deploy/monitoring/alertmanager.yml`) | alerts are only visible in Alertmanager until then |
| Others | Lavin's second review of the 30 revised items | content |

## 5. Working on the code

```bash
cd backend
python -m pytest -q                              # needs TEST_DATABASE_URL (a PostgreSQL server)
TEST_LEARNER_KNOWLEDGE=rule python -m pytest -q
python -m ruff check . ../scripts
python -m app.export_openapi && (cd ../frontend && npm run gen:api)   # after an API change
```

- Tests ignore the developer's `.env`. Evaluation harnesses do not: a `.env` with removed settings (for
  example `CONTENT__SERVE_UNREVIEWED`) stops them, so remove such lines.
- CI runs the backend tests twice, the evaluation smoke runs (E2, E3, E4, E6, load test), the scans, the
  frontend build and the Docker stack.
- Codex reviews every PR; its threads are resolved before merging.
