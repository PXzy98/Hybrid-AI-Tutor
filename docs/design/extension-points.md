# Extension points for course-platform features (task V14)

Prof. Abbas sees PACT growing into "Brightspace plus": the course platform plus AI for teaching, research and
industry training. This term builds none of the platform features below (decision of 2026-11-17); this note
shows the next team where each one plugs in, so it can be added without changing what exists. Read with
[course-structure.md](course-structure.md) (data, roles, settings) and [api-v2.md](api-v2.md) (HTTP API). The
last section (V19) is about a different kind of extension: a new course type.

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

## A new course type as one package (task V19)

**Status: design agreed by Z (2026-11-20); plan items 1 to 6 built (PR for V19, task V19); no type has its own heads yet.** A course has one course type (`courses.course_type`). A new
type should be a set of files another team adds, without changes to the core.

### What a type selects today

| Part | Where | Selected by the type? |
|---|---|---|
| Privacy profile: PII recognizers, health-detail policy, checkers, medical disclaimer, consent note, subject prompt | `backend/app/privacy/profiles/<type>.yaml` (`extends: base`), recognizers `@pii_recognizers.register`, checkers `@checkers.register`, prompt `app/prompts/subjects/<prompt>.md` | yes; an unknown name stops the app when the profile loads |
| Web search sites and engines | `websearch.allowlist`, `websearch.searxng_engines` in `config.yaml` | yes |
| Retrieval and the evidence step | the course's own index | per course |
| Router (cloud need, evidence need, freshness heads; logistics or concept) | one `routing.impl` per deployment (`@routers.register`), heads in `data/routing/models/` trained on medical questions (T15) | **no**: `RouteInput` has no course type |

So heads trained on medical questions also decide for ECE and CS courses; the routing test of 2026-11-20
(`eval/routing-ece/`) measured ECE questions with them.

### Plan

1. **`RouteInput.course_type: str | None = None`** (additive). `route_input()` in
   `app/pipeline/steps/analyze_route.py` fills it from `ctx.settings.course_type`; the non-semantic call in
   `route.py` too. A router that ignores it behaves as now.
2. **Heads per type.** `weights_path(cfg, method, course_type)` (`app/routing/models.py`) returns
   `<model_dir>/<type>/semantic_<method>.npz` when that file exists, otherwise the current
   `<model_dir>/semantic_<method>.npz`; `question_type.weights_path` the same for `question_type.npz`. A type
   name is checked against the profile names (`[a-z_]+`, one of `profile_names()`) before it becomes a path.
   `SemanticRouter.classify(vector, method, course_type=None)` passes it on; `AnalyzeRouteStep` hands it over.
   Existing types have no folder, so they route exactly as today.
3. **Another router for one type** (optional): `routing.by_course_type: {<type>: <impl>}` in `config.yaml`,
   empty by default. `Services` loads each named router once; `RouteStep` and `AnalyzeRouteStep` use the
   type's router when there is one, `routing.impl` otherwise. Rarely needed: trained heads behind the shared
   semantic router are the useful part.
4. **Training per type.** `python -m app.routing.train --data <questions.jsonl> --course-type <type>` writes
   `data/routing/models/<type>/` (the same format, `metadata.course_type` added); without `--course-type` it
   writes the shared heads as now. The question set uses the labels of `data/routing/seed.jsonl`
   (`cloud_required`, `requires_evidence`, `requires_fresh_evidence`, `label_origin`).
5. **Evaluation per type.** `eval/routing-ece/run.py` (and the main routing evaluation) report each type
   with the heads it would get: its own when the folder exists, the shared ones otherwise, side by side.
6. **The cloud gate still decides last.** Routing only proposes local or cloud. Every cloud request still goes
   through `CloudRequest` and the cloud gate in the generate step (personal health, leak guard, `local_only`
   courses), whatever router or heads a type uses; a type's heads cannot send original text to the cloud
   (rule 2).

Tests for the code (second PR): a type without its own folder routes exactly as now (same scores as the shared
heads); a type with a folder uses its heads; an unknown or path-like type falls back to the shared heads;
`routing.by_course_type` picks the named router; a question a type's heads send to the cloud still meets the
cloud gate (personal health detail stays local, `local_only` course stays local). If there is time: ECE heads
trained from `data/routing/ece_cs_questions.jsonl` with the seed rows, before and after on the held-out share
(`eval/routing-ece/`).

### Checklist: adding a course type

1. **Privacy profile** `backend/app/privacy/profiles/<type>.yaml` with `extends: base`: recognizers, checkers,
   `health_detail_policy`, `medical_disclaimer`, `consent_note`, `prompt`. Only add to the base rules.
2. **New recognizers or checkers** in `app/privacy/recognizers/` or `app/verify/checkers/`, registered by name, with
   unit tests on fictional text (positives and course text that must stay).
3. **Subject prompt** `backend/app/prompts/subjects/<prompt>.md`.
4. **Web search** sites in `websearch.allowlist.<type>` and engines in `websearch.searxng_engines.<type>`
   (`config.yaml`); without them the type gets the default list.
5. **Routing heads** (optional): a labelled question set for the subject, `train.py --course-type <type>`,
   the evaluation per type, and the folder `data/routing/models/<type>/` committed with its
   `training_report.json`. Without them the shared heads decide.
6. **Privacy evaluation**: a held-out set written blind from the profile YAML (as
   `eval/privacy-filter/make_course_sets.py`), scored with `course_sets.py`, and a full E6 run (rule 4) in
   the PR.
7. **Enable** the type in the admin settings (`enabled_course_types`); a demo course pack and its manifest
   if one exists.
8. **Tests**: the profile loads; a course of the type gets its prompt, consent note and recognizers; access
   and routing tests as above.

## What must stay true
- Privacy rules (guide section 2): no question text stored or logged; original text and learner profiles only
  to a trusted local model; every endpoint checks the course role; the frontend decides no permission.
- Instructors see class statistics only unless the client asks otherwise (V1, `learner.instructor_individual_view`).
- Each feature's student data is deleted at the end of term and exported first (`end_of_term.py`).
