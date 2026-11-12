# Frontend

React + TypeScript (Vite), Tailwind CSS, React Router, TanStack Query. shadcn/ui, API v2.

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
| `/login` | everyone | Log in with username or e-mail |
| `/join` | everyone | Join a course with an invitation code (new students also create their account) |
| `/change-password` | everyone | Forced after a temporary password |
| `/courses` | logged in | Course picker; the left sidebar lists courses, modules and the student's conversations |
| `/courses/:id/:tab` | students | Tabs: chat, my progress (bands, visibility choices, read-only plan), personalize, quizzes, end-of-term survey |
| `/courses/:id/:tab` | instructors | Tabs: class overview, students (progress, plan editor), course content, members (invitation code, CSV import), settings, end of term, quizzes, end-of-term survey |

Everything uses `/api/v2`; every non-GET request sends `X-CSRF-Token` (`src/api/client.ts`). UI components are
shadcn/ui, copied into `src/components/ui/`. Answers are rendered as Markdown with KaTeX.

Identity is only the httpOnly session cookie; nothing about the user is kept in `localStorage`.
