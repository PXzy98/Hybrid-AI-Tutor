# MVP demo (about 6 minutes)

This script shows the five ideas of the system:
1. The tutor adapts to what each student knows.
2. Check questions update that knowledge.
3. Questions are routed between a local and a cloud model (semantic router).
4. Answers cite course material (medical RAG).
5. Private data never leaves the local network; personal health questions stay local.

Updated 19 Oct 2026 for the integrated system (semantic routing, medical RAG, cloud gate, survey). The run below
was tested in development mode with the local GPU server and DeepSeek as the cloud model.

## Build the multi-course demo (one command)

`scripts/build_demo.py` creates the demo courses from the open course packs (`data/demo_courses/README.md`)
through API v2 only; it never writes to the database. Start the app (see below), make sure the instructor or
admin account has chosen its own password (log in once in the browser), then:

```powershell
$env:DEMO_INSTRUCTOR_USERNAME="prof"
$env:DEMO_INSTRUCTOR_PASSWORD="<the instructor password>"
.venv\Scripts\python scripts\build_demo.py --base-url http://localhost:8000
# optional: --packs harvard_cs50x mit_6_006_algorithms   --students 5   --sample-activity
```

Default packs, one per area: `mit_hst151_pharmacology`, `mit_7_016_intro_biology`, `mit_6_002_circuits`,
`harvard_cs50x`. The script:

1. unpacks the packs when needed (`scripts/fetch_open_courses.py unpack`); `instructor_only/` is never uploaded;
2. creates one course per pack with the pack's course type (skipped when the course code exists, so the command
   can run twice), one module per manifest module, uploads the module files and the course-level documents,
   and waits for the index rebuild. Files the privacy scan refuses (422) are listed and skipped;
3. creates fictional students "Demo Student 1..N" (default 3), lists them in each course and lets them join
   with the course's invitation code. The generated logins are written to `var/demo_accounts.json`
   (git-ignored, never printed). The addresses use `DEMO_EMAIL_DOMAIN` (default `uottawa.ca`, which must be in
   `limits.accounts.allowed_email_domains` of the server); at most 20 joins per hour are allowed per client
   address, so `--students` times the number of packs must stay below that;
4. sets visibility mode B in every demo course;
5. with `--sample-activity`: each student acknowledges mode B, answers the check questions the modules have
   (the packs have none yet, so this is usually nothing) and asks two questions, which needs a working model
   connection; failures are reported, not fatal.

It ends with a table: course, modules, uploaded, refused, index version. With the Docker Compose stack, run
the script **on the host** from a checkout of the repository (the image holds neither the script nor the
packs), pointing it at the stack's proxy: `--base-url http://localhost:8080` for the local stack,
`https://<domain>` in production; it only uses the HTTP API.

The six-minute script below is the older single-course (high blood pressure) demo.

## Before the demo (once, about 15 minutes)

1. Create `.env` from `.env.example`. For the demo, set:

   ```dotenv
   OLLAMA_URL=http://192.168.2.25:11434
   INSTRUCTOR_USERNAME=prof
   INSTRUCTOR_INITIAL_PASSWORD=<choose one>
   CONTENT__SERVE_UNREVIEWED=true      # the HBP content is still a draft (docs/review/)
   # cloud model (optional; without it the local model answers and says so):
   CLOUD_BASE_URL=https://api.deepseek.com
   CLOUD_API_KEY=<key>
   CLOUD_MODEL=deepseek-flash
   ```

2. Install the local models once (see the README): `en_core_web_lg` for the privacy filter, and the routing and
   evidence models:

   ```powershell
   .venv\Scripts\python -m spacy download en_core_web_lg
   cd backend; ..\.venv\Scripts\python -m app.routing.prepare
   ```

3. Start the app in development mode (two terminals) and check that it is healthy:

   ```powershell
   cd backend; ..\.venv\Scripts\python -m uvicorn app.main:app      # http://localhost:8000
   cd frontend; npm install; npm run dev                            # http://localhost:5173
   curl http://localhost:8000/api/v1/health   # "cloud_enabled": true when a key is set, "routing_impl": "semantic"
   ```

   Docker (`docker compose up --build -d`, http://localhost:8080) also works; the image contains the spaCy,
   routing and evidence models, so steps 2 and 3 are not needed. Set `CONTENT__SERVE_UNREVIEWED=true` in `.env`.

4. Open the web app and log in as `prof` with the initial password. The app asks you to choose a new password.

5. Seed the three demo students (through the public API; can be re-run at any time):

   ```powershell
   $env:DEMO_INSTRUCTOR_PASSWORD="<the new instructor password>"
   .venv\Scripts\python scripts\demo_seed.py --base-url http://localhost:8000
   # Docker: docker compose exec -e DEMO_INSTRUCTOR_PASSWORD=<...> api python /app/scripts/demo_seed.py --base-url http://127.0.0.1:8000
   ```

   Expected output:

   ```
   demo.novice        bands: basic basic basic basic basic basic   (not assessed: HBP.2, HBP.3, HBP.4, HBP.5, HBP.6)
   demo.intermediate  bands: intermediate intermediate intermediate intermediate intermediate intermediate
   demo.advanced      bands: advanced advanced advanced advanced advanced advanced
   ```

   The demo students' password is `demo-student-2026` (or `DEMO_STUDENT_PASSWORD`). These are demo accounts only.

6. Ask one question once before the audience arrives, so the local model is loaded on the GPU. The first answer
   after a pause can take 20–30 s; then local answers take about 5–15 s and cloud answers 8–12 s.

## The demo

| Time | Do | Say |
|---|---|---|
| 0:00 | Log in as **demo.novice**. Point at "My progress": everything is *basic*. | "The tutor keeps a learning profile per knowledge component. This student missed the first diagnostic question, so the parts that build on it were not even assessed." |
| 0:45 | **Chat** (topic High Blood Pressure), ask: *What do the two numbers in a blood pressure reading mean?* | "The progress panel shows the router at work. Badge: *basic*, an everyday example first. Below the answer: the MedlinePlus source it used, then a check question for the weakest part." |
| 1:30 | Answer the check question **wrongly**, then **correctly** on the next one. | "The answer is graded by the key, not by the model, so it is reliable evidence. The band of that part changes immediately." Show it in "My progress". |
| 2:15 | Log out and log in as **demo.advanced**. Ask the same question. | "Same question, different student: *advanced*, the idea first, precise terms. The check question is an advanced one." |
| 3:00 | Ask: *Compare the long-term cardiovascular outcomes of SGLT2 inhibitors versus GLP-1 receptor agonists in adults with chronic kidney disease.* (topic Type 2 Diabetes) | "This needs more than the local model and the course material, so the router chooses the cloud. The cloud model only gets the sanitized question, the topic, course passages and three coarse labels." |
| 3:45 | Ask the same with identity: *I'm Priya Raman, student 300418277, email priya.raman@uottawa.ca. Compare …* | "The cloud saw only `<PERSON_1>`, `<STUDENT_ID_1>`, `<EMAIL_ADDRESS_1>` (show the stored request below); the student sees the real values filled back in." |
| 4:30 | Ask (topic Asthma): *I was diagnosed with asthma last week, can I still play soccer?* | "A personal health detail. The cloud never sees it as written: the local model rewrites it as *Can a person newly diagnosed with asthma still play soccer?*, the rewrite is checked again, and only then sent. The student is told: *For privacy, the cloud model received a general version of your question…* If a rewrite fails its checks, the question stays local with *A privacy check kept this question on the local model.* The safety check still refers to a clinician." |
| 5:15 | Open the **End-of-term survey** tab (instructor: set the window; student: five 1–5 ratings, answered once). | "Evaluation is only an end-of-term survey: five anonymous ratings, no student ID, no free text. The instructor sees averages once enough students have answered." |
| 5:40 | Wrap up | "The privacy filter, the learner model, the router's models and the evidence check run locally. Only a sanitized, allow-listed request can reach the cloud, and the E4 audit checks every one." |

### Show what was stored

The request log keeps only sanitized text:

```powershell
docker compose exec -T db psql -U tutor -d tutor -c "select target, sanitized_question from request_log order by id desc limit 3"
```

### If something goes wrong

- No cloud key, or the cloud fails: the local model answers with *No cloud model is connected…* or *The cloud
  model was unavailable…* plus *This question may be beyond what the local model does well…*. This is the
  intended fallback; say so.
- Answers without sources and the note *…found by search but not checked for relevance*: the evidence models are
  missing; run `python -m app.routing.prepare` and restart.
- Some questions have no source at all (for example the DASH diet): the course material does not cover them; the
  answer says that it goes beyond the course material.

## Instructor view

Log in as the instructor and open a course; the course page has these tabs:

- **Class overview**: mastery bands per knowledge component and the most common misconceptions. Any group
  smaller than the minimum group size is hidden, which shows the privacy rule.
- **Students**: every student with the sharing state. A student's progress and learning plan can be opened only
  when the student agreed (visibility mode B) and did not opt out; each view is audited.
- **Course content**: modules, knowledge components and check items.
- **Members**: the invitation code, CSV import of a class list, co-instructors, temporary passwords.
- **Materials**: upload (privacy-scanned; a refused file names the finding types), delete, index rebuild state.
- **Settings**: visibility mode, local only, routing preference, whether students see the routing steps.
- **End of term**: export, then delete the course's student data (typed confirmation).
- **Quizzes** and **End-of-term survey**: quizzes (with AI drafts that must be reviewed before publishing) and
  the survey window with averages.

Students can delete their own learning data in a course from the **My progress** tab.

## Reset after the demo

```powershell
.venv\Scripts\python scripts\demo_seed.py --base-url http://localhost:8000   # re-seeds the three students
```
