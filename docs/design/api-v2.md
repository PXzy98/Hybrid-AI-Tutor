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
| CSRF | Every state-changing request (POST, PUT, PATCH, DELETE), including the public `login` and `join`, sends header `X-CSRF-Token` with the value from `GET /api/v2/auth/csrf` (Z10). That endpoint is **public**: without a session it sets a short-lived anonymous CSRF cookie and returns the matching token (double-submit). Login issues a new token bound to the new session (also in the `X-CSRF-Token` header of the `login` and `join` responses), and logout clears it. A missing or wrong token is 403 with `code: csrf_failed`. `/api/v1` is frozen and does not check it (Z10). |
| Course scope | Course-scoped endpoints are under `/api/v2/courses/{course_id}/...`; access is checked by `require_course_role` before anything else. A course the caller cannot see returns **404**, not 403. |
| IDs | Integers for database objects; `student_id` stays a UUID string and is the only student identifier in learner endpoints. |
| Errors | `{"detail": "<human-readable English>", "code": "<machine_code>"}`; codes are listed in `backend/app/api/v2/errors.py`. |
| Pagination | `?limit=&cursor=`; responses `{"items": [...], "next_cursor": "..." or null}`. Default limit 50, maximum from `limits`. |
| Time | ISO 8601 UTC. |
| Language | Response text is English; the frontend translates UI strings (en, fr). |
| Uploads | `multipart/form-data`; limits from `limits.uploads`. |
| Streams | Server-sent events, `text/event-stream`, events `progress`, `token`, `final`, `error`. |
| Rate limits | 429 with `code: usage_limit` and `retry_after_seconds`. |
| Settings lock | 423 with `code: settings_applying` while a settings change is being applied (course-structure 6.5). |

## 3. Endpoints

Roles: **A** = admin, **I** = instructor member of the course, **S** = active student member, **any** =
logged in. Owner = component owner who implements it.

### 3.1 Auth and account (owner Z)

| Method and path | Who | Purpose |
|---|---|---|
| `POST /auth/login` | public | username or e-mail (field `username`) + password |
| `POST /auth/logout` | any | end session |
| `POST /auth/logout-all` | any | end every session of the account, on every device (Z10) |
| `GET /auth/me` | any | account, system role, memberships |
| `POST /auth/change-password` | any | ends all other sessions |
| `GET /auth/csrf` | public | CSRF token (anonymous before login, bound to the session after) |
| `POST /auth/join` | public or logged in | new student: invitation code + e-mail + display name + password creates the account and activates all his pending memberships; logged-in student: invitation code only, activates that course's pending membership (course-structure 3.3) |
| `GET /me/preferences`, `PUT /me/preferences` | S | global learning preferences |
| `GET /me/consent`, `PUT /me/consent` | S | global consent |

### 3.2 Admin (owner Z)

| Method and path | Who | Purpose |
|---|---|---|
| `GET /admin/instructors`, `POST /admin/instructors` | A | list, create instructor accounts |
| `PATCH /admin/instructors/{account_id}`, `POST /admin/instructors/{account_id}/reset-password` | A | deactivate, change role, reset |
| `GET /admin/settings`, `PUT /admin/settings` | A | system settings; `PUT` sends the `version` it read, 409 if it changed (course-structure 6.2) |
| `GET /admin/settings/history`, `POST /admin/settings/restore/{history_id}` | A | change history and undo |
| `GET /admin/settings/apply-status` | A | `apply_state`, target version, per-process progress and errors (course-structure 6.5); the page polls it while `applying` |
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
| `GET /courses/{course_id}/settings`, `PUT /courses/{course_id}/settings` | I | course settings (course-structure 6); `PUT` sends the `version` it read, 409 if it changed |
| `GET /courses/{course_id}/settings/history`, `POST /courses/{course_id}/settings/restore/{history_id}` | I | change history and undo |
| `GET/POST/PATCH /courses/{course_id}/model-endpoints[/{endpoint_id}]`, `POST .../test` | I | course model connections (Z6) |
| `GET /courses/{course_id}/members` | I | members (students and instructors) |
| `POST /courses/{course_id}/members/import` | I | CSV import, returns the import report |
| `POST /courses/{course_id}/members/instructors` | I | add a co-instructor by e-mail |
| `DELETE /courses/{course_id}/members/{member_id}` | I | remove a member |
| `POST /courses/{course_id}/members/{member_id}/reset-password` | I | temporary password for a student |
| `GET /courses/{course_id}/invite`, `POST /courses/{course_id}/invite/rotate` | I | invitation code: `GET` shows the code (stored encrypted with `SETTINGS_ENCRYPTION_KEY`; null without that key), its expiry and use count; `rotate` returns a new code |
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
| `GET /courses/{course_id}/jobs/{job_id}` | I | Z | background job status (also for quiz drafts, 3.9) |

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
| `GET /courses/{course_id}/quizzes`, `GET .../quizzes/{quiz_id}`, `POST .../quizzes/{quiz_id}/attempt` | S | Q1 | published quizzes assigned to the student, and answering one (3.9) |
| `GET /courses/{course_id}/survey`, `POST .../survey/responses` | S | Q1 | the end-of-term survey (3.10); there is no rating after an answer |

Notes on ask (implemented in `backend/app/api/v2/ask.py`):
- the response is the v1 answer plus `conversation_id`; the stream sends `meta`, `progress`, `result` or
  `error`, then `done`;
- without `module_id` the question is about the course as a whole: retrieval searches the whole course and
  no check item is attached;
- 429 `usage_limit` when the student reached the question limit of the course; when only the daily cloud
  limit is reached, the answer comes from the local model with a warning;
- a `conversation_id` of another student or another course is 404.

### 3.6 Instructor views of learners (owner S)

| Method and path | Who | Purpose |
|---|---|---|
| `GET /courses/{course_id}/class-summary` | I | aggregates (all modes) |
| `GET /courses/{course_id}/students/{student_id}/overview` | I | individual overview (mode B, not opted out, since `visible_since`; audited) |
| `GET/PUT /courses/{course_id}/students/{student_id}/plan` | I | learning plan (same conditions) |
| `GET /courses/{course_id}/insights` | I | class insights, tier 3 (labels and counts only) |
| `GET /courses/{course_id}/quizzes[/{quiz_id}[/results]]` | I | quizzes and their results (3.9) |
| `GET /courses/{course_id}/survey` | I | end-of-term survey averages (3.10) |

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
| `PUT /courses/{course_id}/ai/evaluations/{eval_id}/questions` | I | Z | the instructor's review of the generated questions (while `review`) |
| `POST /courses/{course_id}/ai/evaluations/{eval_id}/run` | I | Z | answer and score; needs `confirm_cloud: true` (course material goes to the cloud model); 409 in a local-only course |
| `PATCH /courses/{course_id}/ai/evaluations/{eval_id}/results/{question_id}` | I | Z | the instructor's spot check of one scored question |

### 3.9 Quizzes (task Q1)

Multiple choice and true/false questions, graded automatically, for progress only (never a grade). Code:
`backend/app/api/v2/quizzes.py`, `backend/app/learner/quizzes.py`, `backend/app/instructor_ai/quiz_drafts.py`;
rules: [course-structure.md](course-structure.md) 4.6. Callers outside the course get 404 on every endpoint
below (anonymous: 401); an instructor on the student endpoint (`attempt`) and a student on an instructor
endpoint get 404 as well.

| Method and path | Who | Purpose |
|---|---|---|
| `GET /courses/{course_id}/quizzes` | I, S | I: every quiz of the course (`QuizOut`, answers and explanations included, `attempts` count), newest first. S: only `published` or `closed` quizzes assigned to the student (`StudentQuizOut`) |
| `POST /courses/{course_id}/quizzes` | I | create a quiz (always a draft); 201 `QuizOut` |
| `GET /courses/{course_id}/quizzes/{quiz_id}` | I, S | one quiz (same two views); a draft or a quiz not assigned to the student is 404 for a student |
| `PATCH /courses/{course_id}/quizzes/{quiz_id}` | I | edit, publish (`status: "published"`) or close (`status: "closed"`) |
| `DELETE /courses/{course_id}/quizzes/{quiz_id}` | I | delete; 204 |
| `POST /courses/{course_id}/quizzes/{quiz_id}/drafts` | I | the local model drafts questions from the course material (background job); 202 `{job_id}` |
| `POST /courses/{course_id}/quizzes/{quiz_id}/attempt` | S | answer the quiz once; 201 `OwnAttempt` |
| `GET /courses/{course_id}/quizzes/{quiz_id}/results` | I | class aggregates, pre/post comparison, and the individual results the instructor may see |

Fields:
- `QuizIn` (create): `title` (1-200 characters), `module_id` (null: the whole course), `kind` (`practice` or
  `final`, default `practice`), `opens_at`, `closes_at` (both optional), `assigned_to` (list of `student_id`;
  null: every student), `questions` (at most 50). `QuizPatch` has the same fields plus `status`
  (`draft`, `published`, `closed`), all optional.
- A question (`QuizQuestion`): `kind` (`mcq` or `true_false`), `kc` (a KC code of the course or null),
  `stem` (3-900 characters), `options`, `answer` (index into `options`), `explanation` (at most 1000
  characters), `sources` (material file names, set by AI drafts), `reviewed`. A multiple choice question has 2
  to 6 distinct options of at most 300 characters; a true/false question always has the options `True`,
  `False` (sent options are replaced) and the answer 0 (True) or 1 (False). Unknown fields are rejected.
- `QuizOut`: `id`, `title`, `module_id`, `kind`, `status`, `opens_at`, `closes_at`, `assigned_to`,
  `questions` (full), `attempts`, `created_at`, `updated_at`.
- `StudentQuizOut`: `id`, `title`, `module_id`, `kind`, `open`, `opens_at`, `closes_at`, `questions`
  (`kind`, `stem`, `options` only: no answer, no explanation) and `attempt`. `questions` is filled only while the
  quiz is open **and** the student has not answered; `attempt` (`OwnAttempt`: `score`, `total`,
  `submitted_at`, `results` with `correct`, `chosen`, `answer`, `explanation` per question) is filled once
  the student has answered, also after the quiz closed. A quiz is open when it is `published` and now is
  inside `opens_at`/`closes_at` (an unset bound does not limit).

Behaviour:
- **Create and edit**: 404 when `module_id` is not a module of this course; 422 when `closes_at` is not after
  `opens_at` (on `PATCH` checked against the stored value of the field not sent), when a `kc` is not a KC code
  of the course, when there are more than 50 questions or when a question is invalid.
- **Review**: saving `questions` through `PATCH` marks every saved question `reviewed: true`. Publishing is
  409 when the quiz has no question or a question is still unreviewed (AI drafts).
- **After the first answer**: `PATCH` with `questions` is 409, setting `status` back to `draft` is 409, and
  `DELETE` is 409 (close the quiz instead). Title, window, assignment and the other `status` changes stay
  possible.
- **Drafts**: only a `draft` quiz (409 otherwise). Body: `count` (1-20, default 5), `kinds` (default both),
  `kc_codes` (optional, 422 when one is not a KC code of the course). The job `quiz.draft` runs on the local
  model only (trusted local connection; course material and KC codes go in, no student data), adds the
  valid questions with `reviewed: false` and the material file as `sources`, and keeps at most 50 questions.
  Poll `GET /courses/{course_id}/jobs/{job_id}`; the job fails when the model wrote no usable question.
- **Attempt**: `answers` is one index per question, in order. 404 when the quiz is a draft or not assigned to
  the student; 409 `the quiz is not open` (not yet open, past `closes_at`, or closed); 422 when the number of
  answers differs from the number of questions or an index is not an option; 409 `already answered` for a
  second attempt (one per student and quiz). The response carries the grading at once. For every question
  linked to a KC the answer is also given to the knowledge model as strong evidence (source `quiz`); without
  the student's consent nothing is stored there.
- **Results**: `attempts`; `sufficient_sample` (attempts at least `learner.class_summary_min_group`) with
  `min_group_size`; `mean_score` (share correct, 0 to 1) and `questions` (`position`, `kc`, `correct_rate`)
  only with a sufficient sample; for a `final` quiz `pre_post` (`students`, `pre_mean`, `post_mean`: the
  post-test against the same students' diagnostic answers; the means are null when fewer than the minimum
  group have both); `students`: one entry (`student_id`, `score`, `total`, `submitted_at`, and for a `final`
  quiz `pre_test`) for each student the instructor may see under the visibility rules (mode B, acknowledged,
  not opted out, attempt after `visible_since`; course-structure.md 4.5). Every individual view is written to
  the audit log (`learner.quiz_results.view`).

### 3.10 End-of-term survey (task Q1)

Replaces the rating after each answer. The instructor opens a time window; each student answers once inside
it. Ratings only, anonymous by design (course-structure.md 4.7). Code: `backend/app/api/v2/survey.py`. Callers
outside the course get 404 (anonymous: 401); an instructor on the student endpoint and a student on the
instructor endpoint get 404 as well.

| Method and path | Who | Purpose |
|---|---|---|
| `GET /courses/{course_id}/survey` | I, S | the window and whether it is open; I also gets the results, S gets `answered` |
| `PUT /courses/{course_id}/survey` | I | set the window (`opens_at`, `closes_at`); set again to change or close it; returns the same as `GET` |
| `POST /courses/{course_id}/survey/responses` | S | answer once; 201, returns the same as `GET` |

Fields:
- `SurveyOut`: `opens_at`, `closes_at` (null before a window was set), `open`, `answered` (students only),
  `results` (instructors only).
- Answer (`SurveyAnswers`): five integers from 1 to 5, no free text, unknown fields rejected:
  `helpfulness`, `material_relevance`, `clarity`, `source_confidence`, `learning_effect`.
- `results`: `responses`, `min_group_size` (3, `MIN_AGGREGATE_SIZE` of `api/v1/survey.py`),
  `sufficient_sample`, `means` (per item, two decimals; null below the minimum group).

Behaviour:
- `PUT`: 422 when `closes_at` is not after `opens_at`. One window per course.
- `POST`: 409 `the survey is not open` outside the window (also when no window was set); 409 `already
  answered`; 422 for a value outside 1-5, a missing item or an unknown field (for example a comment).
- Students never see results; instructors see averages only, never single answers.
- The end of term exports the averages (`survey.json`) and deletes the window, the answers and the record of
  who answered (course-structure.md 3.5).
- API v1 keeps `POST /api/v1/survey` and `GET /api/v1/admin/survey-summary` (frozen); the v2 frontend does not
  use them.

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
| `/api/v1/admin/class-summary`, `/admin/logs` | `/courses/{course_id}/class-summary`, `/logs` |
| `/api/v1/admin/survey-summary` | `GET /courses/{course_id}/survey` (instructor: `results`; end-of-term survey, 3.10) |
| `POST /api/v1/survey` (rating per topic after an answer) | no equivalent: replaced by `POST /courses/{course_id}/survey/responses` (end of term, 3.10) |
