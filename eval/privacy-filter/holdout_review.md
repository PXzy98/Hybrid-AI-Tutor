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

## v3 (Beta upgrade, 2026-11-02): a clean test set after v2 was used for analysis

The misses on v2 were read while planning the Beta upgrade, so v2 is no longer a clean test. The rules of the
Beta upgrade were then developed on the main set and v1 only, and a new set was made **before** any filter
was run on it:

| Set | File | Written by | Labelled by |
|---|---|---|---|
| v3 | `holdout3.jsonl` (raw: `holdout3a_raw.jsonl`, `holdout3b_raw.jsonl`; labels: `labels3.txt`) | gemma4:26b (seed 63) and qwen3.8:27b (seed 64), 102 each, same 11 scenarios | hand, before the first run (frozen in commit "held-out v3") |

- Two generators that wrote none of the earlier data (qwen3.5 wrote the question bank, gemma4:e4b v1 and v2),
  through Ollama's own API with thinking off (`make_holdout.py --native`).
- 204 messages: 186 positive, 18 negative, 114 personal health. `label_holdout.py` checks that every labelled
  value occurs verbatim in its message.
- Same conventions as above. Debatable labels are listed at the top of each batch in `labels3.txt`
  (e.g. GE034 "Check 300112994 for diabetes trends" labelled personal; GE097 "if she has hypertension" not
  personal; targets such as "he needs a 90% to pass" are not grades; staff names count as names).
- The order of work: rules frozen on dev data → v3 generated and labelled → one run of every configuration.

## v4 (round 2 of the Beta upgrade): the final test

Round 2 fixed general gaps seen on v3 (so v3 is "seen" for round 2). After the round-2 rules were frozen, v4 was
made the same way: gemma4:31b (seed 65) and qwen3.5:35b (seed 66), 102 each, hand-labelled in `labels4.txt`
before any run, frozen in its own commit, then run once. 204 messages: 184 positive, 20 negative, 131 personal
health. The qwen batch wrote 13 ten-digit "student numbers"; they are labelled as student numbers. Results:
`results/beta.md`.
