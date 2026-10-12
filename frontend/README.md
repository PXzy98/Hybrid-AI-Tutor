# Frontend

React + TypeScript (Vite), Tailwind CSS, React Router, TanStack Query. Design: docs/System_Design_v3.md.

## Run

```powershell
npm install
npm run dev        # http://localhost:5173 ; /api is proxied to the backend on http://localhost:8000
```

Start the backend first (from `backend/`: `..\.venv\Scripts\python -m uvicorn app.main:app --reload`). For local
development with unreviewed content, point `APP_CONFIG` at a copy of `config.yaml` with
`content.serve_unreviewed: true` (and `privacy.spacy_model: en_core_web_sm` if the large model is not installed).

## Other commands

| Command | What it does |
|---|---|
| `npm run build` | Type-check and build into `dist/` |
| `npm test` | Vitest (jsdom) |
| `npm run gen:api` | Regenerate `src/api/schema.d.ts` from `openapi.json` |

After a backend API change: from `backend/`, run `..\.venv\Scripts\python -m app.export_openapi`, then
`npm run gen:api`. Both `openapi.json` and `src/api/schema.d.ts` are committed, so CI builds without the backend.

## Pages

| Path | Who | What |
|---|---|---|
| `/login` | everyone | Log in (accounts are created by the instructor) |
| `/change-password` | everyone | Forced after a temporary password |
| `/start` | students | Consent, 2 preference questions, diagnostic (every part optional) |
| `/chat` | students | Topic picker, answers with sources, level badge, check questions, presentation feedback |
| `/me` | students | "What I know": bands per knowledge component, reset |
| `/admin` | instructor | Placeholder until the dashboard (Step 13) |

Identity is only the httpOnly session cookie; nothing about the user is kept in `localStorage`.
