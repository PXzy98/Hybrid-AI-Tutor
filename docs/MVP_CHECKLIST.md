# MVP checklist (due Oct 21, 2026)

One row per MVP deliverable in [System_Design_v3.md §12](System_Design_v3.md), with where it is implemented and tested. Details per step: [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md).

Status: ✅ done and tested · 🟡 done, but something outside the code is still open · ⬜ not started

| # | Deliverable (design §12, MVP) | Status | Implemented in | Tested in | Notes |
|---|---|---|---|---|---|
| 1 | Repository skeleton, config, CI | ✅ | `backend/pyproject.toml`, `config.yaml`, `backend/app/core/config.py`, `.github/workflows/ci.yml` | `tests/test_config.py` | CI: ruff, pytest twice (BKT and rule), frontend build and test |
| 2 | Interfaces fixed in week 1 (`schemas.py`), stubs for routing and RAG, contract tests | ✅ | `app/core/schemas.py`, `app/routing/`, `app/rag/`, `docs/INTERFACES.md` | `tests/contracts/`, `tests/test_schemas.py` | Send `docs/INTERFACES.md` to Tongkai and Siyun |
| 3 | Step runner; `/api/v1/ask` runs all steps | ✅ | `app/pipeline/runner.py`, `app/pipeline/steps/*`, `app/api/v1/ask.py` | `tests/test_runner.py`, `tests/test_api.py`, `tests/test_verification.py::test_final_pipeline_and_failure_policies` | 10 steps + `update_learner` (a no-op until Step 11); `privacy_filter` must run first |
| 4 | Accounts and login: instructor bootstrap, student-account API, login and change-password pages | ✅ | `app/auth/`, `app/api/v1/{auth,admin_students}.py`, `frontend/src/pages/{Login,ChangePassword}.tsx` | `tests/test_auth.py`, `tests/test_admin_students.py` | Student-management **UI** is Beta (Step 13); the API is complete |
| 5 | Privacy filter (Presidio + custom recognizers), reversible anonymization, restore | ✅ | `app/privacy/`, `app/pipeline/steps/{privacy_filter,restore}.py` | `tests/test_privacy.py` | Bench recall 28/28 on the covered types; 15/15 health cases |
| 6 | Local and cloud calls; cloud only through the `CloudRequest` guard | 🟡 | `app/llm/`, `app/pipeline/steps/generate.py`, `app/verify/leaks.py` | `tests/test_llm_clients.py`, `tests/test_cloud_guard.py`, `tests/test_generate.py`, `tests/test_verification.py::test_privacy_end_to_end_forced_cloud` | Local tested against the real GPU server. The cloud path is tested with a fake transport; the **provider and key are still open** (design §15) |
| 7 | Response verification (medical safety, grounding, leak checks) | ✅ | `app/verify/`, `app/pipeline/steps/verify.py` | `tests/test_verification.py` | The design puts this in Beta; done early |
| 8 | `schemas` + `LearnerModel` facade; BKT and rule knowledge models | ✅ | `app/learner/{facade,repository,recommender}.py`, `app/learner/knowledge/` | `tests/test_learner.py`, `tests/test_bkt_math.py` | The whole suite also passes with `learner.knowledge: rule` (CI) |
| 9 | Consent + onboarding (preferences + diagnostic) | ✅ | `app/api/v1/onboarding.py`, `app/learner/checks.py`, `frontend/src/pages/Onboarding.tsx` | `tests/test_adaptive_flow.py` | Dependents of a missed prerequisite are not assessed |
| 10 | Level-aware prompts | ✅ | `app/prompts/` (base + 3 levels × 4 styles) | `tests/test_prompt_partials.py` | Safety rules only in the base; checked for all 12 combinations |
| 11 | `attach_check` + `/check` | ✅ | `app/pipeline/steps/attach_check.py`, `app/api/v1/check.py`, `frontend/src/components/CheckCard.tsx` | `tests/test_adaptive_flow.py`, `frontend/src/test/CheckCard.test.tsx` | Graded by the key; no repeat within 24 h |
| 12 | High Blood Pressure content complete | 🟡 | `content/topics/high_blood_pressure/` (6 KCs, 24 MCQs, 12 misconceptions) | `tests/test_content.py` | **Draft, not reviewed.** The demo needs `CONTENT__SERVE_UNREVIEWED=true`. Review file: `docs/review/high_blood_pressure_review.csv` → Dr. Abbas |
| 13 | React chat page (plus onboarding and "What I know") | ✅ | `frontend/src/pages/{Chat,Onboarding,WhatIKnow}.tsx` | `frontend/src/test/`; manual browser run (log, Step 9) | — |
| 14 | One-command start (Docker Compose), demo script | ✅ | `docker-compose.yml`, `backend/Dockerfile`, `frontend/{Dockerfile,nginx.conf}`, `scripts/demo_seed.py`, `docs/DEMO.md` | Manual run (log, Step 10) | — |
| 15 | Routing score: stub or first version | 🟡 | `app/routing/stub.py` | `tests/contracts/test_routing_contract.py` | **Tongkai**: the real router plugs in through `routing.impl` |
| 16 | RAG: stub or first version | 🟡 | `app/rag/stub.py` (`stub`, `fixture`) | `tests/contracts/test_rag_contract.py` | **Siyun**: the real retriever plugs in through `rag.impl`; chunks need `kc_ids` (`HBP.1`…`HBP.6`) and `level` |

## Open items that block nothing in the code but matter for the MVP demo

- [ ] Dr. Abbas reviews the HBP draft (items, misconception corrections), then `reviewed_by` is set in the YAML.
- [ ] Cloud provider and key (OpenAI / Groq / Kimi), and a spending limit.
- [ ] Tongkai and Siyun confirm the interfaces (`docs/INTERFACES.md`), including the `cloud_safe` force-local rule.
- [ ] Inform the professor of the deletion rule (design §8.3).
- [ ] Install `en_core_web_lg` on the machine that runs the server, or build the Docker image (it downloads the model).

## Not in the MVP (Beta, Steps 11–14)

The understand step and weak evidence; misconception tracking and corrections in answers; the instructor dashboard (students, class summary, settings, logs); the evaluation harnesses E1–E4; the other four topics' content.
