# MVP checklist (due Oct 21, 2026)

One row per MVP deliverable in [System_Design_v3.md §12](System_Design_v3.md), with where it is implemented and tested. Details per step: [IMPLEMENTATION_LOG.md](IMPLEMENTATION_LOG.md). Updated 19 Oct 2026 for the integrated main (semantic routing, medical RAG, cloud gate, survey; PRs #2 and #3); differences from the design: [System_Design_v3.md §16](System_Design_v3.md).

Status: ✅ done and tested · 🟡 done, but something outside the code is still open · ⬜ not started

| # | Deliverable (design §12, MVP) | Status | Implemented in | Tested in | Notes |
|---|---|---|---|---|---|
| 1 | Repository skeleton, config, CI | ✅ | `backend/pyproject.toml`, `config.yaml`, `backend/app/core/config.py`, `.github/workflows/ci.yml` | `tests/test_config.py` | CI: ruff, pytest twice (BKT and rule), frontend build and test |
| 2 | Interfaces fixed in week 1 (`schemas.py`), stubs for routing and RAG, contract tests | ✅ | `app/core/schemas.py`, `app/routing/`, `app/rag/`, `docs/INTERFACES.md` | `tests/contracts/`, `tests/test_schemas.py` | Send `docs/INTERFACES.md` to Tongkai and Siyun |
| 3 | Step runner; `/api/v1/ask` runs all steps | ✅ | `app/pipeline/runner.py`, `app/pipeline/steps/*`, `app/api/v1/ask.py` | `tests/test_runner.py`, `tests/test_api.py`, `tests/test_verification.py::test_final_pipeline_and_failure_policies` | 11 steps (with `analyze_route`) + `update_learner`; `privacy_filter` must run first |
| 4 | Accounts and login: instructor bootstrap, student-account API, login and change-password pages | ✅ | `app/auth/`, `app/api/v1/{auth,admin_students}.py`, `frontend/src/pages/{Login,ChangePassword}.tsx` | `tests/test_auth.py`, `tests/test_admin_students.py` | Student-management **UI** is Beta (Step 13); the API is complete |
| 5 | Privacy filter (Presidio + custom recognizers), reversible anonymization, restore | ✅ | `app/privacy/`, `app/pipeline/steps/{privacy_filter,restore}.py` | `tests/test_privacy.py`, `eval/privacy-filter/` (E6) | 14 custom recognizers. E6 held-out test: identifiers reach the cloud in 1.1% of questions; about 1 in 5 freely worded personal-health questions is not recognised ([report](report/privacy_subsystem.md), [upgrades](隐私升级.md)) |
| 6 | Local and cloud calls; cloud only through the `CloudRequest` guard | 🟡 | `app/llm/`, `app/pipeline/steps/generate.py`, `app/verify/leaks.py` | `tests/test_llm_clients.py`, `tests/test_cloud_guard.py`, `tests/test_generate.py`, `tests/test_verification.py::test_privacy_end_to_end_forced_cloud` | Cloud gate for every router (health policy, leak guard, local fallback with a notice). Tested live with **DeepSeek** (`deepseek-flash`) and with E4 `--real-cloud` (0 leaks). Open: the client approves the provider and its data location (DeepSeek: China) |
| 7 | Response verification (medical safety, grounding, leak checks) | ✅ | `app/verify/`, `app/pipeline/steps/verify.py` | `tests/test_verification.py` | The design puts this in Beta; done early |
| 8 | `schemas` + `LearnerModel` facade; BKT and rule knowledge models | ✅ | `app/learner/{facade,repository,recommender}.py`, `app/learner/knowledge/` | `tests/test_learner.py`, `tests/test_bkt_math.py` | The whole suite also passes with `learner.knowledge: rule` (CI) |
| 9 | Consent + onboarding (preferences + diagnostic) | ✅ | `app/api/v1/onboarding.py`, `app/learner/checks.py`, `frontend/src/pages/Onboarding.tsx` | `tests/test_adaptive_flow.py` | Dependents of a missed prerequisite are not assessed |
| 10 | Level-aware prompts | ✅ | `app/prompts/` (base + 3 levels × 4 styles) | `tests/test_prompt_partials.py` | Safety rules only in the base; checked for all 12 combinations |
| 11 | `attach_check` + `/check` | ✅ | `app/pipeline/steps/attach_check.py`, `app/api/v1/check.py`, `frontend/src/components/CheckCard.tsx` | `tests/test_adaptive_flow.py`, `frontend/src/test/CheckCard.test.tsx` | Graded by the key; no repeat within 24 h |
| 12 | High Blood Pressure content complete | 🟡 | `content/topics/high_blood_pressure/` (6 KCs, 24 MCQs, 12 misconceptions) | `tests/test_content.py` | **Draft, not reviewed.** The demo needs `CONTENT__SERVE_UNREVIEWED=true`. Review file: `docs/review/high_blood_pressure_review.csv` → Dr. Abbas |
| 13 | React chat page (plus onboarding and "What I know") | ✅ | `frontend/src/pages/{Chat,Onboarding,WhatIKnow}.tsx` | `frontend/src/test/`; manual browser run (log, Step 9) | — |
| 14 | One-command start (Docker Compose), demo script | ✅ | `docker-compose.yml`, `backend/Dockerfile`, `frontend/{Dockerfile,nginx.conf}`, `scripts/demo_seed.py`, `docs/DEMO.md` | Manual run (log, Step 10) | — |
| 15 | Routing score: stub or first version | ✅ | `app/routing/` (semantic: MiniLM + LR/SVM, cross-encoder evidence), `app/pipeline/steps/{analyze_route,route}.py` | `tests/test_semantic_routing.py`, `tests/contracts/test_routing_contract.py` | **Tongkai**, integrated (`docs/ROUTING_PATCH.md`). Needs `python -m app.routing.prepare` once |
| 16 | RAG: stub or first version | ✅ | `app/rag/medical_hybrid.py`, `app/admin/materials.py` (uploads) | `tests/test_medical_hybrid.py`, `tests/test_material_sync.py`, `tests/test_rag_mvp_validation.py` | **Siyun**, integrated: MedlinePlus (5 topics) + instructor uploads; 10-question fixture Recall@1 100% (`docs/RAG_MVP_VALIDATION.md`) |
| 17 | Student feedback survey | ✅ | `app/api/v1/survey.py`, `frontend/src/components/FeedbackSurvey.tsx`, admin tab Feedback | `tests/test_survey.py`, `frontend/src/test/Survey.test.tsx` | Siyun. Ratings only, no IDs, aggregates of 3 or more |
| 18 | Privacy evaluation and audit | ✅ | `eval/privacy-filter/` (E6), `eval/privacy-audit/` (E4) | CI smoke runs | Report section `docs/report/privacy_subsystem.md` |

## Open items that block nothing in the code but matter for the MVP demo

- [ ] Dr. Abbas reviews the HBP draft (items, misconception corrections), then `reviewed_by` is set in the YAML.
- [x] Cloud key for testing (DeepSeek, Oct 19). [ ] The client approves the provider and data location; spending limit.
- [x] Tongkai and Siyun confirmed the integration (PRs #2, #3): privacy at the cloud gate, local fallback with a notice.
- [ ] Inform the professor of the deletion rule (design §8.3).
- [ ] Install `en_core_web_lg` and run `python -m app.routing.prepare` on the machine that runs the server (the Docker image does not yet contain the routing and evidence models).
- [ ] Merge the report sections (privacy, routing, RAG) for Oct 21 (Jira G1-83).

## Done early (planned for Beta)

The understand step and weak evidence; misconception tracking and corrections in answers; the instructor dashboard; the evaluation harnesses E1–E4 and E6.

## Not in the MVP

The other four topics' reviewed content; web search for up-to-date evidence (Jira G1-92); the privacy upgrades in [隐私升级.md](隐私升级.md) (scan instructor uploads, multi-turn, local LLM second pass); routing items still to agree with Tongkai (TODO.md §1.3–1.5).
