# English-Only Repository Cleanup Audit

**Date:** 2026-11-05
**Branch:** `feature/siyun-v4-integration-20261105`
**Scope:** Entire active Git working tree, not only Siyun-owned modules.

## Changes

- Removed four redundant Chinese-language Markdown files, including the
  translated Siyun team handoff, the translated v4 guide, the old root setup
  translation and the superseded privacy-upgrade note.
- Preserved the authoritative English technical handoff and implementation guide.
- Rewrote the historical backlog, discussion notes, material synchronization
  notes, model capability benchmark overview and test plan in English.
- Supplied an English historical privacy-upgrade summary.
- Converted literal CJK characters in code, tests, JSONL results and benchmark
  data to Unicode escapes. This preserves functional multilingual test inputs
  without committing literal Chinese text.
- Recorded the English-only rule in `AGENTS.md`, the v4 implementation guide,
  `README.md`, and `docs/REPOSITORY_LANGUAGE_POLICY.md`.
- Added `scripts/check_english_only.py` and a backend regression test to
  reject future literal CJK text in tracked source, docs, fixtures and paths.

## Preservation checks

- JSONL semantic comparison with the previous commit:
  **13,027 records across 12 JSON/JSONL files were identical after parsing**.
- Three historical CSV files were checked for reversible Unicode escape
  transformation; no records were intentionally deleted.
- A localized personal-name recognizer and fullwidth punctuation parser were
  exercised after source conversion; both continued to work.
- The original historical documents and unescaped benchmark exports remain
  available through Git history for provenance. Rewritten English summaries
  are not represented as line-by-line translations.

## Final quality gates

| Gate | Verified result |
|---|---|
| Repository CJK text checker | Passed |
| Backend default/BKT | 767 passed, 1 deselected |
| Backend Rule | 767 passed, 1 deselected |
| Backend Ruff | Passed |
| Frontend TypeScript/Vite production build | Passed |
| Frontend unit tests | 28 passed (8 files) |
| Python compilation and Unicode runtime check | Passed |

The language cleanup does not change course permissions, model deployment,
privacy scan policy or the unresolved production dependencies documented in
`SIYUN_TEAM_HANDOFF_Z_T_2026-11-05.md`.
