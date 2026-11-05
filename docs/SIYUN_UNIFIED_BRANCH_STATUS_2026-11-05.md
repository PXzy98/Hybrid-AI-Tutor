# Siyun ELG5902 v4 — unified personal branch status (2026-11-05)

Current single development destination: `feature/siyun-v4-integration-20261105`.
All changes in this development session are made in `F:\5902_v4_integration`.
Team `main` and the earlier task branches are not modified. No PR is created.
This is the user's personal integration branch, not a production release.

| Task | Implemented in the personal branch | Remaining to call it production-complete |
|---|---|---|
| S1 | RAG beta documentation and source-label fixes | Frontend translation belongs to Tongkai |
| S2 | PPTX text/tables/speaker notes/slide-aware indexing and tests | Real authorized lecturer material |
| S3 | Citation numbers and source list aligned | API v2/frontend course integration |
| S4 | Versioned per-course index, module isolation, scanner fail-closed and tests | Z4 database, Z11 privacy scanner, worker and Z9/Z10 authorization |
| S5 | Fictional five-module medical course data and draft medical review | Gita authorization for ELG5902; real course ingestion |
| S6 | Instructor AI Tier 1 draft generator, strict citations and trusted-local adapter | Z6 gateway, Z4 draft store, authorized v2 API and approval workflow |
| S7 | Draft KC/check item/misconception generator and reviewed-content staging | Z4 content acceptance, Lavin second sign-off and authorized API |
| S8 | Per-course ability + BKT and prerequisite projection math, simulated tests | Z4 learner persistence, course settings, calibrated learner evaluation |
| S9 | Mode A/B visibility, opt-out, consent epochs, bounded learning plan and audit guards | Z4/Z10 database and enforceable v2 access/audit |
| S10 | KC/misconception counts, group-size suppression and course scoping | S8 live signals, Z4 storage and authorized instructor v2 endpoint |
| S11 | Label-validated two-course RAG benchmark utility and CLI | Real authorized course indices and independently labeled gold questions |
| S12 | Handover and verified tests | Team production deployment is outside Siyun's ownership |

## Development boundaries

- Do not substitute a dummy privacy scanner or fake authorization in live application code.
- No student text or private user profile may be persisted or sent to an external model.
- Instructor AI outputs remain *drafts* until authorized instructor acceptance.
- Lavin's modified questions are not yet medically re-approved.
- Test data are fictional; regression success is not clinical or educational validation.
- No Ollama, vLLM, Docker or full platform deployment is assigned to Siyun.

The tested additions from this session are described in:
`docs/S7_STRUCTURE_DRAFT_CORE.md`, `docs/S8_COURSE_KNOWLEDGE_CORE.md`,
`docs/S9_LEARNING_PLAN_CORE.md`, `docs/S11_TWO_COURSE_RAG_EVALUATION.md`.
The earlier S6, S9 visibility and S10 implementations remain in the same branch.

## Validation commands

From `backend/` without an external developer `.env`:
```powershell
& "F:\5902\.venv\Scripts\python.exe" -m pytest -q
$env:TEST_LEARNER_KNOWLEDGE = "rule"
& "F:\5902\.venv\Scripts\python.exe" -m pytest -q
& "F:\5902\.venv\Scripts\python.exe" -m ruff check . ../scripts
```

From `frontend/`: `npm run build`, `npm test -- --run`.

All test outputs must be recorded only after their processes exit successfully.

## Final verification after S7/S8/S9/S11 standalone additions

Verified on this unified branch on 2026-11-05:
- Backend BKT: **749 passed, 1 deselected**, exit 0.
- Backend rule: **749 passed, 1 deselected**, exit 0.
- Ruff: **all checks passed**.
- Frontend TypeScript/Vite production build: **passed**.
- Frontend unit tests: **28 passed across 8 files**.
- S11 CLI `--help` executed successfully.

The 43 new offline test cases cover S7 structure drafts, S8 course knowledge,
S9 consent/learning-plan policy, and S11 labelled retrieval evaluation.
These are component and regression validations, not confirmation that absent
Z4/Z6/Z10/Z11 production interfaces or real medical-content approvals exist.

## Teammate contract and latest verified state

See `docs/SIYUN_TEAM_HANDOFF_Z_T_2026-11-05.md` for all integration requests
addressed to Zhenyan and Tongkai, and the English-only handoff notes for team coordination. The latest full default+rule regression on this personal branch is
**766 passed (1 deselected) in each backend mode**, with Ruff, frontend build,
and **28 frontend tests** passing. Real course API, DB, model gateway and external
clinical/source approval remain pending their respective owners.
