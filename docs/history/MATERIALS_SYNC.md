# v3 Instructor material synchronization patch

**Historical implementation note.** The v4 course indexing design supersedes
this topic-based patch. Follow the English v4 guide for new work.

## Objective

The instructor Content page previously showed only uploaded files and omitted
the five built-in medical topic sources. The medical RAG retriever also read
built-in snapshots without including instructor-uploaded documents. This patch
integrated both sources and made retrieval status visible.

## Materials and retrieval

- Built-in reference snapshots are included in the Content dashboard.
- Instructor-uploaded materials live under
  `rag.materials_dir/<topic>/`, by default `data/topics/<topic>/`.
- Display built-in and uploaded sections separately, with file names,
  passage counts, and `Searchable` or `Not searchable` status.
- The upload endpoint waits for indexing before displaying successful retrieval
  status. Parse or indexing failures should report the reason without claiming
  the material is searchable.
- The retriever combines relevant uploaded material with built-in snapshots
  for the selected topic. An invalid document must not hide approved sources.
- Changes to uploaded files and restart persistence require regression tests.
- Only text-backed PDFs can be searched without OCR. PowerPoint handling
  was introduced later as S2; see `docs/RAG_COURSE_BETA.md`.
- Instructor uploads must eventually pass the real privacy scanner.

## Acceptance criteria

1. The Content page lists five built-in topics and approved uploads.
2. Source status correctly distinguishes successful from failed indexing.
3. Uploaded text contributes to retrieval and citations after a restart.
4. Invalid or deleted material cannot appear as a valid source.
5. Sources are scoped to the intended topic/course.

## v4 migration

The v4 implementation replaces topic-only storage with per-course and per-module
materials, asynchronous jobs, a strict document privacy scan, and versioned
indexes. The binding architecture is `docs/design/course-structure.md`, and
Siyun's implementation status is `docs/S4_COURSE_RETRIEVER_STATUS.md`.
