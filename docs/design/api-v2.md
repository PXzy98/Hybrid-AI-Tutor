# HTTP API v2

Status: **defined** (2026-11-04). Owner of this document: Z. Each endpoint group below names the
component owner who implements it. Data model and rules: [course-structure.md](course-structure.md).

---

## 1. Versioning

- **Base path: `/api/v2`.** All v4 work adds endpoints here.
- **`/api/v1` is frozen** from 2026-11-04: no new endpoints, no new fields, bug fixes only. It keeps working
  against the migrated demo course ("General Medical Knowledge") until the frontend has moved to v2 (T6, T7),
  then it is removed (target: Sprint S7). An agent must not add anything to `/api/v1`.
- **Within v2, only additive changes**: new endpoints, new optional request fields, new response fields.
  Renaming or removing a field, changing a type or making an optional field required is a breaking change
  and needs `/api/v3` (decided by Z).
- **The OpenAPI document is the contract.** After any API change run `python -m app.export_openapi` (in
  `backend/`) and `npm run gen:api` (in `frontend/`), and commit both `frontend/openapi.json` and
  `frontend/src/api/schema.d.ts` in the same PR.
- Every endpoint has an `operation_id` (`<group>_<action>`, e.g. `courses_create`) so the generated client
  names stay stable.

## 2. Conventions

| Topic | Rule |
|---|---|
| Authentication | Same server-side session cookie as v1 (`HttpOnly`, `Secure` in production, `SameSite=Lax`). |
| CSRF | Every state-changing request (POST, PUT, PATCH, DELETE) sends header `X-CSRF-Token` with the value from `GET /api/v2/auth/csrf` (Z10). |
| Course scope | Course-scoped endpoints are under `/api/v2/courses/{course_id}/...`; access is checked by `require_course_role` before anything else. A course the caller cannot see returns **404**, not 403. |
| IDs | Integers for database objects; `student_id` stays a UUID string and is the only student identifier in learner endpoints. |
| Errors | `{"detail": "<human-readable English>", "code": "<machine_code>"}`; codes are listed in `backend/app/api/v2/errors.py`. |
| Pagination | `?limit=&cursor=`; responses `{"items": [...], "next_cursor": "..." or null}`. Default limit 50, maximum from `limits`. |
| Time | ISO 8601 UTC. |
| Language | Response text is English; the frontend translates UI strings (en, fr). |
| Uploads | `multipart/form-data`; limits from `limits.uploads`. |
| Streams | Server-sent events, `text/event-stream`, events `progress`, `token`, `final`, `error`. |
| Rate limits | 429 with `code: usage_limit` and `retry_after_seconds`. |

## 3. Endpoints

Roles: **A** = admin, **I** = instructor member of the course, **S** = active student member, **any** =
logged in. Owner = component owner who implements it.

### 3.1 Auth and account (owner Z)

| Method and path | Who | Purpose |
|---|---|---|
| `POST /auth/login` | public | username or e-mail + password |
| `POST /auth/logout` | any | end session |
| `GET /auth/me` | any | account, system role, memberships |
| `POST /auth/change-password` | any | ends all other sessions |
| `GET /auth/csrf` | any | CSRF token |
| `POST /auth/join` | public | activate with invitation code + e-mail + display name + password (course-structure 3.3) |
| `GET /me/preferences`, `PUT /me/preferences` | S | global learning preferences |
| `GET /me/consent`, `PUT /me/consent` | S | global consent |

### 3.2 Admin (owner Z)

| Method and path | Who | Purpose |
|---|---|---|
| `GET /admin/instructors`, `POST /admin/instructors` | A | list, create instructor accounts |
| `PATCH /admin/instructors/{account_id}`, `POST /admin/instructors/{account_id}/reset-password` | A | deactivate, change role, reset |
| `GET /admin/settings`, `PUT /admin/settings` | A | system settings |
| `GET /admin/model-endpoints`, `POST /admin/model-endpoints`, `PATCH .../{endpoint_id}`, `POST .../{endpoint_id}/test` | A | system model connections (Z6) |

### 3.3 Courses, members, settings (owner Z)

| Method and path | Who | Purpose |
|---|---|---|
| `GET /courses` | any | courses the caller can see |
| `POST /courses` | A, instructor | create (creator becomes instructor member) |
| `GET /courses/{course_id}`, `PATCH /courses/{course_id}` | I (GET also S) | details, edit code/title/term label |
| `POST /courses/{course_id}/end-term` | I | export then delete student data (course-structure 3.5) |
| `GET /courses/{course_id}/exports/{export_id}` | I | download the export |
| `POST /courses/{course_id}/archive` | I | archive |
| `GET /courses/{course_id}/settings`, `PUT /courses/{course_id}/settings` | I | course settings (course-structure 6) |
| `GET/POST/PATCH /courses/{course_id}/model-endpoints[/{endpoint_id}]`, `POST .../test` | I | course model connections (Z6) |
| `GET /courses/{course_id}/members` | I | members (students and instructors) |
| `POST /courses/{course_id}/members/import` | I | CSV import, returns the import report |
| `POST /courses/{course_id}/members/instructors` | I | add a co-instructor by e-mail |
| `DELETE /courses/{course_id}/members/{member_id}` | I | remove a member |
| `POST /courses/{course_id}/members/{member_id}/reset-password` | I | temporary password for a student |
| `GET /courses/{course_id}/invite`, `POST /courses/{course_id}/invite/rotate` | I | invitation code |
| `GET /courses/{course_id}/usage` | I | usage summary of the course |
| `GET /courses/{course_id}/logs` | I | sanitized request logs |
| `GET /courses/{course_id}/audit` | I | audit log of the course |

### 3.4 Content (owner Z for modules and KCs, S for materials)

| Method and path | Who | Owner | Purpose |
|---|---|---|---|
| `GET /courses/{course_id}/modules` | I, S | Z | modules in order |
| `POST`, `PATCH`, `DELETE /courses/{course_id}/modules[/{module_id}]`, `POST .../modules/reorder` | I | Z | edit modules |
| `GET/POST/PATCH /courses/{course_id}/kcs[/{kc_id}]` | I | Z | KCs and prerequisites (retire instead of delete) |
| `GET/POST/PATCH /courses/{course_id}/check-items[/{item_id}]` | I | Z | check items |
| `GET/POST/PATCH /courses/{course_id}/misconceptions[/{misconception_id}]` | I | Z | misconceptions |
| `POST /courses/{course_id}/content/import`, `GET /courses/{course_id}/content/export` | I | Z | YAML import/export |
| `GET /courses/{course_id}/materials` | I | S | materials, scan and index status |
| `POST /courses/{course_id}/materials` | I | S | upload (field `module_id` optional = course-level) |
| `DELETE /courses/{course_id}/materials/{material_id}` | I | S | delete and re-index |
| `GET /courses/{course_id}/jobs/{job_id}` | I | Z | background job status |

### 3.5 Student learning (owner: ask Z, learner S)

| Method and path | Who | Owner | Purpose |
|---|---|---|---|
| `POST /courses/{course_id}/ask` | S | Z | ask (body: `question`, `module_id?`, `conversation_id?`, `routing_method?`) |
| `POST /courses/{course_id}/ask/stream` | S | Z | same, SSE |
| `POST /courses/{course_id}/check` | S | S | answer a check item |
| `GET /courses/{course_id}/conversations`, `GET .../conversations/{conversation_id}` | S | Z | own conversations in this course |
| `GET /courses/{course_id}/onboarding`, `POST /courses/{course_id}/onboarding` | S | S | course diagnostic |
| `GET /courses/{course_id}/me/profile` | S | S | "What I know" in this course, the visibility mode, what the instructor can see, the instructor's plan |
| `POST /courses/{course_id}/me/visibility` | S | S | acknowledge mode B, or opt out / opt back in |
| `DELETE /courses/{course_id}/me/learning-data` | S | S | delete own data in this course |
| `POST /courses/{course_id}/survey` | S | S | optional rating |

### 3.6 Instructor views of learners (owner S)

| Method and path | Who | Purpose |
|---|---|---|
| `GET /courses/{course_id}/class-summary` | I | aggregates (all modes) |
| `GET /courses/{course_id}/students/{student_id}/overview` | I | individual overview (mode B, not opted out, since `visible_since`; audited) |
| `GET/PUT /courses/{course_id}/students/{student_id}/plan` | I | learning plan (same conditions) |
| `GET /courses/{course_id}/insights` | I | class insights, tier 3 (labels and counts only) |
| `GET /courses/{course_id}/survey-summary` | I | survey averages (minimum group size from `limits`) |

### 3.7 Instructor AI (owner S for tiers 1–3, Z for tier 4)

| Method and path | Who | Owner | Purpose |
|---|---|---|---|
| `POST /courses/{course_id}/ai/drafts` | I | S | start a generation job (`kind`: `project_ideas`, `sample_proposal`, `faq`, `kcs`, `check_items`, `misconceptions`); returns a job |
| `GET /courses/{course_id}/ai/drafts`, `GET .../ai/drafts/{draft_id}` | I | S | drafts |
| `PATCH /courses/{course_id}/ai/drafts/{draft_id}` | I | S | edit a draft |
| `POST /courses/{course_id}/ai/drafts/{draft_id}/accept` | I | S | publish into the normal tables (or as a course document) |
| `DELETE /courses/{course_id}/ai/drafts/{draft_id}` | I | S | discard |
| `POST /courses/{course_id}/ai/evaluations` | I | Z | start a local vs cloud evaluation (tier 4); returns a job |
| `GET /courses/{course_id}/ai/evaluations[/{eval_id}]` | I | Z | reports |

### 3.8 Operations (owner Z)

| Method and path | Who | Purpose |
|---|---|---|
| `GET /health` | public | liveness and dependencies (database, local model, cloud model) without details |
| `GET /metrics` | internal network only (not routed by the proxy) | Prometheus metrics |

## 4. Mapping from v1

| v1 | v2 |
|---|---|
| `POST /api/v1/ask`, `/ask/stream` (`topic` in the body) | `POST /api/v2/courses/{course_id}/ask[/stream]` (`module_id` optional) |
| `GET /api/v1/topics` | `GET /api/v2/courses`, `GET /api/v2/courses/{course_id}/modules` |
| `GET/DELETE /api/v1/learner/me`, `POST /api/v1/learner/me/preferences` | `GET /courses/{course_id}/me/profile`, `DELETE /courses/{course_id}/me/learning-data`, `PUT /me/preferences` |
| `GET/POST /api/v1/onboarding` | `/courses/{course_id}/onboarding` |
| `POST /api/v1/check` | `/courses/{course_id}/check` |
| `GET /api/v1/sessions/{session_id}` | `/courses/{course_id}/conversations/{conversation_id}` |
| `/api/v1/admin/students...` | `/courses/{course_id}/members...` |
| `/api/v1/admin/config`, `/admin/llm-server/test` | `/courses/{course_id}/settings`, `/admin/settings`, `/admin/model-endpoints...` |
| `/api/v1/admin/topics/{topic}/materials`, `/admin/content` | `/courses/{course_id}/materials` |
| `/api/v1/admin/class-summary`, `/admin/logs`, `/admin/survey-summary` | `/courses/{course_id}/class-summary`, `/logs`, `/survey-summary` |
| `POST /api/v1/survey` | `/courses/{course_id}/survey` |
