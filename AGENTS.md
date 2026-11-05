# Instructions for coding agents

This repository is the Privacy-Aware Hybrid AI Tutor (ELG 5902, Group 1). It is being turned into a
multi-course product ("v4").

## Read first

1. [docs/v4-implementation-guide.md](docs/v4-implementation-guide.md): rules, code map, target architecture,
   owners, tasks, workflow. **It is the source of truth; follow it over anything else in the repository.**
2. [docs/design/course-structure.md](docs/design/course-structure.md) and
   [docs/design/api-v2.md](docs/design/api-v2.md) when your task touches courses, accounts, learner data,
   settings, the database or the HTTP API.
3. [docs/IMPLEMENTATION_LOG.md](docs/IMPLEMENTATION_LOG.md) for how the current code came about.

All repository source files and documents must be in English; no Chinese companion files.
`docs/history/` is out of date.

## Before you change anything

- Work on **one task ID** from section 7 of the guide (for example `Z4`). If the user did not give one, ask.
- Check the task's owner and only change files of that owner's components (guide section 5,
  `.github/CODEOWNERS`). Need something from another component? Use the interfaces in guide section 6; if one
  is missing, stop and say so instead of editing another owner's code.
- Check that the tasks it depends on are merged.

## Rules you must not break (summary; full text in guide section 2)

1. Never store or log question text; `privacy.log_raw_text` stays `false`.
2. Original text and learner profiles only go to a model connection marked trusted local; everything sent
   to an external model passes the cloud gate.
3. Every endpoint checks the caller's role in the course; the frontend never decides permissions.
4. Privacy rule changes re-run E6 (`eval/privacy-filter/`) and must not make it worse.
5. Web search queries only come from `search_query()`.
6. No secrets in the repository: keys live only in the developer's own `.env`. Send only fictional data to
   hosted model APIs. Unit tests never call a real model (use `backend/app/llm/fake.py`).
7. English-only source, comments, test fixtures, Markdown (including `docs/`), filenames, commits and PRs. Use Unicode escapes for multilingual test inputs; run `python scripts/check_english_only.py`.
8. New endpoints go to `/api/v2` only; `/api/v1` is frozen. Within v2 only additive changes.
9. Every new endpoint has access tests (another course's instructor, another student, logged out).

## Workflow

- Branch: `<type>/<task-id>-<short-name>` from `main`; one task per PR; fill in the PR template.
- Commit messages: `<scope>: <what>` in English.
- Backend (in `backend/`), without a developer `.env` affecting the run:
  `python -m pytest -q`, `TEST_LEARNER_KNOWLEDGE=rule python -m pytest -q`, `python -m ruff check . ../scripts`
  (line length 110).
- After an API change: `python -m app.export_openapi` (in `backend/`), then `npm run gen:api` (in
  `frontend/`), and commit both generated files.
- Frontend (in `frontend/`): `npm run build && npm test`.
- Match the style of the surrounding code: comment density, naming, idioms.
