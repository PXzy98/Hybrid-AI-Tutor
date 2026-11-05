# S4 Course Retriever Core — Stand-in Contract (2026-11-05)

The implementation is in backend/app/rag/course_retriever.py and remains an **unwired backend component** until Z4, Z9, Z11 and the v4 pipeline adopt the stable interface.

## Independent behavior implemented

- Public method: CourseRetriever.retrieve(course_id, module_id, query, k).
- Supports course-level source files and module-specific files, with a hard course boundary.
- Files follow the approved layout: courses/<course_id>/materials/_course/ or courses/<course_id>/materials/<module_id>/.
- Keeps a single versioned index per course: courses/<course_id>/index/v<N>/passages.json.
- Rebuild is a worker-friendly function; index files are published in a temporary directory and the current-version pointer is replaced atomically after a successful build.
- Readers reload when index_version changes; the constructor can receive the authoritative database version provider.
- Uses local word and character TF-IDF with a conservative character-only match threshold to avoid out-of-scope retrieval.
- PDF and PPTX source positions are stored on each chunk once task S2 is integrated. S4 on main alone supports text/PDF/DOCX/HTML.
- Requires an injected scan callback that returns **exactly True** after successful Z11 document privacy inspection. Without that callback, indexing fails closed.
- Does not store questions, student profile data, credentials or API keys.

## Remaining integration dependencies

- Z4 provides PostgreSQL course/material/module rows and authoritative index_version updates. An uploaded file must first be stored and scanned, and only then enqueued for rebuilding.
- Z11 provides privacy_profile() and scan_document(). A privacy wrapper must be applied to every document and must fail closed.
- Z9/Z10 enforce instructor/member authorization and course-scoped HTTP routes before calling this retriever.
- Z4's worker owns job progress reporting, post-publish database version update and old-version cleanup.
- S2 adds PowerPoint extraction to the underlying document parser. S1/T frontend source localization is separate.
- These functions use a fake scan callback only for fictional test fixtures. Do not deploy with scan=lambda _: True.

## Verification

Test backend/tests/test_course_index_core.py with a fictional two-course fixture for:
- course-scoped retrieval and module selection;
- missing scanner fail-closed;
- disk index version increment and reader reload;
- scan rejection leaving the previous published index intact;
- database-version-provider gating and asynchronous rebuild;
- invalid course and module identifiers.

The real end-to-end multi-course API test is blocked until Z4, Z9 and Z11 exist. This implementation does **not** claim that milestone is complete.

## Privacy scanner bridge (2026-11-05)

`backend/app/rag/privacy_adapter.py` now wraps Z1
`ScanResult(scanned, findings)` as the strict Boolean callback S4 expects.
It rejects `scanned=False`, any sensitive findings, scanner exceptions or
malformed responses. Z11 must implement the real scanner; the Z1 stub still
blocks all real indexing, as intended.
