# v6 plan (draft of 2026-11-24)

Source: the state of v5 on `main` (df779bc, PRs up to #162), the browser test of 2026-11-24 on the dev server
(local report `var/browser-test-2026-11-24/report.md`), the open items of [v5-plan.md](v5-plan.md) and
[TODO.md](../TODO.md). The guide's rules ([v4-implementation-guide.md](v4-implementation-guide.md) section 2)
apply unchanged. New task IDs are `X1`...; v4 and v5 IDs (`E4`, `T13`, `V10`, ...) are kept.

## 0. Where v5 stands

Every decision of the meeting of 2026-11-17 is implemented and merged except the deployment (V10 to V12),
which waits for the AWS details. Details are in [v5-plan.md](v5-plan.md) sections 0 and 10.

Browser test of 2026-11-24 (dev server on df779bc, lab vLLM up, fictional accounts and questions only):

| Area | Result |
|---|---|
| Privacy (#159, #160) | Pass. A cloud-bound question with "I have asthma ..." or "I have a perianal abscess ..." is answered by the local model; the asthma case shows "A privacy check kept this question on the local model." |
| Student pages (#145, #147 to #150) | Pass: French chips, compact announcements, one scroll area, routing steps in plain French, "Score :", phone banner, logistics and module questions get material, reopened answers keep sources, badge and notes |
| Cloud limits (#161) | Pass: a long cloud answer (about 3,950 characters) is complete |
| Instructor pages (#146, #155 to #157) | Pass: privacy refusal names only the type, equal options refused before save, "Saved.", focus after pin, end of term link, show-password button, drafts stop spinning and are valid, a failed draft gives a reason without the class name, a Wikipedia URL is accepted, a 12-question quiz draft finishes |
| Statistics only (#151) | Pass: the switch is off; no individual student page |
| Web search answer (M3) | **Fail**: the answer is right and its source is python.org, but it starts "According to the course material" |
| Not run | quiz times without seconds (no dated quiz), "1 passage" (always 4 found), saving the admin settings |

## 1. Dates

| Date | What |
|---|---|
| 11/25 | Video submitted (rough cut of part 1 is ready) |
| week of 11/24 | Z confirms the AWS details and the domain with Prof. Abbas |
| 12/1 | GPU / local model cost report to Prof. Abbas (`docs/GPU_COST.md`, merged in #162) |
| 12/3 | Design Day: live demo, on the production site if V10 is done, otherwise on the lab build |
| 12/13 | Final report |

## 2. Phase A: fixes from the browser test (before Design Day)

Each is one task, one branch and one PR (AGENTS.md workflow). Order is the order below.

| ID | Task | Owner | Done when |
|---|---|---|---|
| X1 | **Web sources named as course material (M3).** Web passages are labelled as web sources in the answer prompt (local and cloud), and the prompt says not to call them course material. | Z | a test on the built prompt; browser: the Python version answer names python.org, not "the course material" |
| X2 | **"Since no course material was provided" although passages were found.** Seen on CS50x whole-course questions: the routing says "Found 4 passages", the local answer says no material was provided and shows no source. Find where the passages are lost (relevance filter, evidence selection, prompt budget), then fix. Related to M2. | Z (with S for retrieval) | cause written in the PR; a test with fake models; the browser case answers from the passages with sources |
| X3 | **Routing panel after a privacy override.** When the privacy check keeps a cloud-routed question on the local model, the panel still ends with "Cloud model chosen." Add a step that says the privacy check kept it local (en and fr; no question text). | T | the asthma case shows the extra step; frontend test |
| X4 | **Answer the course question when a health detail is given.** For "I have a perianal abscess and need to submit my assignment late ...", the local model refused the whole question. The tutor should answer the course part (late policy, how to contact the instructor) without medical advice. Prompt change only; no privacy rule change. | Z | the case and the asthma case answered on the lab vLLM; E6 not affected (no rule change) |
| X5 | **"Most asked topics" empty with 6 active students.** Check that only consenting students count (expected) and whether the demo data simply has fewer than 5 consenting students; if so, say in the UI that only students who agreed to learner data are counted. | S | cause written; the caption explains who is counted |
| X6 | **Small UI items**: a source shown as an internal path (`course/5/73/05_week_4_memory.md`) instead of the file title; French "1 réponses"; no character counter seen on the announcement title at 217 characters (B11); the "Students per level" heading shown twice; check that an instructor can delete an announcement (the tester found no delete button). | T | each item fixed or explained in the PR; frontend tests |
| V24 | **A new page starts at the top** (the app scrolls inside `main`, so a new page kept the old position); back and forward return to the old position. Branch `fix/V24-scroll-position` is ready. | T | PR merged |
| — | Review and merge #163 (tests run the deployment's pipeline, UTC database sessions, no local Ollama defaults) | Z | merged |
| — | Retest after Phase A: the failed and not-run items of section 0 (a dated quiz, a one-passage case, saving one admin setting back to its value) | Z (agent) | report in `var/` |

## 3. Phase B: production (blocked on Prof. Abbas)

| ID | Task | Owner | Done when |
|---|---|---|---|
| V10 | AWS deployment: Compose stack on Prof. Abbas's account, Canadian region, only this project's resources; HTTPS on the domain; monitoring and database backups; `AUTH__COOKIE_SECURE=true`, API v1 off | Z | the domain serves PACT; a restore from a backup tested |
| V11 | Domain: Prof. Abbas chooses from `docs/DOMAIN_NAMES.md` and buys it | Abbas | name chosen |
| V12 | Local model for production: RunPod or the lab vLLM forwarded, HTTPS, `VLLM_KEY` required, one port (`docs/DEMO_VLLM.md`) | Z decides | the production site answers through it |
| — | Alert receiver in `alertmanager.yml` | Abbas, Z | set |
| V17 | The browser test again on the production site, all roles | Z (agent) | report; every failure has a task |

## 4. Phase C: evaluation and privacy (after the video)

| ID | Task | Owner | Done when |
|---|---|---|---|
| E4 | End-to-end privacy audit on v5: announcements in retrieval, web search, question KC codes, stored notes, the local check on by default | Z | report |
| Z22 | A fresh held-out medical privacy set; E6 on it | Z | set and scores in `eval/privacy-filter/` |
| Z22c | Allow-list for course terms that look like names (fixed phrases only, never a bare surname); a name after a role word ("my TA") | Z | design agreed by Z, then code; E6 and Z22 re-run, not worse |
| T13 | Web search evaluation, with the time of the search step (M4: about 30 s) and the source wording (X1) | T | report |
| — | Model behaviour M1 (invented details in examples) and M2 (general knowledge with thin material): measure with the grounding checker on the S11 sets, local and cloud | S | numbers in `eval/course-rag-packs/results/` |

## 5. Needs agreement first

| ID | Task | Waits for | Done when |
|---|---|---|---|
| V23 | Individual view by the student's choice (design in `docs/design/individual-view.md`) | Z approves the design; Prof. Abbas agrees before real students use it | code with access tests; the switch stays off by default |
| — | The 30 revised diagnostic items: apply the AI review's suggestions or not; confirm the audience | Lavin, the client | a person approves them |
| V19 | Routing heads for ECE and CS with a before/after report | T has time | report; routing not worse |
| S13 | One onboarding and diagnostic per course | after Design Day | — |

## 6. Report, demo and handover

| Task | Owner | Done when |
|---|---|---|
| Video: assemble the rest after part 1, add narration, submit | Z, all | submitted 11/25 |
| Design Day script (`docs/DEMO_SCRIPT.md`) checked on the build that will be shown | T, Z | dry run done |
| Demo data: course titles with 2004, repeated first names, the unhelpful stored answer (M7); remove the test leftovers of 2026-11-24 on the dev server ("Lab note" announcement, "Retest quiz (temp)") | Z | rebuilt or cleaned |
| Merge the v5 and v6 plans into the guide; update HANDOVER.md and TODO.md | Z | merged |
| Final report: same story as Design Day ("Brightspace plus", privacy first), measured numbers from E6, V16, V13 and the browser tests | all | 12/13 |

## 7. Still to confirm with Prof. Abbas

1. AWS: access, region, limits, and who receives monitoring alerts.
2. Domain name (V11).
3. The local model for production (V12) and its cost (V13 report).
4. Whether the individual view by the student's choice (V23) may be used with real students.

## 8. Not this term

Unchanged from [v5-plan.md](v5-plan.md) section 7: Brightspace-style assignments and grading, LTI and
university login, images in the knowledge base, larger GPUs unless the material needs them. Showing one
student's data to the instructor stays off unless V23 is approved.
