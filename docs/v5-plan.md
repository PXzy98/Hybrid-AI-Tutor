# v5 plan (draft of 2026-11-17)

Source: the weekly meeting of 2026-11-17 with Prof. Abbas (client) and Prof. Ismaeel (advisor), plus the open
items of v4 ([TODO.md](../TODO.md), open PRs, the UI checks). Where the two professors disagree, Prof. Abbas's
view is taken; Prof. Ismaeel's ideas are added where they do not conflict.

Until this plan is merged into [v4-implementation-guide.md](v4-implementation-guide.md), the guide's rules
(section 2) still apply unchanged. Task IDs: `V1`... are new in v5; v4 IDs (`S14`, `Z26`, ...) are kept.

## 0. Status on 2026-11-20 (evening)

Every v5 PR up to #136 is merged. The decisions Z took on the open questions and the next steps are in
section 10.

| Task | State |
|---|---|
| Open v4 PRs #102 to #107 | merged |
| V1 statistics-only instructor view | merged (#109) |
| V2 class statistics | merged (#115); small groups, differences and single scores hidden (#126) |
| V3 privacy notice | merged (#114); French screenshots sent to Lavin (Z, 2026-11-22) |
| Z26 instructor guidelines reach the model | merged (#110) |
| S15 demo learner content, S16 CS course type, Z25 pack scan | merged (#113, #111, #112); S16 checked with the vLLM |
| Backend French texts | merged (#124) |
| V4, V5, V6 free request, chosen sources, a file for one draft | merged (#119, review fixes in #120) |
| V7 web pages as material and as a draft source | merged (#120); W1 (Wikipedia refused the fetcher) fixed in #129 |
| V8 closed loop | merged (#123) |
| V9 accounts from term to term | merged (#118, review fixes #125) |
| V15 a student's own answer instruction | merged (#121) |
| V16 cloud drafts for public material | merged (#122). Before/after measured (`eval/v16-drafts/results/report.md`, 70 drafts on the lab vLLM): KC drafts no longer only repeat the course's KCs (edit effort 3.0 to 1.4; one draft of five fails when every item repeats), quiz stems about "the text" 8 to 2 of 25; the other five kinds send the same request (no change); usable drafts 15 to 22 of 35. Cloud: better one-text drafts, but KC, check item and misconception drafts fail (3 of 3: no schema, own field names) |
| V11 to V14, T10 notes | merged (#116): `DOMAIN_NAMES.md`, `DEMO_VLLM.md`, `GPU_COST.md`, `design/extension-points.md`, `DEMO_SCRIPT.md` |
| Z27 security review | merged (#117); H1, M1, L4 fixed; M2 to M4 fixed (#130); L1 to L3 fixed (#132) |
| V17 browser test | done on the integration build with the lab vLLM (all roles, en and fr, light and dark, desktop and phone width); findings W1 to W27 in section 9, fixed in #129 and #133 except W17 (decided, section 10) and W27 (check by hand); web search answers not run |
| End of term to next term | "Start next term's course" with materials (#133) |
| Settings bug from the meeting | Z to describe it; an empty "Enabled course types" field that switched course creation off was fixed in #127 |
| Routing test, Z23 capacity, answer quality on ECE and CS | done with the lab vLLM (#131): `eval/routing-ece/results/routing_test_2026-11-20.md`, OPERATIONS.md section 10, `eval/course-rag-packs/results/answer_quality.md` |
| Z22 privacy test sets per course type | merged (#134): E6 unchanged; rule changes decided in section 10 |
| V18 edit the wording of KCs and check items | PR #138: Edit dialogs on Course content; codes and learner records stay; duplicate active KC name 409; edits audited (field names only) |
| Z22b low-risk privacy rule changes | PR #139: E6 identical on every set; Z22 leak ECE 24.0% -> 4.0%, CS 12.5% -> 0.0%, general 6.7% -> 0.0%, over-redaction unchanged; the eight misses found (`eval/privacy-filter/results/z22b/report.md`) |
| V19 a course type as one package, including routing | merged (#140 design, #141 code): heads per type under `data/routing/models/<type>/` with fallback to the shared heads, `routing.by_course_type`, `train.py --course-type`, routing evaluation per type; no type has its own heads yet, so routing is unchanged |
| V21 quiz options that differ only in case | PR #142: "AA", "Aa", "aa" are different options; only options equal after trimming and collapsing spaces are refused (quizzes and AI check item drafts) |
| S14 retrieval, T16, T17 | merged (#136, #135) |
| V20 course announcements | approved by Z on 2026-11-21 (section 10); PR open: instructors write, pin, edit and delete; students see the latest on the course home and all under Announcements; privacy-scanned, audited without text |
| V10 AWS deployment | on hold (AWS details) |

## 1. Dates

| Date | What |
|---|---|
| 11/18 | Reflection #2; ask Prof. Gita about the midterm check meeting (in class) |
| 11/21 | Phase 1 done: open PRs merged, routing and class overview tested, privacy decision applied |
| 11/25 | Video (uses the v5 UI) |
| week of 11/23 | Z confirms the AWS details with Prof. Abbas; deployment work starts only after that |
| about 11/27 | First production version on Prof. Abbas's AWS with a domain (his plan: "end of next week") |
| 12/1 | GPU / local model cost report to Prof. Abbas |
| 12/3 | Design Day: live demo on the production site |
| 12/13 | Final report |

## 2. Decisions from the meeting

| Topic | Decision | Who said it |
|---|---|---|
| Name | Keep PACT for now; privacy stays the main message | Abbas, Ismaeel |
| What the instructor sees | **Statistics only**: how many students used it, how many questions, the most frequent topics and concerns. No individual activity, questions or exam answers under a student's name. | Abbas, with Lavin (Ismaeel wanted full visibility; overruled) |
| Individual view (mode B) | Not allowed in this version, including individual quiz scores and learning plans. The code stays but is switched off and hidden, so it can come back if the client asks. | Abbas decides; "keep it, hide it" from Ismaeel; confirmed by Z 2026-11-17 |
| Privacy notice | A clear notice at the top of the student side: what is private, that no one, not even the instructor, sees their activity | Abbas |
| Instructor rules for the tutor | Instructor guidelines (course and module) bind the tutor; students cannot override them. Without instructor rules the student may shape answers freely. | Abbas, Ismaeel agreed |
| Accounts | Own accounts in our own database (full control); class list by CSV with invitation codes; the instructor/admin manages accounts each term | Abbas |
| Draft with AI | Keep the drop-down, add a free request ("what to draft") and a free choice of source: the whole course, some modules, or named files. Two more inputs: upload a file, give a URL. | Abbas, Ismaeel agreed |
| Knowledge base | Not only uploaded files: instructors can add websites as sources; web search fills gaps | Abbas, Ismaeel |
| Closed loop | When quizzes show a student is weak on a topic, the tutor offers that student another explanation and outside resources (private to the student) | Ismaeel (no conflict) |
| Deployment | Docker Compose is fine. **On hold until Z confirms the details with Prof. Abbas next week.** Frontend, backend and database on Prof. Abbas's AWS; we only touch this project's resources; he buys the domain (GoDaddy) from the names we propose | Abbas |
| GPU | No fixed budget, but the cost must be justified; report the options. For the demo: vLLM on RunPod, or the lab vLLM port forwarded to the internet | Abbas; demo choice by Z |
| Brightspace features | Not built this term; leave clear extension points for the next team | Z 2026-11-17 |
| Positioning | "Brightspace plus": the course platform plus AI for teaching, research and industry training; learners are not only university students | Abbas |

## 3. Phase 1: finish v4 and apply the decisions (by 11/21)

| ID | Task | Owner | Done when |
|---|---|---|---|
| — | Review and merge open PRs #102 (docs), #103 (T15), #104 (T11), #105 (Z22 web security), #106 (T16), #107 (Z24 vLLM) | Z | done 2026-11-19 |
| V1 | **Statistics-only instructor view**: every course runs in mode A; the mode B switch, the acknowledge step and opt-out disappear from the UI; individual quiz results, the student sheet and learning plans are hidden; `visibility.mode_b_enabled` system flag (default `false`) keeps the code. Update consent text, manuals and guide 4.8. | Z (UI with T) | no endpoint returns individual learner data while the flag is off (access tests); manuals updated |
| V2 | **Class statistics**: active students, questions per week, most asked topics and misconceptions, quiz averages per question, all above the minimum group; the admin page shows the same counts across courses | S (UI T) | overview and admin show them with 5+ demo students |
| V3 | **Privacy notice** at the top of the student side (first visit and a permanent short line), en and fr | T | text approved by Z; screenshot in both languages |
| Z26 | Module and course guidelines reach the answering model, after the base rules; student preferences only apply where they do not conflict; a student cannot override them ("ignore the instructor") | Z | tests: right module only; override attempt fails |
| — | **Routing test** asked for by Prof. Ismaeel: run the routing evaluation and a manual ask on the local and cloud paths with the new vLLM setting | T | done 2026-11-20: `eval/routing-ece/results/routing_test_2026-11-20.md` |
| — | **Class overview test** with at least 5 demo students (`build_demo.py --students 6`), quizzes and the end-of-term survey answered (the survey showed "not available" in the meeting) | S | screenshots of the overview with data |
| — | **Settings bug** shown in the meeting (routing / model connection settings) | Z | Z describes it; fixed with a test |
| — | **End of term to next term**: export a course, import it as a new course with new dates, without student data, then invite a new class | Z | done once on the dev server; manual steps checked |
| S15 | Demo courses get KCs, check items and a quiz; test that a quiz attempt moves the mastery estimate | S | test asserts `p_mastery` changes after an attempt |
| S16 | Course type of the CS50x pack | S | done (manifest `computer_science`, computing prompt; test `test_computer_science_courses_get_the_computing_prompt`; checked 2026-11-20 with a real answer) |
| Z25 | Document scan refuses public course text; check all eight packs | Z | all packs upload |
| — | Backend French texts: consent text, preference questions, chat error messages (still English in the French UI; consent text still says "What I know") | Z | French UI shows no English from the backend |
| — | Send French UI screenshots to Lavin (she can check basic French; find a second reviewer for details) | Z | e-mail sent |

## 4. Phase 2: client features (by 11/25 for the video, 11/27 at the latest)

| ID | Task | Owner | Done when |
|---|---|---|---|
| V4 | **Draft with AI, free request**: kind "custom" with an instructor-written request (examples: refine or expand the course material on one topic, thesis or research topics, a summary of a new paper and what it means for patients, examples for a lecture, what to add to the course next), next to the existing kinds | S (UI T) | a custom draft from the CS50x pack; drafts stay unpublished until accepted |
| V5 | **Draft sources**: whole course, chosen modules, or chosen files (materials list), instead of one module | S (UI T) | retrieval limited to the chosen files (test) |
| V6 | **Draft from an uploaded file**: a tab to upload a file (for example a new paper) used for this draft only, with an option to add it to the course material; goes through `scan_document()` | S (UI T) | blocked file is refused; added file appears in Materials |
| V7 | **Draft from a URL / websites as sources**: a tab to give a URL; the page is fetched through the single outbound helper (https only, no private or local addresses, size and time limits), stored as a material with its address, and can be re-fetched | T (backend with Z for the outbound rules) | SSRF tests (localhost, 10.x, 169.254.x, redirects) refused; page text indexed |
| V8 | **Closed loop for the student**: after a quiz, weak topics on My progress get "explain it another way" (tutor answer in another style, with outside sources through web search when allowed); nothing is shown to the instructor except class statistics. Instructor side: topics weak for the class (aggregate, above the minimum group) suggest a draft of extra material, which the instructor reviews | S (UI T) | a weak KC after a quiz shows the action; works without instructor visibility |
| V15 | **Student's own answer instructions**: where the instructor set no rule, a student may also write how answers should be presented (free text, short, next to the answer-style choices); stored as a preference, scanned like question text, never shown to the instructor; ignored where it conflicts with the instructor's rules (Z26) | S (UI T) | test: a student instruction cannot override an instructor guideline |
| V16 | **Draft quality on the 9B model** (Z called it "not good enough" in the meeting): better prompts and passages for the instructor AI; for public material the instructor may choose the cloud model after the cloud notice (guide 4.9) | S | five drafts per kind compared before and after: done, `eval/v16-drafts/results/report.md` |
| V17 | **AI-driven browser test of every feature**: an agent operates a real browser and goes through each role's flows end to end (admin: accounts, model connections, settings; instructor: course and modules, materials, guidelines, AI drafts incl. upload and URL, quizzes, survey, statistics, end of term and import; student: invitation sign-up, privacy notice, chat on the local and cloud paths, web search, quizzes, My progress, "explain it another way", survey), in en and fr, light and dark, desktop and phone. Run on the dev server before the video (by 11/24) and again on the production site after V10. Only demo course packs and fictional accounts; generated test passwords stay in the git-ignored `var/`. Findings go into the task list | Z (agent) | report with screenshots per flow; every failure has a task |
| V9 | **Account management**: check what the admin and instructor can do each term (CSV import, invitations, reset a password, deactivate, remove from course) and add what is missing | Z | manual section; access tests |

## 5. Phase 3: production (about 11/27) and Design Day (12/3)

| ID | Task | Owner | Done when |
|---|---|---|---|
| V10 | **AWS deployment** (blocked until the AWS details are confirmed with Prof. Abbas) (replaces Z13's test host): Compose stack (Caddy, frontend, API, worker, PostgreSQL) on Prof. Abbas's account, Canadian region, only this project's resources; HTTPS on the new domain; monitoring and backups of the database | Z | the domain serves PACT; restore from a backup tested |
| V11 | **Domain name**: each member proposes names before the deploy; Prof. Abbas chooses and buys | all | name chosen |
| V12 | **Local model for the demo**: vLLM on RunPod, or the lab vLLM forwarded to the internet. Either way: HTTPS, `VLLM_KEY` required, only the API port open, the key only in the server `.env`; `VLLM_BASE_URL` points at it | Z | the production site answers through it |
| V13 | **Local model hosting cost**: options and costs (RunPod or another GPU in class hours only, 24/7, AWS GPU instance, own server), with the Z23 numbers; recommendation to Prof. Abbas | Z | report sent by 12/1 |
| V14 | **Extension points for course-platform features** (assignments, grading, announcements, LTI, university login): a short design note in `docs/design/` on where they plug in (data model, API v2 routes, frontend nav, permissions), no implementation | Z | note reviewed |
| Z27 | Security review of the whole system before going public (auth, CSRF, access, SSRF incl. V7, uploads, prompt injection incl. Z26, proxy, keys, logs, the public vLLM of V12) in `docs/SECURITY_REVIEW.md` | Z | report; high findings fixed before the deploy |
| Z23 | vLLM capacity (tokens per second, 1 to 32 at a time), model limits set from it | Z | measured 2026-11-20: numbers and recommendation (`max_concurrent` 8, timeout 60) in OPERATIONS.md section 10; limits not yet changed in `config.yaml` (one deployment setting, `limits.models.max_concurrent`, applied to each connection); full-ask timing open |
| — | Alert receiver for monitoring (ask Prof. Abbas) | Z | set in `alertmanager.yml` |
| T10 | Video on the v5 UI; Design Day live demo script on the production site; "Brightspace plus" story (teaching, research, industry training; learners include trainees and research groups, a bridge between academia, research and industry); one demo step uploads an open-access paper and drafts research topics from it | T, all | video submitted 11/25 |
| — | Final report and Design Day material carry the same story and the value for future research | all | report 12/13 |
| T13 | Web search evaluation (G1-106); Tongkai shows web search at the next meeting | T | report |
| E4 | End-to-end privacy audit on v5 (after V1, V7, Z26) | Z | report |
| — | Answer quality on non-medical courses (ECE, CS packs) with the vLLM model | S, T | done 2026-11-20 for 6.002 and CS50x (10 questions each): `eval/course-rag-packs/results/answer_quality.md` |

## 6. Remaining v4 items (in order, when time allows)

- **Retrieval (S14)**: merged (#136): stemming, typo correction, logistics synonyms, a weight for homework and
  exam files in course-wide questions and a semantic step with the router's encoder (`rag.semantic_retrieval`).
  Paraphrase set course-wide hit@4 0.48 -> 0.81, S11 course-wide hit@4 0.93 -> 0.95
  (`eval/course-rag-packs/results/s14-comparison.md`). Accepted by Z with small losses of one or two questions
  (6.006 course-wide hit@4 0.88 -> 0.84, 7.03 scoped hit@1 0.92 -> 0.85, HST.151 course-wide hit@1
  0.93 -> 0.89); those questions are the starting set for later tuning. Left: "when is homework 4 due"
  (circ-28) still misses (the calendar row names another homework's due date), very garbled questions, and the
  evidence step (cross-encoder) can still drop a retrieved passage.
- **Routing (T15, T17)**: routing heads trained on medical questions only; course-rule questions routed to the
  cloud skip retrieval (T17 done: retrieval now also runs when the capability gate chooses the cloud, inside a
  course and for logistics questions).
- **Privacy tests (Z22)**: held-out sets for ECE (41), computer science (30), `life_science` (30) and `general` (25) are in `eval/privacy-filter/` (`make_course_sets.py`, `course_sets.py`, scores in `results/z22/metrics.json`). E6 on main is unchanged since the last report (Z25 and S16 did not affect it). New sets, leak / over-redaction with the course's profile: ECE 24.0% / 6.2%, computer science 12.5% / 7.1%, life science 13.3% / 13.3% (0 of 13 within the profile's scope), general 6.7% / 10.0%. Misses: AWS secret key, quoted `tok_` values, passwords in URLs and prose, 172.16.x addresses, `git@` URLs; over-redaction: eponyms and thinker names (Hardy-Weinberg, Mealy, Kant). Merged (#134). Still open: a fresh held-out medical set, and the rule changes (decided in section 10: secret shapes, URL passwords, 172.16/12 and `git@` addresses first; the allow-list for course terms later).
- **T16 (chat, done)**: after opening a past conversation there is no way back to a new, empty conversation
  (fixed: New chat also works while the first answer is still streaming).
  Note: three merged PRs reused IDs of the task list: #106 calls itself T16 (code splitting), #103 T15 (forms)
  and #105 Z22 (web security; Z22 is the privacy test sets). The task list IDs above keep their meaning.
- **Web audit leftovers**: screen-reader names for wide tables; page title stays on the previous page while
  loading; required-field markers and a show-password toggle (need French text); KaTeX woff2 only; manual
  checks of the Safari Chinese input method (F1) and a real screen reader (A2).
- **S13**: one onboarding and diagnostic per course instead of per module.
- **UI check leftovers**: Materials file names break per character on phones (`Materials.tsx` `break-all`); no
  "saved" message on Settings; focus not returned after dialogs; survey radios wrap on phones; counts without a
  unit; empty top bar on some pages; long instructor sidebar; pale disabled buttons; favicon.
- **Admin page gaps**: misconceptions can only be retired, not deleted; system settings do not edit `checkers` /
  `knowledge_model`; course types are a text field; instructors cannot pick system model connections.
- **Dependencies**: done (Z27): `transformers` 5, `react-router` 7, `katex` 0.19; `vite`/`vitest` advisories are dev-only.
- **Handover (T12, S12)**: routing, frontend and web search notes; `docs/HANDOVER.md` and the progress pages.
- The 30 revised check items: AI review with web search instead of a second expert review (Z, 2026-11-22; `docs/review/AI_REVIEW_2026-11-22.md`); a person still approves them.
- From the client: real course material and an instructor to try the drafts; a maintainer after December.

## 7. Not this term (recorded for the next team)

- Brightspace-style course features (assignments with upload links, grading, announcements): Prof. Abbas's
  "Brightspace plus" direction, left to the next team; V14 records where they plug in.
- Running inside Brightspace (LTI) and login through the university (OAuth; `login_identity` is prepared).
- Anything that shows one student's data to the instructor (individual view, quiz scores, learning plans,
  targeted material); not allowed in this version.
- Images in the knowledge base and larger GPUs (only when the material needs it, per Prof. Abbas).

## 8. Still to confirm with Prof. Abbas (next week)

1. AWS: access, region, limits, and who receives monitoring alerts.
2. Domain name (V11).

## 9. V17 findings (browser test of 2026-11-19/20)

From the admin and instructor parts of V17 on the integration build of all v5 branches, demo course packs and
fictional accounts only. Severity as the tester rated it. "vLLM" marks findings that can only be checked again
with the local model.

| ID | Where | Finding | Severity |
|---|---|---|---|
| W1 | Materials, AI assistant: web page | Wikipedia answers HTTP 403 to the fetcher's User-Agent (`PACT-course-material-fetcher/1.0`, no contact address); the same request with a descriptive agent and an address gets 200 | major |
| W2 | AI drafts, quiz drafts (vLLM) | With the local model unreachable every draft fails with `LLMUnavailable: cloud API unavailable (APIConnectionError)`: it names the cloud and an internal class although the local model was chosen; the quiz draft says only "The draft failed" after about 90 s | major |
| W3 | AI assistant | The form keeps its values after "Draft with AI" and the button stays active, so a second click starts a duplicate draft | minor |
| W4 | Quizzes | A new quiz starts with an empty 4th option that is required, so Save fails until it is removed; "Draft with AI" appears only after the first save | minor |
| W5 | Quizzes list | "1 questions" (no singular) | cosmetic |
| W6 | French interface | File status "accepted" and the draft status chips are not translated | minor |
| W7 | Demo data | Demo students use e-mail addresses at a real university domain; fictional data should use `.invalid` | minor |
| W8 | Course content, system settings | Saving a course or module guideline, or the system settings, shows no "Saved." (the course Settings page does) | minor |
| W9 | Administration, system settings | Empty fields (levels, hysteresis, local model URL and name, course types) do not show the value in effect or say that empty means the default | minor |
| W10 | Administration, create an account | A duplicate e-mail shows "This was changed by someone else. an account with this e-mail exists" (the generic 409 text is put in front of the server's detail) | minor |
| W11 | Administration, reset password | The temporary password appears above the search box, out of view when the list is scrolled; no confirmation before the reset; an earlier banner stays | minor |
| W12 | End of term | No step that starts the next term's course from this one (only the YAML export and import on Content; materials are not carried); "0 students exported, 6 removed." next to "no individual student data" is unclear; the date line ends with ".." | minor |
| W13 | Class overview | The Module selector shows a module while "Whole course" is highlighted; week rows wrap one word per line at about 816 px; an empty course shows "hidden" for 0 questions | minor |
| W14 | Phone width | Admin tables and Materials scroll sideways inside their card; the action buttons and the module column are off screen | minor |
| W15 | Account menu, admin tables | Theme items read as actions while the check mark marks a state; "Disable"/"Enable" next to "Deactivate" in English | cosmetic |
| W16 | AI assistant | Sub-title still says the local model reads the material when the cloud model is chosen; an opened draft is far below the list without scrolling to it; the source radios have no accessible name | cosmetic (radios: minor) |
| W17 | Course content | Knowledge components and check items can only be retired, not edited (misconceptions can be) | decided: edit the wording, keep the identity (section 10, V18) |
| W18 | Module codes | "Thévenin" becomes `th_venin` in codes and file names | cosmetic |
| W19 | KC and quiz drafts (vLLM) | One duplicate KC name rejects the whole KC draft; a quiz draft with the 9B model gave "no usable question"; some 503s under load | to check with the vLLM |
| W20 | Chat answers | Formulas written with \( \) and \[ \] are shown as raw text ("(V_{th})") | minor |
| W21 | French interface | "cloud" and "Nuage" left in four strings | cosmetic |
| W22 | Privacy notice | The full notice opens once per browser, not per student: a new student on a shared computer only sees the short line | minor |
| W23 | French interface | "Explain it another way" and "Draft extra material" prepare a French request, but the course search and the privacy filter are English: no course material was found | major |
| W24 | AI quiz drafts | Questions and explanations say "according to the text" and "Passage 3 states" | minor |
| W25 | Quizzes | The editor shows no "Saved." after a save | cosmetic |
| W26 | Members (instructor) | "Reset password" resets at once, without the confirmation W11 added on the admin page | minor |
| W27 | Join page | Focusing the new-password field made the browser's password manager crash the browser during the automated test | to check by hand |

State on 2026-11-20 (second run, with the lab vLLM reachable and the student part done): W1 to W11, W13 to W16
and W18 to W26 are fixed in #129; W12 ("Start next term's course", with materials) is #133; W17 is decided (section 10, task V18);
W27 is to check by hand. W19 retested with the vLLM: quiz drafts and custom drafts work (3 of 3 questions usable,
a draft in under 30 s); the KC draft failed on accept as described and is fixed; no 503 was seen. Also checked:
the end-of-term survey (a student answers once, averages appear at three answers), the student pages at phone
width (no overflow), and a demo rebuild with the local model (new KCs for every module). Not run yet: web search
answers.

## 10. Decisions of 2026-11-20 and next steps (handover)

Taken by Z after the V17 runs and the review of PRs #129 to #136. No code for these tasks is written yet; the
next agent takes them in this order. Each is one task, one branch and one PR (AGENTS.md workflow).

| ID | Decision and task | Done when |
|---|---|---|
| V18 | **W17: edit the wording of KCs and check items, keep their identity.** An instructor can change the name and description of a knowledge component and the text, options and hint of a check item; the ID, the module and the learner records stay, so mastery estimates and class statistics keep counting the same item. The editor says that a change of meaning needs "Retire" and a new item. Backend: additive `PATCH` routes under `/api/v2/courses/{course_id}/...`, instructor of the course only, with access tests (another course's instructor, a student, logged out); no learner data in logs. Frontend: an edit form on Content like the one for misconceptions, with a "Saved." note, en and fr | PATCH routes and access tests; an edit keeps `p_mastery` and the quiz statistics; OpenAPI and generated types committed. **State:** PR #138 (the PATCH routes existed already; added the name and blank checks, the audit and the UI) |
| Z22b | **Privacy rule changes, low-risk part first.** Recognizers for: an AWS secret key after `secret_access_key`; `TOKEN` / `KEY` / `SECRET` assignments with any prefix, also inside dicts, and `'Bearer ...'`; the password in URL user info (`scheme://user:PASSWORD@host`); "the password for X is V" in prose; the whole 172.16.0.0/12 range, with and without a port; SCP-style `git@host:account/repo.git`. These only redact more. Re-run E6 (rule 4) and the Z22 course sets | E6 leak not worse on any set and over-redaction not worse on the main set; Z22 misses EH005, CH001, EH014, EH018, CH009, GH008, EH012, EH010 found. **State:** PR #139, all met |
| V19 | **A course type as one plug-in package, including routing** (below) | design note reviewed by Z, then the code. **State:** design merged (#140), agreed by Z; code in the V19 PR (plan items 1 to 6, tests as listed); training ECE heads is left for a later PR with a before/after report |
| Z22c | **After the video: an allow-list for course terms that look like names** (Smith chart, Hardy-Weinberg, Michaelis-Menten, Mendel, Krebs, Kant, Rawls, Django; "C" as a language). Risky: a student can be called Smith or Mendel, so only fixed phrases may pass, never a bare surname. Also a name after a role word ("my TA", "my partner"), and whether `life_science` and `general` get the lab address and repository recognizers | design agreed by Z before code; E6 and Z22 re-run |
| — | French screenshots to Lavin: sent by Z (25 files in `notes/fr-screens-2026-11-20/`, outside the repository) | done |
| — | S14: accepted with the small losses listed in section 6 | done |
| — | W27: Z checks by hand that a person can join from Edge (the new-password field) | checked |
| — | T16: the original report was not reproduced; Z gives the steps if it comes back | — |
| — | Still to measure: web search answers in the browser (V17), one full ask through the app (Z23), a fresh medical held-out set (Z22) | reports |

### Decisions of 2026-11-21

| ID | Decision and task | Done when |
|---|---|---|
| V20 | **Course announcements**, approved by Z. Instructors of a course write short plain text notices (title up to 200 characters, text up to 4000), pin, edit and delete them; every member reads them, pinned first, then newest first; students see the latest on the course home. Title and text pass the same privacy scan as an uploaded material (422 with the finding types); create, update and delete are audited with IDs and field names only. New table `announcement` (migration 0018), additive `/api/v2/courses/{course_id}/announcements` routes with access tests. Not in scope: e-mail notifications, unread markers, scheduled publishing | endpoints, access tests and the two views (en and fr) merged; OpenAPI and generated types committed. **State:** PR open |
| V21 | **Quiz options that differ only in case are different answers** (found while building the demo database). A quiz question refused genetics options such as "AA", "Aa", "aa" or "genotype A/A" and "genotype A/a" with "options must differ" (422), because options were compared without case. Options now count as the same only when they are equal after trimming and collapsing runs of spaces, case-sensitive; the same rule applies to the options of AI-drafted check items. The frontend and the check item editor have no such check | "AA", "Aa", "aa" and "A/A", "A/a" accepted; "Yes" and " Yes ", "a  b" and "a b" still refused. **State:** PR #142 |
| V22 | **Fixes from the browser test of 2026-11-21** (report `var/browser-test-2026-11-21/report.md`, local). Student pages B2, B7, B8, B19, B22 to B24 (#145); instructor pages B9 to B18, B25 (#146); logistics answers B1 and the cloud failure reason B3 (`fix/v22-logistics-answers`: single digits are words of the index, a logistics question keeps its retrieved passages when the relevance model accepts none, matching announcements reach the tutor as course-level passages); B5 and B6 (`fix/v22-asked-topics-history`): the KC codes of consenting students' questions are kept in `request_log.kc_ids` for "most asked topics" (the knowledge model does not read them), stored tutor turns keep their sources and model, an answer cut off at `max_tokens` says so, and the local model's `max_tokens` is 2048 (was 1024, which cut long answers with tables). B4 was the demo start script (web search key not passed). Demo data B20, B21 (2004 course titles, repeated first names) stays as it is | PRs merged; the demo rebuilt or its new columns filled |
| V23 | **Individual view by the student's choice** (mode B made usable), agreed in principle by Z on 2026-11-21: switched on by the administrator, chosen per course by the instructor; nothing is shared until the student agrees, and stopping is always possible; the instructor cannot tell who refused; class numbers and individual views use disjoint data: an event recorded while a student shared appears only in their individual view, every other event only in class numbers (differencing, option B chosen by Z on 2026-11-22 after six review rounds; the reasoning is in the design note). Design: [design/individual-view.md](design/individual-view.md). **Needs Prof. Abbas's agreement before any course with real students uses it** (his decision of 2026-11-17 stands: statistics only) | design reviewed by Z; code with the tests of the design note, switch still off by default |
| — | **Re-audit the GPU choice and `llm.local.max_tokens` together** (Z, 2026-11-21). 2048 tokens make long answers about twice as long to write and hold a vLLM slot that long, so the Z23 numbers (about 8 answers at once, about 40 per minute in a burst, measured with short answers) no longer hold for long answers. Measure answer lengths and time per answer at 2048 on the lab GPU, then choose the GPU (V13, `docs/GPU_COST.md`) and `max_concurrent` with them | measured and written into OPERATIONS.md section 10 and GPU_COST.md |
| — | **Retest of 2026-11-21 (after #145 to #148)**: B13 (no "Saved." on the quiz editor: the list gives the time in the database's zone, -05:00 on the demo server, the save in UTC), N2 (a question about the chosen module, such as the suggested "Summarize the key ideas of this module", got no course material because the relevance model accepted no passage), N3 (an announcement sharing one word with the question was added; the source line repeated the title) and N5 ("1 passages") are fixed (#149). N6, decided by Z: the notes under an answer (for example "parts of this answer may go beyond the course material") are stored with the answer and shown, translated, in a reopened conversation (#150). V1 follow-up from a review: the statistics-only switch no longer wipes acknowledgements when other settings are saved, invalidates them while individual views are off, and lets old history entries with mode B be restored (#151) | done |

### Model behaviour seen in the browser tests of 2026-11-21 (not code faults; to evaluate)

These come from the models, not from a bug in the pipeline. Each needs an evaluation on fictional or open-pack questions before a change of prompts, models or settings; record the result in `eval/` and here.

| ID | What was seen | Possible next step |
|---|---|---|
| M1 | **Invented details in examples.** The answer to "When is problem set 4 due?" was right (Lecture 22, from the announcement) but its example added dates that are in no source ("Lecture 21 is on November 10th"). The local 9B model fills examples with plausible facts. | A rule in the answer prompt that examples must not add dates, numbers or names absent from the passages; measure on the logistics questions of the S11 sets with the grounding checker. |
| M2 | **General knowledge when no material reached the model.** Before N2, "Summarize the key ideas of this module" was answered from general knowledge with "Since no specific course material was provided…". The fallback now passes material, but the model still answers from memory whenever passages are thin. | Count such answers in the answer-quality evaluation (`eval/course-rag-packs/answer_quality.py`) and compare the local and cloud models. |
| M3 | **The source named wrongly.** A web search answer said "According to the course material" although its only source was python.org. | Label web passages as web sources in the prompt and check the wording in the T13 web search evaluation. |
| M4 | **Web search is slow.** The OpenAI web search step took about 30 s (`websearch.provider: openai`); the whole answer took about 32 s. | Time it in T13; compare SearXNG and the API provider; consider a shorter timeout with the "course material only" fallback. |
| M5 | **A cloud failure that left no reason** (first browser test, B3): one DeepSeek call failed and the local model answered; the key, model name and balance were fine. The log now gives the reason (#147). Likely causes: `deepseek-flash` spends its hidden reasoning against `llm.cloud.max_tokens` (2000), or the 30 s `timeout_s`. | Read the new log line when it happens again; if it is the token limit or the timeout, raise `llm.cloud.max_tokens` or `timeout_s` (a model setting: Z decides). |
| M6 | **Long answers and `max_tokens`.** Answers with tables were cut at 1024 tokens; the local limit is now 2048 and a cut-off answer says so (#148). | Part of the GPU and `max_tokens` re-audit above: how often answers reach 2048, and the time they take. |
| M7 | **Unhelpful answers in the demo history.** A stored demo answer said "I can't determine Quiz 3's scope without your course material" (a logistics question before #147). | Rebuild the demo questions after the fixes, or remove such turns from the demo data. |
| M8 | **Local AI drafts fail at the 2048-token limit** (browser test of 2026-11-22, demo, CS50x, Week 5, local model). Two custom drafts, "three worked examples about linked lists, each with a practice exercise" and a shorter "one worked example about inserting a node at the start of a linked list with one practice question", both failed after about 60 s with "La rédaction a échoué. DraftError: The model did not produce a valid draft." The worker log shows `local answer cut off at max_tokens=2048` before each failure (jobs 22 and 23): a draft is one JSON object (`title`, `body`, `citations`), so an answer cut off at the limit is invalid JSON and the whole draft is lost. Not yet explained: the same short request with the first 8 Week 5 passages (3,100 characters), sent straight to the lab vLLM with the same prompt and schema, finished normally in 214 tokens; the job sends other passages (the draft's own retrieval and budget) or more of them, so the next step is to log the job's passage count, prompt tokens and completion length (no text). Two more things seen: the page shows the internal class name ("DraftError: …"), and with thin material the local model wrote a draft that only says the material has no example instead of writing one. | **Cause found and fixed** (M8 PR, report `eval/load-test/M8_DRAFT_LOOPS.md`): the drafts were not long; asked for one JSON object the local model looped inside it (endless spaces, or the body counting passage numbers) in 17 of 24 runs of the three demo drafts. Local tier 1 drafts now answer in Markdown (title line, draft, `Citations:` line): 0 of 48 runs cut off, all valid; cloud drafts keep JSON; each draft logs counts only. No model setting changed. Tier 2 and quiz drafts (still JSON) go into the research below |
| — | **Web pages refused as student data** (browser test of 2026-11-22, B-WEB, Z25b): https://en.wikipedia.org/wiki/Binary_search_algorithm as a draft source was refused as STUDENT_ID: the reference list's S2CID, arXiv, hdl and ProQuest numbers look like student numbers (5 of 7 Wikipedia pages sampled). The student number recognizer now skips a number right after such a label; E6 identical. Left: "150 104526" (journal volume and article) matches the SIN pattern on the Fourier transform page, where "sin" is the context word | fixed in the Z25b PR |

### Research: what the 2048-token limit changes (to do, after the video)

The local model's `max_tokens` went from 1024 to 2048 on 2026-11-21 (#148) because answers with tables were cut. A limit applies to every local call: answers, AI drafts (tier 1 and 2), quiz drafts, KC drafts, the understand step and the closed loop. Questions to answer, with numbers, before choosing the GPU and the limits (V13, Z23):

1. **How long are the outputs?** For each kind of call, the distribution of completion tokens on the open packs (median, p95, share that reaches the limit). Answers: the S11 and paraphrase question sets; drafts: five per kind and per pack (V16 set). Log only token counts and finish reasons, never text.
2. **Why do drafts reach the limit?** For the failing drafts (M8): passages, prompt tokens and the end of the output (repetition, a long `body`, or a schema the model cannot close). Compare 1024, 2048 and 4096, and a draft-specific limit (`max_tokens` per call kind instead of one value).
3. **What does a cut-off cost?** A cut answer now carries a note (#148); a cut draft is lost. Decide per kind: a larger limit, a retry asking for a shorter text, or a streamed draft that keeps what was written.
4. **What does the GPU pay?** Time per answer and per draft at each limit with 1, 8 and 16 at the same time (`eval/load-test/capacity.py` with long outputs), the slots a long draft holds, and what that means for `max_concurrent` and for the class sizes of Z23.
5. **The cloud side.** `deepseek-flash` counts its hidden reasoning against `llm.cloud.max_tokens` (2000); check whether this caused M5 and whether drafts with the cloud model reach it.

Output: a short report in `eval/load-test/` and the chosen limits in `config.yaml` (Z decides model settings), then V13 (`docs/GPU_COST.md`).

**State (2026-11-22):** measured, report `eval/load-test/TOKEN_LIMIT_RESEARCH.md` (harness `eval/load-test/output_lengths.py`). Plain answers: median 300, p95 868, max 1,156 completion tokens, none cut (a 1024 limit would cut 2 of 84). Answers asked for detail and a table: median 1,065, p95 1,950, 1 of 64 cut at 2048 (a long table: it ended at 1,936 with 4096). Tier 2 drafts (limit 4096) max 1,545, quiz drafts (2048) max 1,801 for 12 questions, understand (200) max 48: none cut, no loop outside the tier 1 JSON drafts of M8. Slot time on the lab GPU: about 44 tokens/s per call, total throughput flat at about 270 to 300 tokens/s from 8 at once; a 2048-token call takes 47 s alone, 53 s at 8, up to 127 s at 16, so it can pass `llm.local.timeout_s` (60 s) under load. Cloud (fictional prompts): `deepseek-flash` reasoning 49 to 223 tokens, nothing cut at 2000; V16 cloud drafts used up to 78 % of 2000 (one text) and 89 % of 4096 (structure). Options A to G (keep 2048, limits per call kind, a retry asking for a shorter answer, a larger `timeout_s`, plan capacity on the mean answer) are for Z; no setting changed.

### What a course type selects today, and V19

A course has one course type (`courses.course_type`). Today the type selects:

- the **privacy profile** `backend/app/privacy/profiles/<type>.yaml` (`extends: base`): the PII recognizers
  (`@pii_recognizers.register`), the health-detail policy, the checkers (`@checkers.register`), the medical
  disclaimer, the consent note and the subject prompt (`app/prompts/subjects/<prompt>.md`). A new type is one
  YAML file plus any new recognizer or checker module; unknown names stop the app when the profile loads;
- the **web search** sites and engines (`websearch.allowlist`, `websearch.searxng_engines` in `config.yaml`).

The type does **not** select the **router**. There is one router for the whole deployment (`routing.impl`,
`@routers.register`) with one set of trained heads (`data/routing/models`, trained on medical questions, T15),
and `RouteInput` has no course type. Retrieval and the evidence step are per course; the routing score is not.

V19 makes a course type one package that another team can add without changing the core:

1. `RouteInput` gets an optional `course_type` (additive); the pipeline fills it from the course settings.
2. Routing heads per type in `data/routing/models/<type>/` when that folder exists, the current models
   otherwise, so existing types do not change; optionally `routing.by_course_type: {<type>: <impl>}` to use
   another registered router for one type.
3. `routing/train.py` takes a question set and a type and writes that folder; the routing evaluation reports per
   type.
4. `docs/design/extension-points.md` gets a "new course type" checklist: profile YAML, recognizers, checkers,
   subject prompt, web search sites, routing heads and their question set, a Z22-style held-out privacy set
   and an E6 run, and the tests.

Why: the router is the only per-question decision that ignores the subject, so heads trained on medical
questions also decide for ECE and CS courses (the routing test of 2026-11-20 measured ECE only). A separate
router class per type is rarely needed; trained heads per type behind the shared router are the useful part.
Rules 2 and 4 stay: a type's router cannot send original text to the cloud (the cloud gate runs after routing),
and a new privacy profile needs its own held-out set and an E6 run.
