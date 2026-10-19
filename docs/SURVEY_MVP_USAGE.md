# MVP voluntary student feedback survey

This module is **not** the university ITP Metrics form or the optional full ILS
learning-style questionnaire. It is an additional short, optional prototype
evaluation form; the five medical topics share the same four questions.

## Student trial
1. Sign in with a student account and open **Chat**.
2. Select any of the five medical topics (High Blood Pressure, Type 2 Diabetes,
   Asthma, Migraine or Pneumonia).
3. Select **Try a sample question for this topic** to populate the question input.
4. Send a question. After the tutor successfully returns an answer, select
   **Rate this answer (optional)**.
5. Rate four dimensions 1–5: helpfulness, material relevance, clarity,
   and confidence in the cited sources; then **Submit feedback** or **Skip**.

The feedback survey does not run until the user opens it. Ratings are subjective
user perceptions and do **not** prove medical accuracy or grounding correctness.
The real generative chat requires a configured Ollama or cloud LLM;
survey functionality itself can be exercised using the offline integration tests.

## Instructor summary

Sign in as an instructor, open **Instructor dashboard → Feedback** and choose
**Refresh summary**. The page shows submission counts per topic. Mean scores
appear only after **at least 3 submissions** for that topic. There is no route
to retrieve per-respondent scores.

## Privacy / MVP limitations

The table `survey_response` contains only an auto-increment record ID, topic,
and four numeric ratings. No free text, submitted questions, generated answers,
student IDs, usernames, account IDs, session IDs or submission timestamps.
The POST schema rejects any extra input fields. Only students can submit and
only instructors can access the aggregate results.

These are **counts of submissions, not unique people**. Because the project
deliberately does not store identifiers, the MVP API cannot enforce one
submission per individual or prevent repeated submissions by the same account.
The user interface hides the survey after submitting/skipping within its
current mounted topic view, but that is not a server-side anti-spam guarantee.
This experimental survey is not an anonymous research study validated by an
ethics committee and should not be used with identifiable patient data.

## Verification (from project root)

```powershell
cd backend
..\.venv\Scripts\python.exe -m pytest -q tests/test_survey.py
..\.venv\Scripts\python.exe -m pytest -q
cd ..\frontend
npm run test -- --run
npm run build
```

HTTP API:
- `POST /api/v1/survey` (student cookie, required 1–5 values)
- `GET /api/v1/admin/survey-summary` (instructor cookie, aggregates only)
