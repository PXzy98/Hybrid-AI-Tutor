# MVP demo (about 5 minutes)

This script shows the four ideas of the system:
1. The tutor adapts to what each student knows.
2. Check questions update that knowledge.
3. Questions are routed between a local and a cloud model.
4. Private data never leaves the local network.

Everything runs locally with Docker; the model runs on the GPU server.

## Before the demo (once, about 10 minutes)

1. Create `.env` from `.env.example`. For the demo, set:

   ```dotenv
   OLLAMA_URL=http://192.168.2.25:11434
   INSTRUCTOR_USERNAME=prof
   INSTRUCTOR_INITIAL_PASSWORD=<choose one>
   CONTENT__SERVE_UNREVIEWED=true      # the HBP content is still a draft (docs/review/)
   # optional cloud model, to show real cloud answers:
   # CLOUD_API_KEY=...   CLOUD_MODEL=...
   ```

2. Start the app and check that it is healthy:

   ```powershell
   docker compose up --build -d          # first build: several minutes (spaCy model download)
   curl http://localhost:8080/api/v1/health
   ```

   For a quicker build, add `SPACY_MODEL=en_core_web_sm` to `.env` or to the command. The image and the privacy filter always use the same model.

3. Open http://localhost:8080 and log in as `prof` with the initial password. The app asks you to choose a new password; do that.

4. Seed the three demo students (it runs through the public API and can be re-run at any time):

   ```powershell
   $env:DEMO_INSTRUCTOR_PASSWORD="<the new instructor password>"
   .venv\Scripts\python scripts\demo_seed.py --base-url http://localhost:8080
   ```

   Expected output:

   ```
   demo.novice        bands: basic basic basic basic basic basic   (not assessed: HBP.2, HBP.3, HBP.4, HBP.5, HBP.6)
   demo.intermediate  bands: intermediate intermediate intermediate intermediate intermediate intermediate
   demo.advanced      bands: advanced advanced advanced advanced advanced advanced
   ```

   The demo students' password is `demo-student-2026` (or `DEMO_STUDENT_PASSWORD`). These are demo accounts only.

5. Ask one question once before the audience arrives, so the model is loaded on the GPU. The first answer after a pause can take 20–30 s.

## The demo

| Time | Do | Say |
|---|---|---|
| 0:00 | Log in as **demo.novice**. Point at "What I know": everything is *basic*. | "The tutor keeps a learning profile per knowledge component. This student missed the first diagnostic question, so the parts that build on it were not even assessed." |
| 0:45 | **Chat**, ask: *Why does eating too much salt raise blood pressure?* | "Badge: *basic*. The answer starts with an everyday example and stays short, because that is what this student chose in onboarding. Below it is a check question for the weakest part." |
| 1:30 | Answer the check question **wrongly**, then **correctly** on the next one. | "The answer is graded by the key, not by the model, so it is reliable evidence. The band of that part changes immediately." Show it in "What I know". |
| 2:15 | Log out and log in as **demo.advanced**. Ask the same question. | "Same question, different student: *advanced*, the idea first, precise terms (osmosis, vascular resistance). The check question is an advanced one." |
| 3:00 | Ask: *My name is Alice Tremblay, student 300418277, and I have asthma. Why does my inhaler make me shaky?* | "Before any model sees this, the privacy filter replaces the name, the student number and the personal health detail. A personal health detail is never sent to the cloud, so this stays local. The safety check makes sure there is no diagnosis or dose in the answer, and that it refers to a clinician." |
| 3:45 | Show what was stored (command below). | "The database only has the placeholders. The name, the number and 'I have asthma' are nowhere in it." |
| 4:15 | Local vs cloud routing (below). | "The router score decides. The cloud only ever gets the sanitized question plus three coarse labels such as *basic*: never the student ID, the profile or the misconceptions." |
| 4:45 | Wrap up | "The learner model, the privacy filter and the checks are local. The routing score and RAG are teammates' components behind fixed interfaces." |

### Show what was stored

```powershell
docker compose exec api python -c "import sqlite3; c=sqlite3.connect('/app/data/app.db'); [print(r) for r in c.execute('select target, sanitized_question from request_log order by id desc limit 3')]"
```

### Show local vs cloud routing

The routing score is a stub until Tongkai's router is plugged in. Its fixed score can be raised for the demo:

```powershell
# in .env:  ROUTING__STUB_SCORE=1.0      (back to 0.0 afterwards)
docker compose up -d api
```

- Without a cloud key, the answer shows "The cloud model was unavailable, so the local model answered." This demonstrates the fallback.
- With `CLOUD_API_KEY` and `CLOUD_MODEL` set, a question **without** personal health details (for example the salt question with a name in it) is answered by the cloud model, and the name in the answer comes back filled in for the student.
- A question **with** a personal health detail stays local regardless of the score (`cloud_safe = false`).

## Instructor view

Log in as the instructor; `/admin` has five tabs:

- **Students**: add a student (the temporary password is shown once, with a copy button), reset a password, deactivate, or delete with a typed confirmation.
- **Class summary**: mastery bands per knowledge component and the most common misconceptions. Any group smaller than 5 is hidden. With only the three demo students, the whole summary is hidden, which is worth showing as the privacy rule at work.
- **Settings**: the cloud threshold, answer checks, knowledge model, weak evidence and level thresholds. Changes apply to the next question without a restart. To show it: with `ROUTING__STUB_SCORE=0.5`, a threshold of 0.6 keeps questions local, and 0.4 sends them to the cloud.
- **Logs**: sanitized questions, the route, latency p50/p95 and the share routed to the cloud. No student IDs.
- **Content**: review status per topic, and course-material uploads for the RAG pipeline.

## Reset after the demo

```powershell
.venv\Scripts\python scripts\demo_seed.py --base-url http://localhost:8080   # re-seeds the three students
docker compose down        # keeps the data volume; add -v to delete all accounts and data
```
