# To do (v4 and v5)

The task list is section 7 of [docs/v4-implementation-guide.md](docs/v4-implementation-guide.md) (owners, sprints,
dependencies, "done when"); Jira project G1 tracks the same tasks. This page is the short status of 2026-11-15.
The state of each area and the decisions taken are in [docs/HANDOVER.md](docs/HANDOVER.md).

v5 (from the meeting of 2026-11-17): tasks, their state on 2026-11-20 and the findings of the V17 browser
test (W1 to W27) are in [docs/v5-plan.md](docs/v5-plan.md), sections 0 and 9; the decisions of 2026-11-20 and the next tasks (V18, Z22b, V19, Z22c) in section 10. V18 (edit the wording of KCs and check items): PR #138. V19 (a course type as one package, including routing): merged (#140, #141). V21 (quiz options that differ only in case, decided 2026-11-21): fixed, see section 10. V16 draft quality before and after: measured in `eval/v16-drafts/results/report.md`; its follow-ups (cloud structure drafts need the JSON schema, larger output limit for one-text drafts) are not tasks yet. V20 (course announcements, approved by Z on 2026-11-21): PR open. The table below keeps the v4 items.

## Deadlines (syllabus)

Reflection #2 (ethics, individual) 11/18 · video 11/25 · Design Day 12/3 · final report 12/13.

## Done

- **Platform (Z1 to Z15)**: courses and modules, accounts and invitations, settings layers, PostgreSQL, model
  gateway, privacy profiles, document scanning, API v2, usage limits, CSRF, end of term and export, instructor
  AI tier 4, CI scans and monitoring configuration, operations manual.
- **Learner, content and instructor AI (S1 to S11)**: course retriever and materials on API v2, the
  eight open course packs, instructor AI tiers 1 to 3, the course-level knowledge model (the default), visibility modes, overview and learning plans, retrieval
  evaluation on all eight packs.
- **Quizzes and the end-of-term survey (Q1)**, decided at the advisor meeting of 2026-11-12.
- **Frontend on API v2 (F1, carrying T6 to T8)** with the UI upgrade (U1 to U5), accessibility (T11), manuals
  (T12), routing evaluation on ECE and CS (T4), question type (T5), demo build (T9).

## Open

| ID | Task | Owner | Status |
|---|---|---|---|
| T13 | Web search evaluation (G1-106) | T | search built (#88: off / API / SearXNG); evaluation needs SearXNG or a key |
| T10 | Video (11/25) | T | demo script merged (#116) |
| T11 | Renaming | T | done: PACT (2026-11-17, kept at the meeting); rename again only if the client picks another name with the domain |
| T12 | Routing, frontend and web search handover notes | T | manuals done |
| — | `transformers` 5, `react-router` 7, `katex` done (Z27); `vite`/`vitest` (dev-only advisories) | T, Z | partly done |
| Z13, Z6, Z2 | Deploy on the test host with monitoring; vLLM load test; local speed of the 9B model | Z | waits for server access |
| Z13 | Choose the alert receiver | Z | waits for the client |
| S12 | Self-review and handover checklist | S | handover notes in `docs/history/s-tasks/` |
| S13 | Learning profile for the whole course: one onboarding and diagnostic per course (not per module), a course summary on My progress and in the instructor's view | S (frontend with T) | not started |
| S14 | Review how retrieval passes course material to the local model, above all the syllabus: paraphrased questions must still be answered (paraphrase test set per pack); dev server 2026-11-17: "When does the course end?" and a misspelled question miss the CS50x syllabus | S | retrieval part merged (#136), accepted with small losses on 6.006, 7.03 and HST.151; circ-28, garbled questions and the evidence step left |
| S15 | Demo courses get knowledge components, check items and a quiz (drafted by the instructor AI); a test that a quiz attempt moves the mastery estimate | S | done: `build_demo.py --learner-content`; test in `test_quizzes_v2.py` |
| S16 | Course type of the CS50x pack (`ece` gives a CS course the ECE subject prompt) | S | done: `computer_science` profile (ece recognizers, computing prompt) for CS50x and 6.006 |
| T15 | Routing by subject: the routing heads are trained on medical questions only; harder ECE questions get no sources | T | not started |
| T16 | Student chat: after opening a past conversation there is no way back to a new, empty conversation | T | done: New chat while the first answer was still streaming did nothing (`c` stays empty, no rebuild); it now carries a stamp in the router state and also closes the phone sheet; UI tests added |
| T17 | Course-rule questions routed to the cloud skip retrieval ("Can I use ChatGPT for the problem sets?" gets no syllabus) | T | done: the capability gate no longer skips retrieval inside a course or for logistics questions; the passages reach the cloud only through the CloudRequest; end-to-end test added |
| Z22 | Privacy filter tests: held-out ECE set, `life_science` and `general` sets, E6 scores for the v4 types, a fresh held-out medical set | Z | partly done: ECE, computer science, `life_science`, `general` sets and E6 re-run done; the medical set is open; rule fixes: low-risk part in PR #139 (Z22b), allow-list for course terms later (Z22c), v5-plan.md section 10 |
| — | Model behaviour from the browser tests of 2026-11-21 (M1 to M7: invented details in examples, general knowledge without material, web sources named as course material, slow web search, a cloud failure, long answers, unhelpful demo answers): evaluate and decide (docs/v5-plan.md section 10) | Z, S, T | open |
| V10 | AWS deployment on Prof. Abbas's account with the domain (V11), monitoring and backups; then the browser test again on the production site | Z | waits for the AWS details |
| V13 | GPU / local model cost report to Prof. Abbas (12/1), with the Z23 numbers and the token-limit research | Z | written: `docs/GPU_COST.md` (lab RTX 5060 Ti 16 GB, fp8 weights and fp8 KV: 45 to 49 answers a minute through the whole app at 32 students, none refused; one card for one class up to about 150; class sizes 30 to 200; other GPUs estimated by bandwidth); to send to Prof. Abbas |
| E4 | End-to-end privacy audit on v5 (announcements in retrieval, web search, question KC codes, stored notes) | Z | open |
| V19 | Routing heads per course type: train ECE (and CS) heads from their question sets with a before/after report; no type has its own heads yet | T | open |
| — | The 30 revised diagnostic items: decide whether to apply the AI review's suggestions (harder advanced items, more plausible distractors) and confirm the audience (undergraduate or medical school) with the client; a person approves them (`docs/review/AI_REVIEW_2026-11-22.md`) | Z | to decide |
| — | Web audit and UI check leftovers (screen-reader names for wide tables, page title while loading, KaTeX woff2, manual Safari Chinese input and screen reader checks) and admin page gaps (delete a misconception, edit `checkers` / `knowledge_model`, course types as a list, system model connections for instructors) (docs/v5-plan.md section 6) | T, Z | open |
| — | Demo data: course titles with 2004, repeated first names, the unhelpful stored answer (M7); rebuild the demo questions after the fixes | Z | open |
| — | M8: local AI drafts fail when the JSON is cut at 2048 tokens | Z | fixed in the M8 PR: the local model looped inside the JSON (spaces or passage numbers) in 17 of 24 runs; local tier 1 drafts now answer in Markdown (0 of 48 cut off); report `eval/load-test/M8_DRAFT_LOOPS.md` |
| — | Research the 2048-token limit (output lengths per call kind, why drafts reach it, cost of a cut-off, GPU time and slots, cloud reasoning tokens) and re-audit the GPU choice and `llm.local.max_tokens` (now 2048, was 1024) together: answer length and time per answer at 2048, then GPU and `max_concurrent` (docs/v5-plan.md section 10, V22) | Z | measured (`eval/load-test/TOKEN_LIMIT_RESEARCH.md`): answers median 300, p95 868 tokens, none cut; detail answers with a table 1 of 64 cut (a long table, not a loop); tier 2 and quiz drafts never cut; a 2048-token call holds a slot 47 s alone, up to 127 s at 16 at once, against `timeout_s` 60. Options A to G for Z (model settings: Z decides); then V13. Z chose (V13 settings PR): local answers stay 2048 (3072 helped nothing in the app load test), local `timeout_s` 120, quiz drafts 4096, cloud `max_tokens` 8192 and `timeout_s` 60 (long questions: 9 of 12 cut at 2000), `max_concurrent` 8 |
| Z23 | vLLM capacity: tokens per second in the load test, runs at 1 to 32 at a time, model limits set from them, step timing of one ask, GPU for more than 5 students at once | Z | needs the test host |
| Z24 | The deployment's local model is its vLLM (`VLLM_BASE_URL`, `VLLM_KEY` replace `OLLAMA_URL`) | Z | done (#107) |
| Z25 | Document scan refuses public course text (CS50x `pset_5.md` as `GRADE`); check all eight packs | Z | done: three allele exceptions never matched (a backspace instead of `\b`); 0 of 304 pack files refused |
| Z25b | Web pages as draft sources refused as student data: the identifiers of a reference list (S2CID, arXiv, hdl, ProQuest, PMID, OCLC, …) looked like student numbers (5 of 7 Wikipedia pages refused, browser test of 2026-11-22) | Z | fixed in the Z25b PR (E6 identical); left: a journal volume and article number such as "150 104526" matches the SIN pattern on pages full of "sin" (Fourier transform) |
| Z26 | The module guideline (Modules page) is stored but never reaches the answering model; use it for questions scoped to that module | Z | done: course and module guidelines reach the answering model (local and cloud) |
| Z27 | Security review of the whole system (auth, CSRF, access, SSRF, uploads, prompt injection, proxy and networks, keys, logs, scans), report in `docs/SECURITY_REVIEW.md` | Z | report merged (#117); H1, M1, L4 fixed; M2, M3, M4 fixed (#130); L1 to L3 fixed (#132) |

Not this term: targeted material for single students (only the learning plan with notes now). Tests and demos
use the eight open course packs in `data/demo_courses/`.

## Waiting for others

- Course server access: deployment, vLLM load test, Z2 local speed, monitoring.
- The client: cloud provider and billing, alert receiver, project name.
