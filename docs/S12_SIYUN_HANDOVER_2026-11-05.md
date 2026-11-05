# S12 — Siyun v4 implementation and handover (2026-11-05)

## Baseline and branch strategy

- Read `AGENTS.md` and `docs/v4-implementation-guide.md` before changes.
- The GitHub main baseline was `7e943a6` (2026-11-04). The main worktree stays untouched.
- Independent task branches were created from main. The integration branch is **for testing/review**, not a single omnibus PR.
- Personal integration branch: `feature/siyun-v4-integration-20261105`.
- No production student data, access credentials, teacher-provided ELG 5902 materials or unapproved questionnaire responses were added.

## Checklist

| Task | Status | Evidence / remaining work |
|---|---|---|
| S1 | **Partial** | Relative paths and Lavin status corrected in `docs/RAG_COURSE_BETA.md` (`docs/s1-rag-paths`). Page/slide labels remain rendered by the v1 API; frontend translation belongs to Tongkai. Task says done when *merged*, not yet met. |
| S2 | **Implemented on task branch, not merged** | `.pptx` local extraction of text, tables, speaker notes, slide-specific metadata; archive size limit, images-only error, three-slide teacher-upload test (`feature/s2-pptx-retrieval`). |
| S3 | **Implemented on task branch, not merged** | One source entry per numbered prompt passage, including repeated file/page references; deterministic excerpt labels (`fix/s3-citation-sources`). Tests use fictional evidence. |
| S4 | **Core only; integration blocked** | `CourseRetriever.retrieve(course_id, module_id, query, k)`; per-course versioned disk index; fail-closed injected scanner; worker-friendly rebuild; isolation tests (`feature/s4-course-index-core`). Needs Z4 database/worker/version updates, Z11 scan_document(), v4 course API and authorization. |
| S5 | **Fictional demo pack prepared; real courses pending** | Five-module original demo notes, course outline, fictional project brief and templates (`feature/s5-medical-demo-kit`), all visibly unreviewed. Existing MedlinePlus snapshots are referenced, not redistributed. ELG 5902 materials excluded until Prof. Gita grants permission; real teacher uploads/retrieval need the Z4/Z11 pipeline. |
| S6 | **Blocked** | Requires production S4 and Z6 model gateway; no instructor AI generation or review workflow is claimed. |
| S7 | **Blocked** | Requires Z4 database and completed S4. Lavin draft content is staged, not automatically published as accepted AI-generated questions. |
| S8 | **Blocked** | Course-level knowledge model depends on Z4. Existing v3 BKT and rule learner regression tests remain passing. |
| S9 | **Blocked** | Needs Z4 course rows, Z10 visibility/permissions; cannot implement safe cross-course instructor views against missing database interfaces. |
| S10 | **Blocked** | Requires S8. No class insights are generated from actual student records. |
| S11 | **Blocked for real evaluation** | A labelled benchmark CLI exists. Meaningful dual-course results require authorized real course documents and independently labelled questions, neither available for both courses yet. Do not report synthetic fixtures as measured course quality. |
| S12 | **Completed as handover document** | This checklist, branch links, dependency and medical-review notes. Merge status remains pending code owner review. |

## Lavin feedback integration

- Lavin's 2026-11-05 reply found no obvious medical inaccuracies or inappropriate content **in the original questions**.
- She recommended plausible distractors, variable difficulty within knowledge concepts, and clarified that the original difficulty was nearer undergraduate than medical-school level.
- The updated set still has **84 draft items** across five medical topics and the original **26 KCs / 32 misconception corrections**.
- **30 items** were revised, including the **13 specifically commented** items; 3 answer letters changed and were checked against YAML.
- Reviewer comments and revision log are preserved in `docs/review/` on `feature/s7-lavin-draft-content`.
- No revised question is marked `reviewed_by`; no medical second sign-off has been received.
- A missing guard against submitting unapproved onboarding items has been restored in the v4 learner implementation.
- Obtain explicit client audience clarification and Lavin's second review before making edited questions student-facing.

## Task branches for review

- `docs/s1-rag-paths` — `22c31db`
- `feature/s2-pptx-retrieval` — `52af88e`
- `fix/s3-citation-sources` — `6d1c70e`
- `feature/s4-course-index-core` — `0191fd7`
- `feature/s5-medical-demo-kit` — `538aa83`
- `feature/s7-lavin-draft-content` — `8140d0e`
- `feature/siyun-v4-integration-20261105` — combines task branches for local testing; its commit changes as verified tasks are integrated.

All task branches are pushed to `origin`. None should be treated as merged into `main` until a code-owner PR review occurs.

## Tests and verification

Run in `backend/` with no developer `.env`:
```powershell
python -m pytest -q
$env:TEST_LEARNER_KNOWLEDGE='rule'; python -m pytest -q
python -m ruff check . ../scripts
```

Run in `frontend/`:
```powershell
npm run build
npm test
```

**Final integrated branch verification (after S4 + S5 + S12, 2026-11-05):**
- BKT: **672 passed, 1 deselected**; exit 0.
- Rule learner: **672 passed, 1 deselected**; exit 0.
- Ruff: **all checks passed**; exit 0.
- Frontend production build: **passed**; exit 0.
- Frontend unit tests: **28 passed (8 files)**; exit 0.
- S4+S5 local smoke test: fictional medical demo documents were indexed as a course, and the outline, project requirements, migraine and pneumonia module notes were retrieved from the expected scope. Cross-course leakage test passed, with a local fake scanner used for **fictional fixtures only**.
- All automated tests use fake LLMs where a model is needed. No live Ollama/cloud inference, clinical validation, official ELG 5902 lecture access or production v4 database integration was verified.

## Ownership and next decisions

1. Zhenyan: Z4 course/material DB and background worker, Z11 privacy scanner, Z6 model gateway, Z10 permissions; decide the v4 source-citation transport with Tongkai.
2. Tongkai: localize page/slide labels and connect frontend citations to the course-aware v2 API; do not change source numbering.
3. Prof. Gita: give explicit permission before using ELG 5902 teaching slides or assignments.
4. Lavin/client: confirm undergraduate vs medical-school target and approve or revise updated items individually.
5. Siyun: once these dependencies land, complete production S4, S6-S11 through the required interfaces, run real multi-course evaluations and document results.

## Safety / limitations

- The current course retriever is an **unwired core**. Its tests use an explicitly injected fake scanner on fictional examples. Never deploy that scanner to a real class.
- `/api/v1` remains frozen for new HTTP endpoints; future endpoints belong under `/api/v2` with course-role enforcement and API generation.
- Retrieval relevance scores are not medical-correctness probabilities.
- Original demo materials and the Lavin revisions are *not* an approved clinical curriculum.
- Do not publish measured student-learning gains without real student evaluation and consent.
