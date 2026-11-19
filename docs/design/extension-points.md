# Extension points for course-platform features (task V14)

Prof. Abbas sees PACT growing into "Brightspace plus": the course platform plus AI for teaching, research and
industry training. This term builds none of the platform features below (decision of 2026-11-17); this note
shows the next team where each one plugs in, so it can be added without changing what exists. Read with
[course-structure.md](course-structure.md) (data, roles, settings) and [api-v2.md](api-v2.md) (HTTP API).

## The four places every feature touches

| Place | What exists | How a feature plugs in |
|---|---|---|
| Data model | `backend/app/storage/models.py`; every course row has `course_id` with `ondelete="CASCADE"`; Alembic revisions in `backend/alembic/versions/` (one per change, numbered) | new tables keyed by `course_id` (and `account_id` or the pseudonymous `student_id` for people); a new migration; add the student tables to `end_of_term.STUDENT_TABLES` and to the export if they hold student data |
| API | `backend/app/api/v2/<group>.py`, each with its own `router`, included in `app/api/v2/__init__.py`; course routes live under `/courses/{course_id}/...` | a new module and one `include_router` line; additive only (rule 8); `python -m app.export_openapi` and `npm run gen:api` |
| Permissions | `require_course_role("instructor" \| "student")` and `require_system_role("admin" \| "instructor")` in `app/platform/access.py`; a refusal is 404 so other courses are not revealed | every route starts with one of them (rule 3), and gets access tests (rule 9); a new role (for example a TA) is a new value of `CourseMember.role` plus the places that list roles |
| Frontend | the course page sections in `frontend/src/pages/sections.ts` (`STUDENT_SECTIONS`, `INSTRUCTOR_SECTIONS`), rendered in `pages/CourseDashboard.tsx`; texts in `src/i18n/en.ts` and `fr.ts` | a section entry (id, label, icon) and a `case` in `sectionNode`; an `individual: true` flag hides a section that shows one student's data while the deployment allows only statistics (V1) |

Background work (long jobs such as grading a batch or importing a gradebook) uses the job queue:
`@jobs.handler("<kind>")` in a module listed in `HANDLER_MODULES` (`app/platform/jobs.py`), started with
`jobs.enqueue(...)` and polled through `GET /courses/{id}/jobs/{job_id}`.

## The features

### Assignments with upload links
- Data: `assignment` (course_id, module_id, title, instructions, opens_at, due_at, max_bytes, status) and
  `submission` (assignment_id, student_id, file name, size, sha256, submitted_at, status). Files under
  `data/courses/<id>/submissions/<assignment>/` like materials (`index_jobs.store` shows the pattern: exclusive
  create, size limit, a database row).
- API: `/courses/{id}/assignments` (instructor: create, edit, list submissions; student: list, submit own).
- Privacy: a submission is student work, not course material: never indexed for answers, never sent to a model
  without the student's consent, deleted at the end of term with the other student tables.

### Grading
- Data: `grade` (assignment_id or quiz_id, student_id, score, max, feedback, graded_by, released_at). Quizzes
  today are progress checks, explicitly not grades (course-structure.md 4.6); grades are a separate table.
- Permissions: a student sees only their released grades; an instructor sees their course's. This is
  individual data by nature, so it is outside the statistics-only rule only because grading is the
  instructor's job; keep it out of every AI prompt and out of the learner model.

### Announcements
- Data: `announcement` (course_id, title, body, published_at, author_id); optional per module.
- API: `/courses/{id}/announcements`; a student list and an instructor editor; the body is Markdown rendered
  with the existing safe renderer (`components/Markdown`, no raw HTML).
- AI: announcements are course material the tutor may cite: write them as a Markdown material
  (`index_jobs.store` and `request_rebuild`) when they are published.

### Running inside Brightspace (LTI 1.3)
- Login: `LoginIdentity` already separates the account from how it signs in (`provider`, opaque `subject`);
  an LTI launch adds `provider = "lti"` and the platform's subject ID, and maps the LTI context to a course
  (a `course_platform_link` table: course_id, platform issuer, context ID).
- Roles: LTI roles map to `CourseMember.role` at launch; the course stays the permission boundary.
- Grade passback (LTI Advantage AGS) would send `grade` rows, never learner-model data.

### University login (Microsoft Entra ID / OAuth)
- `provider = "entra"`, `subject` = the token's `oid`; accounts are matched by the verified e-mail on first
  login (`AccountService`), then by the subject. The password login stays for accounts without it.
- The session, CSRF and role checks do not change: only `POST /auth/login` gains a sibling
  `GET /auth/oidc/callback`.

## What must stay true
- Privacy rules (guide section 2): no question text stored or logged; original text and learner profiles only
  to a trusted local model; every endpoint checks the course role; the frontend decides no permission.
- Instructors see class statistics only unless the client asks otherwise (V1, `learner.instructor_individual_view`).
- Each feature's student data is deleted at the end of term and exported first (`end_of_term.py`).
