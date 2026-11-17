# PACT: Privacy-Aware Course Tutor

PACT is a course tutor for any subject (ELG 5902, Group 1). Instructors create courses, import their class list and
upload their material; students ask questions about the course. The system removes personal information
locally, then routes each question to a local model the course controls or to a cloud model. Answers cite the
course material and adapt to what the student already knows. Original questions and learner profiles never
leave the course's own servers, and question text is never stored.

What it does (v4):
- **Courses and modules** for any subject; the course type (medical science, life science, ECE, general) picks
  the privacy rules. Class list import (CSV) and invitation codes.
- **Ask**: privacy filter, semantic router (local or cloud; concept or logistics question), retrieval over the
  course's own material, answer checks, a local/cloud label on every answer.
- **Learner model** per course, a diagnostic, quizzes (AI drafts reviewed by the instructor) and an end-of-term
  survey.
- **Instructor dashboard**: class overview and class insights, each student's progress when the course allows
  it (visibility mode B; students can opt out), learning plans, AI drafts of course content, local versus cloud
  evaluation, end of term (export, then delete the course's student data).
- **One Docker Compose stack** (Caddy, FastAPI, worker, PostgreSQL, optional monitoring); the local model
  (vLLM or Ollama) runs separately and is reached by URL.

## Start here

| For | Read |
|---|---|
| Everyone working on the code, and coding agents | [AGENTS.md](AGENTS.md), then [docs/v4-implementation-guide.md](docs/v4-implementation-guide.md) (rules, architecture, owners, tasks) |
| State of the work, decisions, open tasks | [docs/HANDOVER.md](docs/HANDOVER.md), [TODO.md](TODO.md) |
| Deploying and running | [docs/OPERATIONS.md](docs/OPERATIONS.md), [deploy/README.md](deploy/README.md) |
| Courses, accounts, settings, data model; the HTTP API | [docs/design/course-structure.md](docs/design/course-structure.md), [docs/design/api-v2.md](docs/design/api-v2.md) |
| Web search (off, hosted API or SearXNG) | [docs/WEB_SEARCH.md](docs/WEB_SEARCH.md) |
| Privacy rules and their evaluation | [docs/PRIVACY_PROFILES.md](docs/PRIVACY_PROFILES.md), [eval/privacy-filter/](eval/privacy-filter/) |
| Model connections | [docs/MODEL_CONNECTIONS.md](docs/MODEL_CONNECTIONS.md) |
| Database and migrations | [docs/DATABASE.md](docs/DATABASE.md) |
| Using the tutor | [docs/STUDENT_MANUAL.md](docs/STUDENT_MANUAL.md), [docs/INSTRUCTOR_MANUAL.md](docs/INSTRUCTOR_MANUAL.md) |
| Demo and test courses | [data/demo_courses/README.md](data/demo_courses/README.md) |
| How the code came about | [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md); older documents in [docs/history/](docs/history/) |

## Quick start (Docker)

Requirements: Docker with Compose v2, and a local model server (vLLM or Ollama) the course controls.

```bash
cp .env.example .env    # set POSTGRES_PASSWORD, OLLAMA_URL, INSTRUCTOR_USERNAME, INSTRUCTOR_INITIAL_PASSWORD
docker compose up -d --build
```

- Services: `proxy` (Caddy: the web app, `/api` forwarded to `api`, HTTPS once `SITE_ADDRESS` is a domain
  name), `api` (FastAPI; applies the database migrations at startup), `worker` (indexing, AI drafts,
  evaluations, the live settings switch), `db` (PostgreSQL 16, internal network only). `--profile monitoring`
  adds Prometheus, Alertmanager and Grafana; `--profile searxng` adds a self-hosted search engine for web
  search, which is off by default ([docs/WEB_SEARCH.md](docs/WEB_SEARCH.md)).
- The first account (`INSTRUCTOR_USERNAME`) is the admin and must choose a new password at first login; it then
  creates instructor accounts and model connections. Production settings, upgrades and backups:
  [docs/OPERATIONS.md](docs/OPERATIONS.md).
- `docker-compose.override.yml` is for local development (it publishes the database on `127.0.0.1:5432`);
  production uses `docker compose -f docker-compose.yml`.
- Demo courses from the open course packs, built through the API: `python scripts/build_demo.py`
  ([data/demo_courses/README.md](data/demo_courses/README.md)).

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/`), Alembic migrations, tests |
| `frontend/` | React 19 + TypeScript, Tailwind CSS 4, shadcn/ui, on API v2 (see [frontend/README.md](frontend/README.md)) |
| `deploy/` | Caddy and monitoring configuration |
| `data/demo_courses/` | the eight open course packs (zips) used by evaluations, integration tests and demos |
| `data/routing/` | routing training data and weights |
| `content/` | the fictional v3 course content (YAML import format) |
| `eval/` | evaluations: privacy filter (E6), routing, retrieval, learner model, model comparison, load test |
| `scripts/` | demo build, course pack download, v3 migration, content export |
| `config.yaml` | pipeline steps, models, thresholds, hard limits; any value can be overridden in `.env` as `SECTION__FIELD` |

## Development

Requirements: Python 3.12, Node 20+, PostgreSQL for the backend tests. On bash use `.venv/bin/` (Linux, macOS)
or `.venv/Scripts/` (Git Bash) instead of `.venv\Scripts\`.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "backend[dev]"
.venv\Scripts\python -m spacy download en_core_web_sm   # tests; production uses en_core_web_lg
cd backend; ..\.venv\Scripts\python -m app.routing.prepare; cd ..   # routing and evidence models, about 600 MB
Copy-Item .env.example .env                              # keys and passwords live only here
```

- **spaCy model**: the server refuses to start without the model named in `config.yaml`
  (`privacy.spacy_model`, default `en_core_web_lg`) and never downloads it by itself. For quick local work set
  `PRIVACY__SPACY_MODEL=en_core_web_sm` in `.env`.
- **Routing and evidence models** run offline (`routing.local_files_only: true`). Without them the app still
  works: the router picks the cloud with the reason in its diagnostics, and passages are marked "not checked
  for relevance".
- **Cloud model**: any OpenAI-compatible API in `.env` (`CLOUD_BASE_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL`); the
  provider is chosen by the client. The cloud only receives text that passed the cloud gate; without a key the
  local model answers. Send only fictional data to hosted APIs while developing.

Run in development mode (two terminals):

```powershell
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --reload     # http://localhost:8000/docs
cd frontend; npm install; npm run dev                                   # http://localhost:5173
```

Checks (tests need `TEST_DATABASE_URL`, see [docs/DATABASE.md](docs/DATABASE.md); they ignore the developer's
`.env`):

```powershell
cd backend
..\.venv\Scripts\python -m pytest -q
$env:TEST_LEARNER_KNOWLEDGE="rule"; ..\.venv\Scripts\python -m pytest -q; Remove-Item Env:TEST_LEARNER_KNOWLEDGE
..\.venv\Scripts\python -m ruff check . ../scripts
cd ..\frontend
npm run build; npm test
```

Tests run offline; the few that need the local model server or a cloud key are marked (`-m ollama`,
`-m cloud`). Before using the course packs: `python scripts/fetch_open_courses.py unpack` (never commit the
unpacked folders).

Accounts from the command line (from `backend/`): `..\.venv\Scripts\python -m app.auth.cli create-instructor
<username>`, and `set-password <username>` for recovery (it also clears a lockout).

## Team

| Who | Components |
|---|---|
| Zhenyan Xing | platform (accounts, courses, settings, API, database), privacy, model gateway and LLM deployment, Docker and operations |
| Siyun Tan | retrieval and course content, instructor AI tiers 1 to 3, learner model (backend) |
| Tongkai Liu | routing and web search, frontend and user experience, demo material and manuals |

Owners per component: guide section 5 and `.github/CODEOWNERS`.
