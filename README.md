# Privacy-Aware Hybrid AI Tutor

A health-education tutor (ELG 5902, Group 1). Students pick one of five topics (High Blood Pressure, Type 2 Diabetes, Asthma, Migraine, Pneumonia) and ask questions. The system removes private information locally, then routes each question to a local model (Ollama) or a cloud model. Answers are grounded in course material (RAG) and adapted to what the student already knows. The tutor tracks the student's mastery of each knowledge component and adapts the level, the material and the check questions. Learning preferences only change how the answer is presented. The learner profile never leaves the local network.

- Design: [docs/System_Design_v3.md](docs/System_Design_v3.md) (diagrams in [docs/diagrams/](docs/diagrams/))
- Implementation plan, step by step: [docs/IMPLEMENTATION_PROMPTS.md](docs/IMPLEMENTATION_PROMPTS.md)
- Progress log: [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md)
- For teammates (routing, RAG): [docs/INTERFACES.md](docs/INTERFACES.md)

## Repository layout

| Path | Contents |
|---|---|
| `backend/` | FastAPI app (`app/`) and tests |
| `frontend/` | React + TypeScript web app (Step 9) |
| `content/topics/` | KCs, check questions, misconception catalog per topic (Step 5) |
| `config.yaml` | Pipeline steps, models, thresholds, learner settings |
| `.env` | Secrets and machine-specific URLs (copy from `.env.example`) |
| `eval/` | Evaluations; `model-boundary-test/` is done |
| `data/synthetic/` | Synthetic test data (fictional people only) |

## Development setup

Requirements: Python 3.12, Node 20+ (frontend, from Step 9). The commands below are for PowerShell; on bash use `.venv/bin/` (Linux/macOS) or `.venv/Scripts/` (Git Bash) instead of `.venv\Scripts\`.

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
