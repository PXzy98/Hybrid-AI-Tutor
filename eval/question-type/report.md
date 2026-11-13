# Question type head: concept vs logistics (T5)

749 labelled questions (175 logistics) from the S11 course packs, the T4 ECE/CS questions, the medical seed questions (every third one) and a supplement of six more subjects (`data/question_type/`). The head is a logistic regression (C=4, balanced classes) on the local `all-MiniLM-L6-v2` embedding the router already computes; threshold 0.5. Every split is by course.

## Held-out courses

Trained on 556 questions, tested on 193 questions of 5 courses never seen in training: `mit_hst151_pharmacology`, `mit_6_006_algorithms`, `migraine`, `supp_economics`, `supp_nursing`.

Accuracy **0.933** (always answering concept: 0.736); logistics precision 0.83, recall 0.94.

| True \ predicted | concept | logistics |
|---|---|---|
| concept | 132 | 10 |
| logistics | 3 | 48 |

| Course | n | accuracy | logistics precision | logistics recall |
|---|---|---|---|---|
| mit_hst151_pharmacology | 30 | 1.00 | 1.00 | 1.00 |
| mit_6_006_algorithms | 66 | 0.94 | 0.79 | 0.92 |
| migraine | 33 | 0.82 | 0.00 | - |
| supp_economics | 32 | 1.00 | 1.00 | 1.00 |
| supp_nursing | 32 | 0.91 | 0.93 | 0.88 |

Held-out errors:

- concept (p(logistics) 0.62, `mit_6_006_algorithms`): how do I use depth first search to order tasks with dependencies?
- concept (p(logistics) 0.97, `mit_6_006_algorithms`): what should I review for the final, what topics does the review lecture list?
- concept (p(logistics) 0.62, `mit_6_006_algorithms`): Show how to reduce a scheduling problem with precedence constraints to a shortest path problem in a DAG, handle ties and resource limits, and explain which part makes the general problem NP-hard.
- logistics (p(logistics) 0.41, `mit_6_006_algorithms`): What happens if I get a C on problem set 0?
- concept (p(logistics) 0.55, `migraine`): For a classroom diary graph, distinguish the number of headache days from a rating of pain intensity.
- concept (p(logistics) 0.53, `migraine`): Find and cite the migraine classification criteria reproduced in the course handout.
- concept (p(logistics) 0.58, `migraine`): List the trigger examples actually included in the course material.
- concept (p(logistics) 0.65, `migraine`): Which participants were eligible for the uploaded migraine study?
- concept (p(logistics) 0.53, `migraine`): Walk through the instructor's worked example of interpreting a headache diary.
- concept (p(logistics) 0.81, `migraine`): For an abstract diary-sampling exercise, minimize x^2+4y^2 subject to x+y=B, x>=L and y>=0, where B>=L>=0. Derive the optimal allocation, all boundary regimes and sensitivity to L without clinical interpretation.
- logistics (p(logistics) 0.50, `supp_nursing`): What happens if I fail the dosage calculation test, can I retake it?
- logistics (p(logistics) 0.38, `supp_nursing`): Is the pharmacology midterm in person?
- concept (p(logistics) 0.75, `supp_nursing`): How is the Glasgow Coma Scale graded?

## Leave-one-course-out

Each course is predicted by a head trained on all the others, so every question is scored once on unseen course material. Accuracy **0.967** over 749 questions; logistics precision 0.90, recall 0.97.

| True \ predicted | concept | logistics |
|---|---|---|
| concept | 555 | 19 |
| logistics | 6 | 169 |

| Course | n | accuracy | logistics precision | logistics recall |
|---|---|---|---|---|
| asthma | 33 | 0.97 | 0.00 | - |
| harvard_cs50x | 70 | 0.96 | 0.81 | 1.00 |
| high_blood_pressure | 33 | 0.94 | 0.00 | - |
| migraine | 33 | 0.85 | 0.00 | - |
| mit_6_002_circuits | 71 | 0.99 | 0.93 | 1.00 |
| mit_6_006_algorithms | 66 | 0.94 | 0.79 | 0.92 |
| mit_7_016_intro_biology | 31 | 1.00 | 1.00 | 1.00 |
| mit_7_03_genetics | 29 | 1.00 | 1.00 | 1.00 |
| mit_hst035_pathology | 29 | 1.00 | 1.00 | 1.00 |
| mit_hst151_pharmacology | 30 | 1.00 | 1.00 | 1.00 |
| mit_res_6_007_signals | 66 | 0.98 | 1.00 | 0.92 |
| pneumonia | 33 | 0.97 | 0.00 | - |
| supp_chemistry | 32 | 0.97 | 1.00 | 0.94 |
| supp_economics | 32 | 1.00 | 1.00 | 1.00 |
| supp_history | 32 | 0.91 | 0.88 | 0.94 |
| supp_nursing | 32 | 0.94 | 0.94 | 0.94 |
| supp_software | 32 | 0.97 | 1.00 | 0.94 |
| supp_statistics | 32 | 1.00 | 1.00 | 1.00 |
| type2_diabetes | 33 | 1.00 | - | - |

## What the numbers say

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

