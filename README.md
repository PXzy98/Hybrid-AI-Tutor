# Integrated main + RAG + semantic routing (v3)

完整保留教师后台，合并真实医学 RAG 和 500 题 LR/SVM routing。
Windows 首次运行请看 [开始使用.md](开始使用.md)（English: [GETTING_STARTED.md](GETTING_STARTED.md)），版本来源与限制见 [docs/INTEGRATION.md](docs/INTEGRATION.md)。
安装：Python 3.12 运行 `setup_local.py`；启动：分别运行 `start_backend.ps1` 与 `start_frontend.ps1`。

---

以下为主分支原有项目说明：

# Privacy-Aware Hybrid AI Tutor

A health-education tutor (ELG 5902, Group 1). Students pick one of five topics (High Blood Pressure, Type 2 Diabetes, Asthma, Migraine, Pneumonia) and ask questions. The system removes private information locally, then routes each question to a local model (Ollama) or a cloud model. Answers are grounded in course material (RAG) and adapted to what the student already knows. The tutor tracks the student's mastery of each knowledge component and adapts the level, the material and the check questions. Learning preferences only change how the answer is presented. The learner profile never leaves the local network.

- Design: [docs/System_Design_v3.md](docs/System_Design_v3.md) (diagrams in [docs/diagrams/](docs/diagrams/))
- Implementation plan, step by step: [docs/IMPLEMENTATION_PROMPTS.md](docs/IMPLEMENTATION_PROMPTS.md)
- Progress log: [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md)
- For teammates (routing, RAG): [docs/INTERFACES.md](docs/INTERFACES.md)
- MVP status: [docs/MVP_CHECKLIST.md](docs/MVP_CHECKLIST.md) · demo script: [docs/DEMO.md](docs/DEMO.md)
- Privacy: [docs/report/privacy_subsystem.md](docs/report/privacy_subsystem.md) (evaluation, design, test results) · planned upgrades: [docs/隐私升级.md](docs/隐私升级.md)
- Routing and RAG as integrated: [docs/ROUTING_PATCH.md](docs/ROUTING_PATCH.md), [docs/RAG_INTEGRATION.md](docs/RAG_INTEGRATION.md); differences from the design: [System_Design_v3.md §16](docs/System_Design_v3.md)

## Quick start (Docker)

Requirements: Docker with Compose, and the Ollama GPU server on the network (`OLLAMA_URL`).

```powershell
Copy-Item .env.example .env       # set OLLAMA_URL, INSTRUCTOR_USERNAME, INSTRUCTOR_INITIAL_PASSWORD
docker compose up --build -d      # http://localhost:8080 (WEB_PORT changes the port)
```

- `api`: FastAPI with the privacy filter and the learner model; SQLite lives in the `tutor-data` volume.
- `web`: nginx serving the React app and proxying `/api` to `api`. The browser sees one origin.
- The first build downloads the spaCy model `en_core_web_lg` (about 400 MB). `SPACY_MODEL=en_core_web_sm` gives a smaller image.
- Log in as the instructor, choose a new password, then create students (API `/api/v1/admin/students` until the dashboard of Step 13). For a demo with three prepared students, see [docs/DEMO.md](docs/DEMO.md).
- Any `config.yaml` value can be overridden in `.env` as `SECTION__FIELD`, e.g. `CONTENT__SERVE_UNREVIEWED=true` (needed while the course content is unreviewed) or `ROUTING__THRESHOLD=0.7`.
- `docker compose down` stops the app; `docker compose down -v` also deletes all accounts and data.
- Known gap: the image does not yet contain the routing and evidence models (see below). Without them the app still answers, but routing selects the cloud and course sources are marked "not checked".

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/`) and tests |
| `frontend/` | React + TypeScript web app (see `frontend/README.md`) |
| `content/topics/` | KCs, check questions, misconception catalog per topic |
| `scripts/` | Content review export, demo seeding |
| `config.yaml` | Pipeline steps, models, thresholds, learner settings |
| `.env` | Secrets and machine-specific URLs (copy from `.env.example`) |
| `eval/` | Evaluations; `model-boundary-test/` is done |
| `data/synthetic/` | Synthetic test data (fictional people only) |

## Development setup (without Docker)

Requirements: Python 3.12, Node 20+. The commands below are for PowerShell; on bash use `.venv/bin/` (Linux/macOS) or `.venv/Scripts/` (Git Bash) instead of `.venv\Scripts\`.

```powershell
python -m venv .venv
.venv\Scripts\python -m pip install -e "backend[dev]"
.venv\Scripts\python -m spacy download en_core_web_sm   # tests; production uses en_core_web_lg
Copy-Item .env.example .env                              # then fill in what you need
```

Run the checks from `backend/`:

```powershell
cd backend
..\.venv\Scripts\python -m ruff check .
..\.venv\Scripts\python -m pytest -q
```

### spaCy model for the privacy filter

The server refuses to start without the spaCy model named in `config.yaml` (`privacy.spacy_model`, default `en_core_web_lg`, about 400 MB). It never downloads it by itself.

```powershell
.venv\Scripts\python -m spacy download en_core_web_lg
```

For quick local development you can use the small model instead: set `PRIVACY__SPACY_MODEL=en_core_web_sm` in `.env`. Tests always use the small model.

### Routing and evidence models

The semantic router and the evidence check run locally and offline (`routing.local_files_only: true`). Download their models once (MiniLM sentence encoder and two cross-encoders, about 600 MB in the Hugging Face cache):

```powershell
cd backend; ..\.venv\Scripts\python -m app.routing.prepare
```

Without them the app still works: the router selects the cloud with the reason in its diagnostics, and the retrieved course passages are used but marked "not checked for relevance" (one warning in the server log).

### Cloud model

Any OpenAI-compatible API, set in `.env` (never commit keys):

```
CLOUD_BASE_URL=https://api.deepseek.com      # example: DeepSeek, tested Oct 19, 2026
CLOUD_API_KEY=...
CLOUD_MODEL=deepseek-flash
```

The cloud only receives the sanitized question, the topic, course passages and three coarse labels; questions with a personal health detail stay local (`privacy.health_detail_policy`). Without a key, or when the cloud fails, the local model answers and the student is told why. Reasoning models count their hidden reasoning against `llm.cloud.max_tokens` (2000). Check the provider's data location and retention with the client before a pilot (DeepSeek stores data in China): see [docs/隐私升级.md](docs/隐私升级.md).

Run the app in development mode (two terminals):

```powershell
cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app --reload     # http://localhost:8000/docs
cd frontend; npm install; npm run dev                                   # http://localhost:5173
```

### First instructor account

There is no self-registration: the instructor creates student accounts. To create the first instructor, set `INSTRUCTOR_USERNAME` and `INSTRUCTOR_INITIAL_PASSWORD` in `.env` before the first start; that password must be changed at first login. Alternatively, run from `backend/`:

```powershell
..\.venv\Scripts\python -m app.auth.cli create-instructor <username>
..\.venv\Scripts\python -m app.auth.cli set-password <username>      # recovery: also clears a lockout
```

Tests run offline by default. Tests that need the Ollama server or a cloud key are marked; run them with `-m ollama` or `-m cloud`.

## Team

- Zhenyan: privacy filter, learner model, pipeline, API, frontend
- Tongkai: routing score (plugs in via `routing.impl`)
- Siyun: RAG retrieval (plugs in via `rag.impl`)
