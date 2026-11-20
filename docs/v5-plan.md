# v5 plan (draft of 2026-11-17)

Source: the weekly meeting of 2026-11-17 with Prof. Abbas (client) and Prof. Ismaeel (advisor), plus the open
items of v4 ([TODO.md](../TODO.md), open PRs, the UI checks). Where the two professors disagree, Prof. Abbas's
view is taken; Prof. Ismaeel's ideas are added where they do not conflict.

Until this plan is merged into [v4-implementation-guide.md](v4-implementation-guide.md), the guide's rules
(section 2) still apply unchanged. Task IDs: `V1`... are new in v5; v4 IDs (`S14`, `Z26`, ...) are kept.

## 0. Status on 2026-11-20

| Task | State |
|---|---|
| Open v4 PRs #102 to #107 | merged |
| V1 statistics-only instructor view | merged (#109) |
| V2 class statistics | merged (#115); small groups, differences and single scores hidden (#126) |
| V3 privacy notice | merged (#114); screenshots to Lavin not sent yet |
| Z26 instructor guidelines reach the model | merged (#110) |
| S15 demo learner content, S16 CS course type, Z25 pack scan | merged (#113, #111, #112); S16 check with the vLLM open |
| Backend French texts | merged (#124) |
| V4, V5, V6 free request, chosen sources, a file for one draft | merged (#119, review fixes in #120) |
| V7 web pages as material and as a draft source | merged (#120); Wikipedia refuses the fetcher (V17 finding W1) |
| V8 closed loop | merged (#123) |
| V9 accounts from term to term | merged (#118, review fixes #125) |
| V15 a student's own answer instruction | merged (#121) |
| V16 cloud drafts for public material | merged (#122); the before/after comparison of five drafts per kind needs the vLLM |
| V11 to V14, T10 notes | merged (#116): `DOMAIN_NAMES.md`, `DEMO_VLLM.md`, `GPU_COST.md`, `design/extension-points.md`, `DEMO_SCRIPT.md` |
| Z27 security review | merged (#117); H1, M1, L4 fixed; M2 to M4 fixed (#130); L1 to L3 fixed (#132) |
| V17 browser test | admin and instructor parts done on the integration build (fictional data); student part and every flow that needs the local model still to run; findings in section 9 |
| End of term to next term | done once in V17 (export, new course from the YAML export); gaps in W12 |
| Settings bug from the meeting | Z to describe it; an empty "Enabled course types" field that switched course creation off was fixed in #127 |
| Routing test, Z23 capacity, V16 comparison, answer quality on ECE and CS | open: need the lab vLLM, which was unreachable on 2026-11-20 |
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
| V16 | **Draft quality on the 9B model** (Z called it "not good enough" in the meeting): better prompts and passages for the instructor AI; for public material the instructor may choose the cloud model after the cloud notice (guide 4.9) | S | five drafts per kind compared before and after |
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
| Z23 | vLLM capacity (tokens per second, 1 to 32 at a time), model limits set from it | Z | measured 2026-11-20: numbers and recommendation (`max_concurrent` 8, timeout 60) in OPERATIONS.md section 10; limits not yet changed in `config.yaml`; full-ask timing open |
| — | Alert receiver for monitoring (ask Prof. Abbas) | Z | set in `alertmanager.yml` |
| T10 | Video on the v5 UI; Design Day live demo script on the production site; "Brightspace plus" story (teaching, research, industry training; learners include trainees and research groups, a bridge between academia, research and industry); one demo step uploads an open-access paper and drafts research topics from it | T, all | video submitted 11/25 |
| — | Final report and Design Day material carry the same story and the value for future research | all | report 12/13 |
| T13 | Web search evaluation (G1-106); Tongkai shows web search at the next meeting | T | report |
| E4 | End-to-end privacy audit on v5 (after V1, V7, Z26) | Z | report |
| — | Answer quality on non-medical courses (ECE, CS packs) with the vLLM model | S, T | done 2026-11-20 for 6.002 and CS50x (10 questions each): `eval/course-rag-packs/results/answer_quality.md` |

## 6. Remaining v4 items (in order, when time allows)

- **Retrieval (S14)**: paraphrased and misspelled questions miss the syllabus ("When does the course end?");
  course-wide retrieval ranks homework and exams above lectures; "when is homework 4 due" (circ-28) is not
  found; retrieval is only lexical (add a semantic step).
- **Routing (T15, T17)**: routing heads trained on medical questions only; course-rule questions routed to the
  cloud skip retrieval.
- **Privacy tests (Z22)**: held-out ECE set, `life_science` and `general` sets, a fresh medical set, E6 scores.
- **T16 (chat)**: after opening a past conversation there is no way back to a new, empty conversation.
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
- Lavin's second review of the 30 revised check items.
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
| W17 | Course content | Knowledge components and check items can only be retired, not edited (misconceptions can be) | to decide |
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
and W18 to W26 are fixed in #129; W12 ("Start next term's course", with materials) is #133; W17 is to decide;
W27 is to check by hand. W19 retested with the vLLM: quiz drafts and custom drafts work (3 of 3 questions usable,
a draft in under 30 s); the KC draft failed on accept as described and is fixed; no 503 was seen. Also checked:
the end-of-term survey (a student answers once, averages appear at three answers), the student pages at phone
width (no overflow), and a demo rebuild with the local model (new KCs for every module). Not run yet: web search
answers.