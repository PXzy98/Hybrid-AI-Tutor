# Handover (task Z14)

State of the v4 work on 2026-11-09, for whoever continues it. The rules, owners and task list are in
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
| How the code came about | [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md) |

## 2. State per area (Z tasks)

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
| Z9 API v2 (accounts, courses, members, invitations, content, settings, admin) | merged (#42–#45); main fix #47; viewable invitation code #52; end of term not built (section 4) | `app/api/v2/`, `app/platform/courses.py`, `app/catalog/editor.py` |
| Z10 usage, CSRF, login limits, access tests | merged (#46) | `app/platform/usage.py`, `app/auth/csrf.py`, `tests/test_access_every_endpoint.py` |
| Z11 ECE profile, `scan_document`, `search_query`, consent text | merged (#48) | `app/privacy/recognizers/engineering.py`, `eval/privacy-filter/ece*.py` |
| Z12 instructor AI tier 4 | merged (#53); background jobs in the `job` table, run by the worker | `app/instructor_ai/eval/`, `app/platform/jobs.py` |
| Z13 CI scans, `/metrics`, Prometheus, alerts, Grafana | merged (#49, #58); not deployed on the test host, no alert receiver chosen yet | `.github/workflows/ci.yml`, `app/platform/metrics.py`, `deploy/monitoring/` |
| Z14 manual and handover | merged (#50; this page, OPERATIONS.md); load test on the server outstanding | `docs/` |
| Z15 rule 14 in Z code | merged | `app/privacy/recognizers/` |

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
  exposed (guide 4.4). Counters exist; the v2 ask endpoint will call them.
- **CSRF**: on API v2 only; API v1 is frozen and its frontend predates it. The session token is derived from
  the HttpOnly session cookie; before login a double-submit cookie is used.
- **Credentials are redacted in every course** (`secret_token` in the base profile); lab addresses and
  repository URLs only in ECE.
- **Known scan findings** are listed with their reason in `backend/.pip-audit-ignore` (the bandit baseline
  is empty since #55 and #56); anything new fails CI.

## 4. Open work by owner

What Z did in other owners' areas (for their review): guide section 7.5.

| Owner | Task | Why it matters |
|---|---|---|
| S | `course_id` on the learner tables + an interface to export and delete one course's learner data | needed by end of term and export (Z9) and the v2 ask endpoint |
| T | `transformers` 5 together with Z | 6 pip-audit advisories ignored with reason |
| T | `react-router` 7 (moderate advisory), `vite`/`vitest` (dev tools); `README.md`, `frontend/README.md` and `docs/DEMO.md` still describe SQLite | CI reports the advisories |
| T | frontend for API v2 (T6, T7); a v2 client sends `X-CSRF-Token` | course management is API-only until then |
| Z | v2 ask endpoint (pipeline per course, usage checks); end of term and export | after S's interface |
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
