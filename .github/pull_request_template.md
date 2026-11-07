## Task

Task ID from docs/v4-implementation-guide.md section 7 (for example `Z4`):

## What changed

-

## How it was tested

Paste the commands and their results (backend tests twice, ruff, frontend build and tests, evaluations if relevant).

```
```

## Privacy and permissions

Effect on privacy (what can reach a model, what is stored) and on permissions (who can see what). Write "none" if there is none.

## Checklist

- [ ] Only files of my own component are changed (guide section 5, `.github/CODEOWNERS`), or the other owner agreed
- [ ] New endpoints are under `/api/v2` and have access tests (another course's instructor, another student, logged out)
- [ ] No secrets, no real student data, no question text in logs or tests
- [ ] Privacy rule changes: full E6 re-run, results not worse (attach the summary)
- [ ] API changed: `frontend/openapi.json` and `frontend/src/api/schema.d.ts` regenerated and committed
- [ ] Chinese only in code or test data that handle Chinese input, English behaviour unchanged; no Chinese in comments, commit messages or Markdown outside `docs/`
- [ ] An English document in `docs/` changed: its `_zh.md` companion is updated or marked out of date
