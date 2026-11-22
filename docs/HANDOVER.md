# Handover (task Z14)

State of the v4 work on 2026-11-17 and of v5 on 2026-11-20, for whoever continues it. The rules, owners and task list are in
[v4-implementation-guide.md](v4-implementation-guide.md) (the source of truth); this page says where things
stand and where to look. Running the system: [OPERATIONS.md](OPERATIONS.md).

## 1. Where to read what

| Topic | Document |
|---|---|
| Rules, owners, tasks, workflow | [v4-implementation-guide.md](v4-implementation-guide.md), `AGENTS.md` |
| Courses, roles, enrollment, settings, data model | [design/course-structure.md](design/course-structure.md) |
| HTTP API v2 (the contract) | [design/api-v2.md](design/api-v2.md), `frontend/openapi.json` |
| Database, migrations, the demo course | [DATABASE.md](DATABASE.md) |
| Model connections and the gateway | [MODEL_CONNECTIONS.md](MODEL_CONNECTIONS.md) |
| Privacy profiles, document scanning, web search queries | [PRIVACY_PROFILES.md](PRIVACY_PROFILES.md) |
| Containers, proxy, metrics, CI scans | [../deploy/README.md](../deploy/README.md) |
| Deploying and running | [OPERATIONS.md](OPERATIONS.md) |
| Using the app (students) | [STUDENT_MANUAL.md](STUDENT_MANUAL.md) |
| Using the app (instructors, TA note) | [INSTRUCTOR_MANUAL.md](INSTRUCTOR_MANUAL.md) |
| How the code came about | pull requests; the v3 build log [history/IMPLEMENTATION_LOG.md](history/IMPLEMENTATION_LOG.md) |

## 2. State per area

| Task | State | Where |
|---|---|---|
| Z1 interface contract | merged | `backend/app/platform/`, `core/schemas.py` |
| Z2 9B vs 27B | merged (#51); the speed of the whole ask pipeline on the vLLM server not measured | `eval/model-compare/` (judged in both orders: 27B 6, 9B 2, 12 ties; 9B stays the default; both fit one 24 GB GPU in 4-bit) |
| Z3 PostgreSQL + Alembic | merged | `backend/alembic/`, `app/storage/` |
| Z4 course catalog | merged | `app/catalog/` |
| Z5 settings layers, live component switch | merged | `app/platform/settings.py`, `components.py` |
| Z6 model gateway | merged; vLLM capacity measured on 2026-11-20 (Z23, Qwen3.5-9B): 43 tokens/s for one answer, 476 tokens/s in total at 32 at a time with short prompts, 120 to 160 tokens/s with course passages, no errors; recommended `max_concurrent` 8 (now 4), `queue_timeout_seconds` 60 (OPERATIONS.md section 10); one full ask through the app not timed (needs accounts) | `app/llm/`, `eval/load-test/` (`capacity.py`, `results/`) |
| Z7 privacy profiles | merged | `app/privacy/profiles/` |
| Z8 Docker Compose | merged | `docker-compose.yml`, `deploy/` |
| Z9 API v2 (accounts, courses, members, invitations, content, settings, admin) | merged (#42–#45); main fix #47; viewable invitation code #52; v2 ask #61; end of term and export #63 (`app/platform/end_of_term.py`) | `app/api/v2/`, `app/platform/courses.py`, `app/catalog/editor.py` |
| Z10 usage, CSRF, login limits, access tests | merged (#46) | `app/platform/usage.py`, `app/auth/csrf.py`, `tests/test_access_every_endpoint.py` |
| Z11 ECE profile, `scan_document`, `search_query`, consent text | merged (#48) | `app/privacy/recognizers/engineering.py`, `eval/privacy-filter/ece*.py` |
| Z12 instructor AI tier 4 | merged (#53); background jobs in the `job` table, run by the worker | `app/instructor_ai/eval/`, `app/platform/jobs.py` |
| Z13 CI scans, `/metrics`, Prometheus, alerts, Grafana | merged (#49, #58); not deployed on the test host, no alert receiver chosen yet | `.github/workflows/ci.yml`, `app/platform/metrics.py`, `deploy/monitoring/` |
| Z14 manual and handover | merged (#50; this page, OPERATIONS.md); load test of the app on the server outstanding | `docs/` |
| Z15 rule 14 in Z code | merged | `app/privacy/recognizers/` |
| Z16 answers by subject | merged (#97): the course's privacy profile chooses the system prompt and the checkers (no medical safety check outside medical courses) | `app/prompts/`, `app/privacy/profiles/` |
| Z17 local model calls through the gateway | merged (#96): understand, the generalize rewrite and `llm_check` use the stored trusted local connection | `app/llm/gateway.py` |
| Z18 repository cleanup | merged (#95) | `docs/history/` |
| Z19 course sources in answers | merged (#100): the evidence step kept no passage of the course retriever, so answers had no sources | `app/routing/evidence.py` |
| Z20 structured drafts on vLLM | merged (#99): the JSON schema is sent to trusted local OpenAI-compatible connections; tier 2 drafts may use 4,096 output tokens | `app/llm/openai_compat.py`, `app/instructor_ai/structure_drafts.py` |
| Q1 quizzes and the end-of-term survey (decided 2026-11-12) | merged (#66): quizzes (multiple choice and true/false, local-model drafts reviewed by the instructor, auto-grading, results under the visibility rules, `final` = post-test against the diagnostic), the end-of-term survey (window, anonymous ratings, minimum group of 3), both exported as aggregates and deleted at the end of term; migration 0013 | `app/learner/quizzes.py`, `app/api/v2/quizzes.py`, `app/api/v2/survey.py`, `app/instructor_ai/quiz_drafts.py`, `tests/test_quizzes_v2.py`; api-v2.md 3.9, 3.10; course-structure.md 4.6, 4.7 |
| S (learner data per course, S9) | merged (#60, #62, #77): learner tables per course, export and delete one course, visibility choices, overview, learning plan, answer style in the overview | `app/learner/course_data.py`, `course_views.py`, `visibility_policy.py`, `app/api/v2/learner.py` |
| S4 materials on API v2 | merged (#67): upload scanned before storing, delete, index rebuild job | `app/api/v2/`, `app/rag/index_jobs.py` |
| S5 open course packs | merged (#64, #65 for the scan false positives) | `data/demo_courses/`, `scripts/fetch_open_courses.py` |
| S6, S7, S10 instructor AI tiers 1 to 3 on API v2 | merged (#70): drafts as background jobs, accept into course content, class insights | `app/instructor_ai/draft_jobs.py`, `insights_source.py`, `app/api/v2/` |
| S8 course-level knowledge model | merged (#87): `learner.knowledge: course` is the default; course ability replayed from the evidence log, a starting estimate shifted by it, prerequisites cap what is shown (the stored estimate stays raw BKT); the whole suite passes with `bkt`, `rule` and `course` | `app/learner/knowledge/course.py`, `course_core.py`, `eval/learner-sim/results/course_model.md` |
| S11 retrieval evaluation | merged (#72): all eight packs | `eval/course-rag-packs/` |
| T4 ECE and CS routing evaluation | merged (#75); retrained candidates not adopted | `eval/routing-ece/` |
| T5 question type (concept / logistics) | merged (#80): own weight file, set by the route step; logistics questions search course-level files first | `app/routing/question_type.py`, `app/rag/course_retriever.py` |
| S14 course retrieval: paraphrases and misspellings | merged (#136): stemming, typo correction, logistics synonyms, course-wide weight for homework and exams, semantic step (embeddings stored with the index; `rag.semantic_retrieval`; courses get them at their next rebuild) | `app/rag/course_retriever.py`, `app/rag/query_text.py`, `app/rag/encoder.py` |
| T9 demo build | merged (#69): the demo courses from the packs through API v2 | `scripts/build_demo.py` |
| F1 frontend on API v2 (carries T6, T7, T8) | merged (#71, #78; UI upgrade #81 to #85): student and instructor dashboards, admin, model connections, quizzes, survey, materials | `frontend/`, `docs/design/ui-upgrade.md` |
| T11 accessibility and renaming, T12 manuals | merged (#74, #101, #73); the product is named PACT (Privacy-Aware Course Tutor); routing, frontend and web search handover notes still open | `docs/ACCESSIBILITY.md`, `docs/STUDENT_MANUAL.md`, `docs/INSTRUCTOR_MANUAL.md` |
| T13 web search | merged (#88, #90, #92 to #94): modes `off`, `openai` (the default), hosted `api` (Tavily) and self-hosted `searxng`; runs for cloud answers that need recent information, query from `search_query()`, allow-listed sites per course type; evaluated on 79 questions (G1-106: OpenAI 48 of 59, Tavily 40, no search 30) | `app/websearch/`, `app/pipeline/steps/web_search.py`, [WEB_SEARCH.md](WEB_SEARCH.md) |

### v5 (2026-11-20)

The v5 tasks come from the meeting of 2026-11-17; [v5-plan.md](v5-plan.md) section 0 has the state of each
one, section 9 the findings of the V17 browser test and section 10 the decisions of 2026-11-20 with the next
tasks for whoever takes over (V18, Z22b, V19, Z22c).

| Task | State | Where |
|---|---|---|
| V1 statistics-only instructor view | merged (#109); mode B code kept, switched off by `learner.instructor_individual_view` (default false) | `app/learner/visibility_policy.py`, `app/api/v2/learner.py` |
| V2 class statistics | merged (#115, #126): minimum group `max(5, setting)`, every row of the course counts (also of students who left), complementary suppression over all sums, quiz mean to 0.1 | `app/learner/statistics.py`, api-v2.md 3.4 |
| V3 privacy notice | merged (#114) | `frontend/src/components/PrivacyNotice.tsx` |
| V4 to V6 drafts from a free request, chosen sources, a file for one draft | merged (#119, #120) | `app/instructor_ai/drafts.py`, `app/api/v2/ai_drafts.py` |
| V7 web pages | merged (#120): fetched through `PinnedTransport` (https, public addresses only, size and time limits), stored as `web-*.md`, re-fetch under a row lock | `app/rag/web_pages.py`, `app/api/v2/materials.py` |
| V8 closed loop | merged (#123): "Explain it another way" for the student; topics weak for the class (minimum group) hand a request to the AI assistant | `app/learner/weak_topics.py`, `frontend/src/pages/instructor/Overview.tsx` |
| V9 accounts from term to term | merged (#118, #125): admin student list, deactivate, reset, delete with audit and scrub | `app/api/v2/admin.py`, `app/auth/purge.py` |
| V15 a student's own answer instruction | merged (#121): scanned, `<` and `>` refused, only to the trusted local model, below the instructor's rules | `app/learner/facade.py`, `app/prompts/render.py`, migration 0017 |
| V16 cloud drafts for public material | merged (#122): only through `DraftCloudRequest` and `CloudClient.complete_draft` (cloud gate), everything sent is scanned. Before/after measured in `eval/v16-drafts/` (KC and quiz drafts better, the rest unchanged); open: cloud KC, check item and misconception drafts fail (the cloud call has no JSON schema), one-text local drafts stop at 1,024 tokens or fail on repeated citations | `app/instructor_ai/draft_cloud.py`, `app/llm/cloud_guard.py` |
| Backend French texts | merged (#124) | `app/api/v2/fr.yaml`, `localize.py` |
| Z26, S15, S16, Z25 | merged (#110, #113, #111, #112) | |
| Z25b reference-list identifiers | the student number recognizer skips a number right after a bibliographic label (S2CID, arXiv, hdl, ProQuest, PMID, OCLC, doi, …), so Wikipedia pages pass the document scan; E6 identical | `app/privacy/recognizers/student_id.py` |
| Z27 security review | merged (#117) | [SECURITY_REVIEW.md](SECURITY_REVIEW.md) |
| V19 a course type as one package (routing) | V19 PR: `RouteInput.course_type`, heads per type with fallback, `routing.by_course_type`, `train.py --course-type`; checklist in design/extension-points.md | `app/routing/models.py`, `app/pipeline/settings_view.py` (`router_of`) |
| V18 edit the wording of KCs and check items | PR #138: the code stays, so learner records and statistics keep counting the item; another active KC's name is a 409; edits audited with field names only | `app/catalog/editor.py`, `frontend/src/pages/instructor/ContentEdit.tsx` |
| Z22b privacy rules (only redact more) | PR #139: prefixed credential names, Bearer, URL passwords, passwords in prose, private addresses before a full stop, `git@` remotes; E6 identical | `app/privacy/recognizers/engineering.py`, `eval/privacy-filter/results/z22b/` |
| V20 course announcements | PR open (approved by Z on 2026-11-21): plain text, pinned first, latest three on the student's course home; privacy-scanned before storing, audited without text, no writes in an archived course; no e-mail or unread markers | `app/api/v2/announcements.py`, migration 0018, `frontend/src/pages/Announcements.tsx` |

## 3. Decisions taken during the work (not obvious from the code)

- **First account is the admin**: the account from `INSTRUCTOR_*` in `.env` gets the system role `admin`. API v1
  shows an admin as `instructor`.
- **Identity data only in `account`**: privacy invariant 6, checked by E4. A membership keeps an e-mail only
  while pending. Login identities hold `account:<id>`.
- **Invitation codes**: 10 characters, 120 days. Join checks the hash; the code is also stored encrypted with
  `SETTINGS_ENCRYPTION_KEY`, so instructors can see it again (Z, 2026-11-08; #52).
- **Content codes never change** (KC, item, misconception, module): learner data refers to them by code.
  Every edit is checked with the seed checks on the whole course. Edits bump `course.content_version`, and
  running processes reload the served course's content.
- **Course types are the privacy profile files**: a new `profiles/<name>.yaml` is a new course type. The API
  validates against the files, not a fixed list (#47).
- **Usage limits**: config only for now (`limits.usage`); the `usage_*` course settings stay null and are not
  exposed (guide 4.4). The v2 ask endpoints check and count them; API v1 has no limits.
- **One pipeline for every course**: API v2 ask runs the same runner inside a course scope
  (`app/platform/course_scope.py`), which gives the steps the course's content, learner model, retriever and
  conversations. A question without a module uses the topic `general`.
- **CSRF**: on API v2 only; API v1 is frozen and its frontend predates it. The session token is derived from
  the HttpOnly session cookie; before login a double-submit cookie is used.
- **Evaluation is only the end-of-term survey** (advisor meeting 2026-11-12): the rating after each answer and the
  answer-style buttons are removed from the new frontend; `/api/v1/survey` stays (API v1 is frozen) but nothing in
  v2 uses it. Survey answers carry no student ID and no time; a separate row only records that a student answered
  (course-structure.md 4.7).
- **Quizzes are progress, not grades**: multiple choice and true/false, one attempt, graded automatically; AI
  drafts come from the local model only and cannot be published unreviewed; results follow the visibility rules
  (guide 4.8). Targeted material for single students is next term; this term only the learning plan with notes.
- **Tests and demos use the eight open course packs** in `data/demo_courses/`.
- **Credentials are redacted in every course** (`secret_token` in the base profile); lab addresses and
  repository URLs only in ECE.
- **Known scan findings** are listed with their reason in `backend/.pip-audit-ignore` (the bandit baseline
  is empty since #55 and #56); anything new fails CI.

## 4. Open work by owner

What Z did in other owners' areas (for their review): guide section 7.5.

| Owner | Task | Why it matters |
|---|---|---|
| T | video (T10, Nov 25) | course deliverable |
| T | routing, frontend and web search handover notes (T12) | handover |
| T, Z | `transformers` 5 (6 pip-audit advisories ignored with reason), `react-router` 7 and `vite`/`vitest` (CI advisories) | CI reports them |
| Z | deploy on the test host with the monitoring profile; the app under load and the speed of the whole ask pipeline on vLLM | needs access to the test host |
| Z | E4 privacy audit on API v2 and the current `main` (audit P4); the health check also for vLLM (audit I6, A4) | the last full E4 predates v4 |
| Z | choose the alert receiver (`deploy/monitoring/alertmanager.yml`) | alerts are only visible in Alertmanager until then |
| Others | Lavin's second review of the 30 revised items: replaced on 2026-11-22 by an AI review with web search (`docs/review/AI_REVIEW_2026-11-22.md`: 0 major, 26 minor, all keyed answers correct, most advanced items too easy); a person still has to approve the items | content |

## 5. Working on the code

```bash
cd backend
python -m pytest -q                              # needs TEST_DATABASE_URL (a PostgreSQL server)
TEST_LEARNER_KNOWLEDGE=rule python -m pytest -q
python -m ruff check . ../scripts
python -m app.export_openapi && (cd ../frontend && npm run gen:api)   # after an API change
```

- Tests ignore the developer's `.env`. Evaluation harnesses do not: a `.env` with removed settings (for
  example `CONTENT__SERVE_UNREVIEWED`) stops them, so remove such lines.
- CI runs the backend tests twice, the evaluation smoke runs (E2, E3, E4, E6, load test), the scans, the
  frontend build and the Docker stack.
- Codex reviews every PR; its threads are resolved before merging.
