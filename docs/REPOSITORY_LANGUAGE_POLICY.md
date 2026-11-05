# Repository Language Policy

This is a University of Ottawa engineering capstone repository. **All committed
repository text is English-only**, including source code, identifiers, comments,
tests, documentation, configuration, tracked sample data, filenames, commit
messages and team handoffs. French UI translations and French-language test
scenarios remain permitted where the product explicitly requires them.

No Chinese-language Markdown companions or literal Chinese/CJK characters
may be committed anywhere in the active repository, including `docs/`.

## Validation

Run from the repository root:

```powershell
python scripts/check_english_only.py
```

The checker covers tracked files and nonignored additions, file paths, and
UTF-8 text content. It rejects literal CJK ideographs and associated
fullwidth/CJK punctuation. Run it before every commit alongside the ordinary
Ruff, backend, frontend and privacy regression tests.

## Preserve existing functional coverage

Some privacy recognizers and synthetic multilingual benchmarks intentionally
exercise Chinese-language patterns. They are not endorsements of a
Chinese-language project interface. To keep these tests functional without
literal Chinese source text:

- Python/TypeScript source literals use `\uXXXX` escapes, which still
  evaluate to the original Unicode characters at runtime.
- JSON and JSONL fixtures use JSON Unicode escapes, which deserialize to
  their original strings. Their structured meanings must remain unchanged.
- Historical CSV review/result exports retain reversible `\uXXXX`
  notation for CJK text. These CSV exports are archives and should be decoded
  when human-readable multilingual historical results are needed; do not use
  their raw escaped fields as live benchmark answers.
- Historical documents formerly maintained only in Chinese have been replaced
  by English reference notes or, when redundant with an authoritative English
  counterpart, removed. Their original versions remain accessible in Git history.

This policy is about repository text and documentation. It must **not**
disable recognition of real private data in another language, weaken the
privacy boundary, or redefine previously recorded benchmark results.

## Authoritative documents

- [English v4 implementation guide](v4-implementation-guide.md)
- [English team handoff](SIYUN_TEAM_HANDOFF_Z_T_2026-11-05.md)
- [Historical privacy upgrade plan](history/PRIVACY_UPGRADE_PLAN.md)

The original Chinese companion files are not maintained.
