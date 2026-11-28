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
| week of 11/24 | Z confirms the AWS details and the domain with Prof. Abbas; deployment meeting with the TA, Jean (meeting of 11/25) |
| 12/1 | GPU / local model cost report to Prof. Abbas (`docs/GPU_COST.md`, merged in #162); Design Day dry run (Q16) and feature freeze |
| 12/2 | Final prototype presented in class |
| 12/3 | Design Day: live demo, on the production site if V10 is done, otherwise on the lab build |
| 12/13 | Final report |

## 1a. First priority: the product is renamed ScholarMind AI (decided by Z on 2026-11-25)

The product is renamed from PACT (Privacy-Aware Course Tutor) to **ScholarMind AI**. This comes before every
other task of this plan.

| ID | Task | Owner | Done when |
|---|---|---|---|
| X9 | **Rename to ScholarMind AI** in the repository, the same scope as T11: the name in the interface (English and French), the tab title, the API title, README, AGENTS.md, the manuals, file header comments, the Grafana dashboard, the web page fetcher's User-Agent, the current docs; the domain ideas (`DOMAIN_NAMES.md`) proposed again with the new name. Internal names stay (`tutor` database user, `tutor_*` metrics, package names, storage keys such as `pact.privacyNotice.seenBy`, the repository name); history and earlier plans keep the old name. | Z | PR merged; the browser shows ScholarMind AI on the login page, the sidebar and the tab title |
| X9b | Outside the repository: the video, the Design Day slides and script, the cost report sent to Prof. Abbas, the final report and the domain (V11) use the new name; the GitHub repository name only if Z decides so | Z, all | each item checked |
| X9r | **Back to the name PACT** (Z, 2026-11-28): the Design Day registration carries the name PACT and cannot change. Revert of X9 (#166): interface (English and French), tab title, API title, README, AGENTS.md, manuals, file headers, Grafana, User-Agent, domain ideas. The Compose project keeps a fixed name, now `pact` (images `pact-api`, `pact-proxy`). The ScholarMind version stays on the locked branch `archive/scholarmind-2026-11-28` | Z | PR merged; the browser shows PACT on the login page, the sidebar and the tab title |
| X10 | **Biomedical engineering course type** (`biomedical_engineering`, Z 2026-11-25, for Prof. Abbas's BMG5109 / ELG6131 course): the health rules of `medical_science` and the engineering rules of `ece` in one profile, a subject prompt with the health safety rules, web search sites, its own routing heads (`data/routing/models/biomedical_engineering/`, 154 questions in `data/routing/bme_questions.jsonl`; held-out route accuracy, mean of ten group splits, 0.73-0.74 -> 0.92-0.94, outside the training support 20% -> 0%: `eval/routing-bme/results/report.md`) and a held-out privacy set (`eval/privacy-filter/bme_holdout.jsonl`, results `eval/privacy-filter/results/x10/report.md`) | Z | PR merged; the type can be chosen when a course is created |
| X10b | **Privacy rules for biomedical engineering text**, from the X10 set: health readings and devices of the student or a relative, bare keys and tokens, grades without a grade word, repository URLs on other hosts; and not taking "my ECG trace" in a lab question as the student's own health | Z | E6 and the course sets before and after, not worse; leak on `bme_holdout.jsonl` lower |
| Z25c | Binary codes in a DAC or truth table ("111110101", "0 1 0 0 0 0 0 0 0") are not student numbers: two lecture notes of the real course were refused as STUDENT_ID | Z | PR merged; E6 identical |

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
| X7 | **Tell the student when the tutor is busy.** Today a question waits silently for a free model slot (`app/llm/gateway.py`: at most `limits.models.max_concurrent` = 8 at a time, up to `queue_timeout_seconds` = 60 s), and only after that says "the model is busy; try again in a moment". In the load test of #162 the slowest answer at 32 students took 48 s. Change: when a question has to wait for a slot, or no text has arrived after a few seconds, the answer stream sends a new event (additive in v2, no question text) and the chat shows a notice such as "Many students are asking right now. Your question is in line and will be answered shortly." (en and fr), which goes away when the answer starts. The same notice on AI drafts and quiz drafts that wait. When the wait ends in the busy error, the message says that it was high volume and offers to send the question again. | Z (gateway, stream event), T (chat and draft UI) | backend test with a fake model and a full gateway (the event is sent, no text in it); frontend test of the notice and its removal; checked in the browser with `eval/load-test/app_load.py` at 32 students against a copy of the demo database |
| X8 | **Drafts may write new examples and exercises; facts stay from the material.** Today every tier 1 draft, local and cloud, gets the same rule (`instructor_ai/drafts.py` `_RULES`: "Use only the supplied material; do not invent facts ..."; a custom draft adds "from the passages only ... say so instead of inventing it"), so a request for a worked example on a lecture without one returns "the material has no example" on both models. Change the rule by what is written, not only by the model: worked examples, practice questions, analogies and scenarios may be new, built on the concepts and formulas of the passages; dates, grading, requirements, citations and facts or numbers not in the passages are never invented. Cloud drafts (public material only, V16, unchanged) get the new rule; the local 9B model either keeps the strict rule or gets it with a note on the draft ("examples are generated; check them"), decided by Z from the comparison. Prompt change only; no privacy rule, no cloud gate change. | Z (S's component, Z allowed) | design note agreed by Z first; then the V16 method before and after (five drafts per kind, the lecture-3 worked example among them, local and cloud): usable drafts and invented facts counted; **after Design Day** (section 2a: no behaviour change in the last week) |
| V24 | **A new page starts at the top** (the app scrolls inside `main`, so a new page kept the old position); back and forward return to the old position. Branch `fix/V24-scroll-position` is ready. | T | PR merged |
| — | Review and merge #163 (tests run the deployment's pipeline, UTC database sessions, no local Ollama defaults) | Z | merged |
| — | Retest after Phase A: the failed and not-run items of section 0 (a dated quiz, a one-passage case, saving one admin setting back to its value) | Z (agent) | report in `var/` |

## 2a. Quality before Design Day (Prof. Abbas, meeting of 2026-11-25)

Prof. Abbas: in the last week, **quality only, no new features**. The platform has to look professional and be
stable, fast and private: no information leaks, and no one can break into the database. He will use it in the
winter term in one small course (under 20 students), so students will also need an orientation. Research on
the deployment environment and on GPUs waits until after Design Day; for Design Day the AWS deployment uses
Z's vLLM server, reachable from the internet (V12).

How this phase runs:
- Q1 comes first, because it finds the work; then the Q tasks run in parallel. One task, one branch, one PR, as
  in section 2.
- Fixes only. A fix may add a field (additive v2) only when it cannot be done otherwise.
- Browser checks use fictional accounts and questions only.
- X8 changes what drafts may write. It is a behaviour change, so it moves to after Design Day unless Z decides
  otherwise. V23 stays in section 5.
- Feature freeze from 12/1: after the dry run (Q16), only fixes for what the dry run finds.

**Professional look (interface and user experience)**

| ID | Task | Owner | Done when |
|---|---|---|---|
| Q1 | **Walk through every page** as a student, an instructor and an admin, in English and French, on a desktop (1280 px) and a phone (375 px), in light and dark mode. Note inconsistent wording, labels and spacing; empty states (no course, quiz, announcement or data yet); loading states; error messages that show raw codes; untranslated text; broken layouts. Give each finding a severity | Z (agent), T | report in `var/`; findings listed in this section; every major one fixed |
| Q2 | **First use.** A student's first login: join with an invitation code, the privacy notice, Personalize, the first question. An instructor's new empty course: create a module, upload, publish, invite students. Add short in-app hints where a step is unclear. Update the student and instructor manuals with screenshots of ScholarMind AI (also the base of the students' orientation in the winter) | Z, T | both flows done in the browser without help; manuals updated |
| Q3 | **One brand.** The ScholarMind AI name, mark and favicon are the same on the login page, sidebar, browser tab, invitation texts, manuals, Design Day slides and video | T | checklist done |
| Q4 | **Accessibility re-check** after the v5 and v6 changes: axe tests cover the new parts (announcements, the busy notice, statistics captions, routing panel step); keyboard path through chat and quizzes; contrast in dark mode | T | axe tests pass for every page; `ACCESSIBILITY.md` updated |

Q1 findings (walk-through of 2026-11-25 on the local Compose stack from `main` da9cb32, demo build with 4
courses and 6 students; report `var/q1/report.md`): 5 major, 21 minor. Every page loads in under 2 s, there is no
horizontal scroll on a phone, and French and dark mode render cleanly. Decisions by Z on 2026-11-25 are in the
last column.

| ID | Major finding | Fix |
|---|---|---|
| Q1-01 | The student's routing panel shows internal values ("Routing · LR", "Estimated Cloud need: 4.3%", "Support coverage: 0%", "0.000 s") and an unfinished-looking sentence | Z: plain-language steps by default; the technical values move into a collapsed "Details" (shown at Design Day) |
| Q1-02 | "Found by search but not checked for relevance" under an answer whose panel says the material was checked (after X2, the check ran and confirmed none) | its own note when the check ran but confirmed none |
| Q1-03 | "Kirchhoff's current law" read as a person: the model gets "<PERSON_1>'s current law", and the placeholder shows after a reload | Z: Z22c now (allow-list of fixed course phrases, never a bare surname), with an E6 re-run; placeholders shown as "[name]" |
| Q1-04 | First visit to a course: the page opens scrolled down and the suggestion cards are hidden behind the question box | the first view starts at the top; notices kept compact |
| Q1-05 | Admin and instructor rosters show name, e-mail and last login | Z: keep (needed to manage accounts; learning data stays hidden) |
| — | A public MIT 6.002 lecture refused at upload: formula subscripts extracted as 9-digit runs read as STUDENT_ID | with Q1-03: digit runs inside formulas are not student numbers in the document scan; E6 not worse |

The 21 minor findings (Q1-06 to Q1-26: source titles, empty states, French slips, instructor and admin wording,
the materials and members pages, phone layout of tables) are fixed in two PRs: student pages and instructor/admin
pages. The conversation list in the student sidebar (Q1-08) uses the existing API (decided by Z).

**Stable**

| ID | Task | Owner | Done when |
|---|---|---|---|
| Q5 | **Retest and regression.** Retest the section 0 items not yet run (a dated quiz, a one-passage case, saving one admin setting back to its value) and the main path of every role. Run it on a fresh build from `main` with the demo data | Z (agent) | report; every failure is fixed or explained |
| Q6 | **Failure behaviour.** What students and instructors see when the local model is down or slow, or the cloud is off; when the worker restarts during an index rebuild; when the database restarts. Every case shows a clear message, never a blank page or a raw error, and the app recovers without a manual restart | Z | each case checked on the local Compose stack; fixes come with tests |
| Q7 | **Believable demo data** (section 6 item): course titles, repeated first names, the unhelpful stored answer (M7), the test leftovers removed. Enough consenting demo students that some topics reach the minimum group (X5), so the statistics are not all hidden | Z | demo database rebuilt |
| Q8 | **Soak run.** 60 minutes of mixed use by a few scripted fictional students (`eval/load-test/app_load.py` at a low rate) on the deployment candidate. Watch errors, response times, memory and the worker queue | Z | report: no errors, memory flat |

**Fast**

| ID | Task | Owner | Done when |
|---|---|---|---|
| Q9 | **Measure, then fix the largest delays.** Measure on the Compose stack: page load (first and later visits), time to the first answer token and to the full answer on the local model, routing step duration, and the web search step (M4: about 30 s). Targets at normal load: pages under 2 s, first token under 5 s. Fix the largest delays found (for example a time cap on the web search step, or slow queries in the database log) | Z, T | numbers before and after, in the report |
| Q10 | **Frontend delivery.** Caddy sends hashed assets with a long cache and `index.html` without cache, compressed; check the bundle size after T16 | T | Lighthouse performance at least 90 on login and chat (desktop) |

**Private and secure**

| ID | Task | Owner | Done when |
|---|---|---|---|
| Q11 | **E4 moves here** (section 4): an end-to-end privacy audit of announcements in retrieval, web search queries, KC codes, stored notes and the local check on by default. Also check that after a test run the Compose stack's logs and the course exports contain no question text | Z | report; E6 not worse |
| Q12 | **Security re-check of the deployment** against `SECURITY_REVIEW.md` "Before the public deployment": the production Compose file (secure cookie, API v1 off, `SITE_ADDRESS`); HTTPS only; security headers (CSP, HSTS); login rate limit; CSRF; the database not published; no default or initial passwords left (admin, Grafana); secrets only in the server's `.env`; image scan (Trivy) with no fixable HIGH or CRITICAL | Z | checklist done on the AWS stack after V10 |
| Q13 | **Attack checks** on our own deployment, fictional data only. Try: another course's IDs (covered by `test_access_every_endpoint.py`); uploads (a path in the file name, a zip bomb, an oversized file, a wrong type); the web page fetcher against internal addresses (SSRF); Markdown and HTML in answers and announcements (XSS); injection through search and filter parameters; login brute force. Write down the results | Z | report; every finding fixed, or accepted with a reason |
| Q14 | **The local model on the internet** for Design Day (V12, Z's server): vLLM with `--api-key`, HTTPS, one open port, and if possible a firewall that admits only the AWS server's address. The deployment sets `VLLM_KEY` | Z | checked from outside: a request without the key is refused |
| Q15 | **The database at rest**, with Jean and V10: daily backups and a tested restore; the database user has only the rights it needs; the AWS volume encrypted at rest; retention of exports and logs as documented | Z, Jean | restore test done; settings written in `OPERATIONS.md` |

**Dry run**

| ID | Task | Owner | Done when |
|---|---|---|---|
| Q16 | **Design Day dry run** on the deployed site with `DEMO_SCRIPT.md`: all three roles, English and French, one phone, timed | all | done by 12/1; every failure fixed or cut from the script |

## 3. Phase B: production (blocked on Prof. Abbas)

| ID | Task | Owner | Done when |
|---|---|---|---|
| V10 | AWS deployment: Compose stack on Prof. Abbas's account, Canadian region, only this project's resources; HTTPS on the domain; monitoring and database backups; `AUTH__COOKIE_SECURE=true`, API v1 off | Z | the domain serves ScholarMind AI; a restore from a backup tested |
| V11 | Domain: Prof. Abbas chooses from `docs/DOMAIN_NAMES.md` and buys it | Abbas | name chosen |
| V12 | Local model for production: RunPod or the lab vLLM forwarded, HTTPS, `VLLM_KEY` required, one port (`docs/DEMO_VLLM.md`) | Z decides | the production site answers through it |
| — | Alert receiver in `alertmanager.yml` | Abbas, Z | set |
| V17 | The browser test again on the production site, all roles | Z (agent) | report; every failure has a task |

## 4. Phase C: evaluation and privacy (after the video)

| ID | Task | Owner | Done when |
|---|---|---|---|
| E4 | End-to-end privacy audit on v5: announcements in retrieval, web search, question KC codes, stored notes, the local check on by default (**moved to Q11**, section 2a) | Z | report |
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
| Design Day script (`docs/DEMO_SCRIPT.md`) checked on the build that will be shown (Q16) | T, Z | dry run done |
| Demo data: course titles with 2004, repeated first names, the unhelpful stored answer (M7); remove the test leftovers of 2026-11-24 on the dev server ("Lab note" announcement, "Retest quiz (temp)") (Q7) | Z | rebuilt or cleaned |
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
