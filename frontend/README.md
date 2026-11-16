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
| `/courses` | logged in | Course picker |
| `/admin` | administrators | Instructor accounts, system settings (versioned save), model connections (the link is only shown to administrators; the API enforces the role) |
| `/courses/:id/:tab` | students | Sections: chat, my progress (bands, visibility choices, read-only plan), personalize, quizzes, end-of-term survey; delete my learning data in this course |
| `/courses/:id/:tab` | instructors | Sections: class overview (with class insights), students (progress, plan editor), course content (modules, KCs, check items, misconceptions, YAML import and export), AI assistant (drafts, cloud evaluation), members (invitation code, CSV import), materials (upload, delete, index rebuild), settings (with the course's model connections and archiving), end of term, quizzes, end-of-term survey |

## Layout

`src/components/AppShell.tsx` is a full-height shell; only the content area scrolls.

- **Sidebar** (`src/components/shell/`, 264 px): brand, course switcher (a native select inside a course, links on
  `/courses`), join / new course / administration, then for the open course its sections
  (`src/pages/sections.ts`; instructors in the groups Class, Teaching, Course), the modules (the chat scope) and,
  for students, New chat and the conversations grouped by day. The account menu at the bottom holds language,
  theme (light, dark, system), change password and log out. The sidebar can be hidden on desktop
  (`localStorage` key `tutor.sidebar`) and is a sheet on screens narrower than `md`.
- **Top bar**: the sidebar button, the page `h1` (course code and title), the role and archived badges.
- **Disclaimer**: a muted `role="note"` line under the content.

`CourseDashboard.tsx` renders only the active section; a student's chat stays mounted (hidden) on other sections
so a running answer survives.

Everything uses `/api/v2`; every non-GET request sends `X-CSRF-Token` (`src/api/client.ts`). UI components are
shadcn/ui, copied into `src/components/ui/`. Answers are rendered as Markdown with KaTeX.

Identity is only the httpOnly session cookie; nothing about the user is kept in `localStorage`.
