# Complete integration v3

Local branch: `integration/main-rag-semantic`.

| Source | Verified remote commit | Retained contribution |
| --- | --- | --- |
| main | 4cf64d7bea85e249592961649289720e30782cfb | Full instructor dashboard/API, accounts, uploads, logs, class summaries, learner model, understand step, privacy and verification |
| feature/rag-siyun-clean | 2ca304ffb0ea27e8a6b3dc1cf855af0fa5aa60d7 | Medical hybrid retrieval, source snapshots for five topics, evidence helpers, optional PubMed discovery and RAG tests |
| semantic-routing-tongkai | 090803b73e5d11881232c44e34ff1dc588782921 | 500-question LR/SVM routing, semantic capability/evidence/freshness heads, evidence checks, live progress/timings and per-question method choice |

All three remote commits were fetched and checked during this integration. The branch has real merge
ancestry: first main + RAG, then the semantic branch. It is not a flat copy over an old working directory.
The ZIP contains complete source and a Git bundle for restoring that local branch. No remote push or
automatic PR/merge was performed while preparing this handoff.

## Conflict resolutions

- Keep main's complete instructor routes, service modules, pages and navigation. Add the progress-display
  setting to its existing runtime config and history; no instructor feature is removed.
- Keep main's full account/learner/storage code. Use its understand step and pipeline order, inserting
  semantic analysis immediately before retrieval.
- Keep `rag.impl: medical_hybrid` and the main branch's materials_dir. Teammate-owned RAG source files,
  bundled medical data and RAG test files are preserved unchanged.
- Keep additive semantic request/response/schema fields; regenerate OpenAPI and TypeScript types from
  the fully merged backend.
- Runtime reconfiguration updates the semantic router config as well as the learner/pipeline.
- Make upload status truthful: files saved without indexing are reported as not yet searchable.
- Add first-run helpers with password validation, effective spaCy-model preparation and model-cache reuse.

## Routing and evidence limits

The original capability, evidence and freshness policy remains. This integration does not adopt the
previously discussed simplification to a single capability head. Neither model choice nor source presence
proves answer correctness. The 500 labels remain synthetic `prototype_policy` examples; Qwen answers
were not generated and graded to produce them. Cross-encoder evidence thresholds need validation on
the actual course domain. See the included real-model smoke report, which retains failure cases.

Semantic routing does not add a privacy-condition branch, as requested. Existing upstream privacy
filtering, sanitized CloudRequest construction and response checkers are preserved; the integration
boundary is marked TEAM INTEGRATION in routing/generation code.

## Upload boundary

The materials-sync patch adds `ingest` and `material_status` hooks to `medical_hybrid`. The instructor
Content page lists bundled snapshots and uploads separately, with indexing status and passage counts.
Uploaded text, Markdown, HTML, DOCX and text PDFs are indexed immediately and reloaded from disk on
startup. Replacing a file removes its previous passages; unreadable documents remain saved with an
explicit error and are excluded from retrieval. Scanned PDFs need OCR before uploading.
See `docs/MATERIALS_SYNC.md` for limits and verification.

The bundled snapshots/KC labels remain a research baseline; PubMed discovery is opt-in and is not
automatically attached to student requests. A snapshot download date is not treated as verified current
evidence. Cloud routing does not itself enable web search or retrieve missing course documents.
