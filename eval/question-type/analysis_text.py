ANALYSIS = """## What the numbers say

- The head separates course organisation from subject questions well on courses it has never seen: most
  errors are questions at the border. The five held-out courses include a subject (migraine, medical
  seed questions) that has no logistics question at all, so every error there is a false alarm.
- Most false alarms are the document-grounded seed questions ("find the criteria in the course handout",
  "walk through the instructor's worked example"). They name the course material, which is also what a
  logistics question does, but they ask about the subject, so they are labelled concept. A false alarm costs
  little: the question is still answered, it only skips personalization and prefers course-level files.
- A missed logistics question ("is the midterm in person?") is retrieved like any concept question, which is
  today's behaviour.
- The labels of the S11 and T4 sets are used as they are (`type: logistics` against the other types); one
  S11 question about what to review for the final (`alg-18`) is labelled concept there and is a border case.

## Limits

- The logistics examples are few (175) and the packs repeat the same kinds of question (grading, textbook,
  late policy, due dates), so the numbers show how well the head knows those kinds, not every way a student
  can ask. The supplement of six subjects was written for this task, with hard negatives (questions about
  deadlines, grading or schedules *as a subject*), but it is still one author's wording.
- Questions are English only. The head sees the sanitized current question; it never stores it.
- The threshold is 0.5. A false logistics answer skips personalization, a false concept answer only loses the
  course-level preference, so a higher threshold is the safer direction if the first proves too eager.
- Retrain with `python -m app.routing.question_type_train` (rewrite the data with `--rebuild-data`); the
  routing models in `data/routing/models/` are not touched.

## Effect on retrieval (S11 packs, question types from the S11 labels)

`eval/course-rag-packs/run.py`, k=4, all eight packs; before = every question retrieved as a concept question
and calendar tables chunked as plain lines; after = logistics questions with `question_kind="logistics"`
(course-level files unweighted, boost 1.5) and one passage per table row.

| Questions | Mode | Before hit@1 / hit@4 | After hit@1 / hit@4 |
|---|---|---|---|
| logistics (48) | course-wide | 0.69 / 0.85 | 0.75 / 0.90 |
| logistics (48) | asked from inside a module | 0.71 / 0.88 | 0.75 / 0.90 |
| calendar questions (10) | course-wide | 0.20 / 0.60 | 0.40 / 0.80 |
| concept (123) | module scoped | 0.984 / 1.00 | 0.976 / 1.00 |
| concept (123) | course-wide | 0.683 / 0.943 | 0.675 / 0.943 |
| application (41) | scoped / course-wide | 1.00 / 1.00 and 0.756 / 0.902 | unchanged |
| all (212) | scoped | 0.920 / 0.967 | 0.929 / 0.976 |
| all (212) | course-wide | 0.698 / 0.915 | 0.708 / 0.925 |

The four calendar questions that never reached `calendar.md` before: `gen-26` rank 1, `bio7016-26` rank 1,
`hst151-26` rank 3, `circ-28` still not found (syllabus and assignment text about homework outranks the calendar row).
The concept loss is one question (`gen-20`, "in the first lecture") whose answer moved from rank 1 to 2
because a calendar row about the first lecture now matches it; hit@4 is unchanged. Boosts of 1.5, 2.0 and 3.0
give the same result; 1.0 (no boost, only the unweighting and the table rows) gives logistics 0.71 / 0.90.
"""
