# ELG 5902 v4 — Siyun backend handoff to Zhenyan and Tongkai
**Date:** 2026-11-05
**Owner:** Siyun Tan (S)
**Repository:** https://github.com/PXzy98/Hybrid-AI-Tutor
**Personal delivery branch:** `feature/siyun-v4-integration-20261105`
**Local workspace:** `F:\5902_v4_integration`
**Primary specifications:** `AGENTS.md`, `docs/v4-implementation-guide.md` (sections 2, 5–8),
`docs/design/course-structure.md`, `docs/design/api-v2.md`.

> This is a teammate integration contract, not a claim that production v4 is finished.
> Do not interpret passing offline tests as authorization, privacy approval,
> clinical sign-off, real LLM operation, or a multi-course production deployment.

## 1. Decision and collaboration model

Siyun keeps **all personal work on the branch above**, per the team's current workflow
preference; do not ask him to rebuild work on multiple personal task branches.
The team `main` has not been modified by this handoff. Teammates may use this branch
to inspect and integrate S-owned components through their defined interfaces.

The v4 guide assigns **S**: course content/retrieval, Instructor AI tiers 1–3 backend,
course learner model, instructor learner views, privacy-conscious aggregates,
real two-course retrieval evaluation, and handover. It assigns **Z**: course DB,
platform/access, privacy, model gateway/vLLM, jobs, Docker/operations, Tier 4.
It assigns **T**: routing, web search, entire frontend, user docs/demo UI.
These are distinct responsibilities: **Ollama/vLLM/LLM deployment is not Siyun's task**.

## 2. Precise status by S task

| ID | Delivered in this branch | Still needed before the task is production-complete |
|---|---|---|
| **S1** | RAG beta guide uses relative project paths; v1 page-number/citation fixes | T localizes `page N` and `slide N` in the frontend; do not broaden frozen API v1 |
| **S2** | PPTX slide text, tables, speaker notes, slide-aware chunks, archive limits, images-only error, fictional fixtures | Authorized real teaching-file verification |
| **S3** | Prompt citation number and Sources list alignment (including repeated file/page), regression tests | T ensures v2 UI renders the same passage numbers and file positions |
| **S4** | `CourseRetriever.retrieve(course_id,module_id,query,k)`; per-course/versioned on-disk index; module/course scope; fail-closed scanner injection; worker-friendly rebuild | Z4 material/index DB and job worker, Z11 privacy scanner, Z9/Z10 course authorization, v4 pipeline wiring |
| **S5** | Five-topic fictional General Medical Knowledge demo syllabus, modules, templates and project brief; MedlinePlus snapshots referenced, not redistributed | Instructor/client-approved actual materials; Gita's permission before using ELG5902 teaching files |
| **S6** | Validated local-only project ideas, sample-proposal guides and FAQ *drafts* with source-reference checks | Z6 gateway, Z4 `ai_draft` persistence/jobs, Z9/Z10 instructor-only v2 generation/list/edit/accept/delete |
| **S7** | Validated local-only draft KCs, four-choice check items and misconception corrections; Lavin's 84-item revision package staged, not approved | Z4 content/draft lifecycle and migration, authorized accept/publish API, Lavin's second sign-off |
| **S8** | Course-scoped ability + BKT KC state; acyclic prerequisites and mastery projection; offline tests and v3-math parity checks | Z4 course-indexed evidence/KC persistence, effective settings, online pipeline/KnowledgeModel integration and formal comparative evaluation |
| **S9** | Mode A/B consent, opt-out/opt-in, `visible_since`, fail-closed overview projection, mandatory audit hooks, learning-plan validations | Z4 student-course visibility rows, Z10 durable roles/audits, course-scoped v2 profile/plan/opt-out/export handlers |
| **S10** | Aggregate KC/misconception label counts by course with suppression for small cohorts; no question text returned | S8 persisted signals, authorized v2 insights endpoint and appropriate privacy threshold |
| **S11** | Two-course labelled RAG evaluation CLI with exact-gold validation, retrieval metrics and no query text in report | Two authorized indexed courses, questions independently labelled by instructors, real results |
| **S12** | Self-review, tests and handover documents | Final acceptance following actual integrations |

Implementation locations: `backend/app/rag/`, `backend/app/instructor_ai/`,
`backend/app/learner/`, `backend/tests/`, `data/demo_courses/`,
`content/topics/`, `eval/course_rag_v4.py` and `docs/review/`.

## 3. Blocking contracts for Zhenyan (Z)

Please provide the following **on the Z-owned platform side**; do not ask S to
implement the database, scanner, model deployment or global security layer.

### Z4 / Z9 / Z10 — course store, jobs and roles (critical path)

1. PostgreSQL/Alembic schema and database interfaces for `course`, `module`, `material`,
   `index_version`, `job`, `ai_draft`, `learner_kc_state`,
   `evidence_log`, `learning_plan`, visibility fields on `course_member`,
   and `audit_log`. Course IDs must remain integer IDs.
2. Course-scoped material upload/delete first checks `require_course_role("instructor")`,
   saves/records the document, scans it, then schedules indexing; only the worker
   publishes an index version and updates the **authoritative DB index_version**.
   On scanner or indexing failure, the previously published index stays active.
3. Worker integration with S's `CourseRetriever(..., scan=..., index_version=...)`.
   Directory shape: `courses/<course_id>/materials/_course/` or
   `courses/<course_id>/materials/<module_id>/` and
   `courses/<course_id>/index/v<N>/passages.json`.
4. Implement real `require_course_role`, `require_system_role` and CSRF;
   an unauthorized course must return 404. A student must not be able to read
   another student's learner data or any instructor AI drafts.
5. Specify an atomic **audit + authorization + query/update** transaction for S9;
   anonymous, cross-course, opted-out, or unacknowledged learners never appear.
   Mode A -> B does not reveal historical data; opt-in after opt-out sets a new
   `visible_since` epoch.
6. Provide the final signatures for material ID, job ID, draft ID, effective settings
   and background-job callbacks before wiring S endpoints. Z1 `FakeCourseDirectory`
   currently refuses access by default and is not production membership storage.

**Acceptance:** after upload of a fictional source for Course A, A students can
retrieve its authorized passages; Course B students cannot; module-level retrieval
includes shared syllabus plus the selected module only; failed scan leaves the
previous index untouched; restart and index-version changes reload correctly.

### Z11 — approved privacy scanner (required for S4)

Implement `privacy_profile(course_type)` and
`scan_document(text, profile) -> ScanResult`, with an explicit
accepted/rejected outcome, no raw-document logging, and clear failure behavior.
S4 presently requires an injected `scan(text) -> bool` callback and indexes only
when the result is exactly `True`. Z should provide a wrapper that converts the
real `ScanResult` to that Boolean **only after policy approval**.
`scan=lambda _: True` occurs in fictional unit tests only and must never be
used in deployment.

**Acceptance:** rejected, unscannable, or erroring documents cannot be indexed;
their extracted text is not written to persistent passage indexes.

### Z6 — model gateway (required for S6/S7)

Publish the guide-defined async contract:

```python
await gateway.complete(
    "local", messages, settings=effective_settings(course_id),
    trust_required="trusted_local", stream=False,
)
```

The S6/S7 modules currently take this as a **dependency-injected interface**
and perform strict JSON/schema, course ID and citation validation. They return
`status="draft"`; no student-visible publication method exists in the core.
Z supplies the gateway's real `LLMResult.text`, timeouts, model trust levels,
and job orchestration. No student records should enter instructor generation;
do not send unapproved full-course materials to an external provider.

**Acceptance:** disabled or unavailable trusted-local endpoint yields a controlled
error, not an automatic cloud fallback; generated drafts are not student-visible
until an instructor explicitly accepts them.

### Z4 content migration — **medical release blocker**

Lavin reviewed **the original** 84 questions. On Nov 5 she found no obvious
medical inaccuracies in those original items but asked for better distractors
and difficulty separation. S revised **30** items while retaining 84 total items,
26 KCs and 32 misconception corrections. These edited items have **not**
received Lavin's second medical review. The v4 database removes the old
`reviewed_by` field: Z4 must preserve *unapproved/draft* status during migration
rather than treating newly imported YAML as instructor-published content.
Do not expose these revised questions to students automatically.
Ask the client to confirm undergraduate versus medical-school target level.

## 4. Required actions for Tongkai (T)

1. **T3 / S1 / S3:** localize `page N` and `slide N` in the Sources UI, but
   preserve backend numeric page/slide positions and the `[i]` passage numbering.
   A duplicated file across two passages still needs consistent passage citations.
2. **T4 / T5:** train/evaluate ECE routing and add `SemanticAnalysis.question_kind`
   (`concept` or `logistics`); logistics should prefer whole-course syllabus,
   project requirements, templates and deadlines, *without* student KC updates.
3. **T6 / T7:** after Z publishes authorized API v2 and S publishes learner/AI
   endpoints, implement course material upload/index status, editable instructor
   drafts, explicit accept/decline, per-course student view, visibility opt-out,
   and learning-plan UI. The frontend never grants access by itself.
4. **T8:** show the required cloud-data notices and local/cloud labels from
   server-provided settings; never imply that a local model is accessible
   just because a draft core exists.
5. **T9 / T10:** use the fictional demo pack for the UI demo and an approved
   reviewer flow. Do not use real ELG5902 lecture files until Gita authorizes.
6. Following each authorized API change, regenerate
   `frontend/openapi.json` using `python -m app.export_openapi`,
   then `npm run gen:api` and rerun frontend build/tests.
   No new features should be added to the frozen `/api/v1`.

**Acceptance:** instructor can upload a scan-approved fictional PPTX and see
`slide N`; student can ask within the correct course and open accurately numbered
sources; only the instructor sees AI drafts; student visibility choices are clear;
a non-member cannot access a course via direct URL or API.

## 5. Integration order / checkpoints

1. Z publishes **real** course DB, roles and content/interface contracts (Z3/Z4/Z9/Z10).
   Leave the existing S branch intact; S owns the adapter inside S components.
2. Z publishes scanner (Z11) and worker. S connects S4 index and upload
   endpoints to those contracts; run cross-course/multi-module/failed-scan tests.
3. Z publishes trusted-local gateway (Z6); S connects S6/S7 generation,
   draft storage and explicit instructor acceptance. T builds the UI against v2.
4. S connects course-level S8 evidence persistence, S9 consent/overview/plans
   and S10 insights; Z supplies actual access checks and durable audit.
5. T integrates routing, page/slide citations, UI and API-generated types.
6. Gita and Lavin approve materials/revisions; only then S runs **real**
   two-course labelled retrieval evaluation and reports the measured metrics.

Dependencies may move in parallel if the final interfaces and fake test fixtures
match. Missing interfaces are blockers, not permission to bypass privacy.

## 6. Tests and proof, including limits

The integrated branch was previously verified at **749 backend tests passed** in
both default/BKT and rule configurations (one deselected in each), **28 frontend
tests passed**, Ruff passed, and the frontend build succeeded. Subsequent S8 parity
and S11 metric tests must be rerun before the final handoff commit; refer to the
most recent verified test record rather than extrapolating counts.

S11 reports Hit@1, Recall@1, Recall@K, Precision@1, Precision@K,
MRR@K, negative-query abstention, index-backed source traceability, and mean/p95
retrieval latency. A single gold passage has at most `Precision@4 = 0.25`
under the planned fixed-four-slot denominator. A relevance score or
source traceability score is **not** evidence of medical accuracy.
Run with approved CSV columns
`id,course_id,module_id,question,gold_source,gold_anchor,negative`
and `eval/course_rag_v4.py`. Gold anchors must uniquely occur in an indexed
passage; negative cases have blank gold fields. Do not invent ground truth.

The existing E2 simulated-learner smoke test ran on five medical topics, with
only 8 fictional students and 8 interactions each; it produced
`learner.knowledge: rule` as a *smoke-only* result and explicitly states
that the sample is too small for model selection. It does not validate real
course-level S8 learning gains or calibrated BKT/Elo parameters.

### Local verification commands

```powershell
cd F:\5902_v4_integration\backend
& F:\5902\.venv\Scripts\python.exe -m pytest -q
$env:TEST_LEARNER_KNOWLEDGE='rule'
& F:\5902\.venv\Scripts\python.exe -m pytest -q
Remove-Item Env:TEST_LEARNER_KNOWLEDGE -ErrorAction SilentlyContinue
& F:\5902\.venv\Scripts\python.exe -m ruff check . ../scripts
cd ..\frontend
npm run build
npm test -- --run
```

Unit tests use fictional evidence and fake models, not live student profiles
or a real local/cloud LLM. Before actual class release, run the specified
privacy evaluation E6 and course-role/CSRF tests, as well as the production
index/LLM/worker tests with authorized fictional test data.

## 7. What Siyun needs back from each teammate

**From Zhenyan:** exact Z4 `course/member/material/index_version/job/ai_draft/
learner/evidence/plan/audit` database interfaces; Z6 gateway contract and
failure behavior; Z11 scanner outcome and privacy profile; Z9/Z10 permission
dependencies and audit transaction; confirmation of draft status on YAML import.

**From Tongkai:** expected v2 Sources payload and translation UI behavior;
T5 logistics classifier contract; instructor drafts/learner UI requirements
and any extra response fields; completion of generated TypeScript API types.

**From Gita / Lavin (external to engineering):** written permission to use
ELG5902 materials; audience level; second medical review on S's 30 edits.
S cannot certify those approvals on behalf of the client.

## 8. Final release gate (do not skip)

Declare S1–S12 **production-complete only when** the real v4 interfaces are
wired, all relevant backend+frontend+security tests pass on the combined code,
students cannot reach drafts/unconsented learner profiles, a real two-course
labelled benchmark report exists, and clinical/usage approvals are documented.
Until then, describe the delivered state as **implemented and tested S-owned
cores awaiting Z/T integration**, not the completed multi-course product.

## 9. Additional S-owned integration adapters (updated 2026-11-05)

S has also supplied `backend/app/rag/privacy_adapter.py`:
`privacy_scan_callback(profile, scanner=scan_document)` wraps the Z1
`ScanResult(scanned, findings)` contract. It returns True **only if**
`scanned is True` with **zero findings**. Unknown/malformed results,
exceptions and the current Z1 `scanned=False` stub are rejected.
This is deliberately conservative; Z must explicitly decide any reviewed
exceptions in Z11 rather than weakening the S adapter.

`backend/tests/test_siyun_z1_gateway_contract.py` exercises S6/S7 against
Z1's actual `FakeGateway` and `effective_settings()`, verifying that
trusted-local requests never fall back to the external client.
`backend/tests/test_siyun_cross_component_smoke.py` checks the S4/S6/S7/S8/
S9/S10/S11 sequence with fictional course files and deliberately injected
fake services, without claiming production authorization or a working DB.

S11 evaluator now includes fixed-K `precision_at_k`, `precision_at_1`,
`recall_at_1`, and an active-index provenance check that raises rather
than giving credit for a fabricated source. These are retrieval integrity
metrics, not medical truth judgments.

## 10. Final independently executed regression (2026-11-05)

The unified personal branch passed the **complete** local regression after the
new scanner adapter, gateway contract tests, cross-component smoke test, S8
parity checks and S11 metrics:

| Verification | Result |
|---|---|
| Backend default BKT | **766 passed, 1 deselected**; exit 0 |
| Backend `TEST_LEARNER_KNOWLEDGE=rule` | **766 passed, 1 deselected**; exit 0 |
| Ruff (backend and scripts) | **Passed** |
| Frontend production build | **Passed** |
| Frontend unit tests | **28 passed (8 files)** |
| Simulated E2 smoke | **Completed on 5 topics, fictional data only** |

The E2 smoke report (with its limitations prominently stated) is in
`docs/S8_E2_SIMULATED_SMOKE_2026-11-05.md`. None of these tests establish
actual Z4/Z6/Z10/Z11 production readiness, real course retrieval quality, or
release approval.
