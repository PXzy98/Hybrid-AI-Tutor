# E6 held-out sets: how they were made and labelled

The recognizers were developed against `cases.jsonl`, so the numbers on that set are optimistic (several rules
were added after looking at its misses). Two further sets measure how the filter generalizes:

| Set | File | Role | Written by | Labelled by |
|---|---|---|---|---|
| v1 | `holdout.jsonl` (raw: `holdout_raw.jsonl`) | **dev**: its misses were used to widen the rules | gemma4:e4b, seed 61 | hand |
| v2 | `holdout2.jsonl` (raw: `holdout2_raw.jsonl`) | **test**: written after the rules were frozen, never used for tuning | gemma4:e4b, seed 62 | hand |

`make_holdout.py` asks gemma4 (not qwen, which wrote the question bank) for 102 messages per set in 11
scenarios (own name, other names, student numbers, contact details, grades, own and family health, combinations,
general questions, eponyms, hypothetical patients), with no templates. The generator's own labels were not
usable: it tags every medical term as a health detail, also in general questions, and it mixes up IDs and phone
numbers. Its labels are kept in the raw files for reference only; every message was labelled again by hand
(the coding assistant, 2026-10-19; a team member should re-check the debatable ones below).

Conventions (same as `cases.jsonl`):

- PERSON: the name without its title ("Dr. Chen" → "Chen"); names of staff and doctors count too, only the
  allow-listed course staff are not PII.
- STUDENT_ID: the 9-digit number; GRADE: the result itself ("C+", "85%", "3.8"); a target ("I need an A") is not
  a grade.
- HEALTH_DETAIL: a condition, symptom, medicine, test result or reading **attributed** to the student or to
  someone they know. A medical term in a course question ("the pneumonia chapter", "if a patient has asthma") is
  not. `personal_health` is true when the message has at least one such detail; it decides "must stay local".
- Messages with no entity are the negative set (13 in v1, 9 in v2: the generator put personal details into most
  "general" messages).

Debatable labels (a different labeller could decide otherwise):

- v1: H065 "chronic fatigue related to severe diabetes? My friend Amir needs help with his diet" — labelled not
  personal health (the condition is not attributed to Amir explicitly).
- v2: T005 "I'm struggling with Pneumonia symptoms" (own illness or the course topic) — labelled personal;
  T011 "has Michael Rodriguez been diagnosed with severe asthma?" — personal (a named person's possible
  diagnosis); T017 "his uncle is having problems" (in a blood-pressure context) — personal; T072 "Can I talk
  about the hypertension again?" — not personal; T075 "If a student like Aiya (300456123) is experiencing chronic
  shortness of breath" — personal (a real student with ID); T090 "My aunt … is struggling" (no condition) — not
  personal; T097 "I'm worried about my results" (blood-pressure context) — personal.

Rule changes made from the v1 misses (all general, none names a specific test message): a possessive before a
condition or vital sign ("my diabetes", "her asthma", "my uncle's pneumonia", "my blood pressure is spiking"),
she/he as subjects, more symptom and medicine words, a course-word guard after a term ("the asthma section"),
letter grades and GPAs without "I got". After that the rules were frozen and v2 was generated.
