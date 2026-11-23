# Z22d: personal health details the term list did not know; the local model's check on by default (2026-11-23)

Found while planning the video (T10): "I have a perianal abscess and need to submit my assignment late" had no
finding in any profile (`computer_science`, `ece`, `general`), so it was cloud-safe; with a name and a student
number the cloud would have received "I'm <PERSON_1>, student number <STUDENT_ID_1>. I have a perianal abscess
...". All test data is fictional. Before = main at 3677917, after = this branch; same machine, same commands:

```
run.py --fast
run.py --beta --fast                                   (cases.jsonl)
run.py --beta --fast --cases holdout{,2,3,4,5}.jsonl   (v1 to v5)
course_sets.py                                         (Z22 sets)
ece.py
```

## What changed

- `backend/app/privacy/recognizers/health_detail.py` (every profile): more condition terms, counted only when
  attributed to the student or a relative like the other terms: abscesses, words ending in -itis, named
  tumours (-oma), cysts, ulcers, hernias, haemorrhoids, kidney stones, gallstones, strep throat, shingles,
  chickenpox, measles, mumps, food poisoning, stomach flu, concussions, injuries, bleeding, fractures and
  sprains of a body part; "diagnosed with / treated for / hospitalized for <up to three words>"; "I broke my
  wrist" style injuries.
- `privacy.llm_check` is on by default (code and `config.yaml`); it reads a cloud-bound question when it names
  a health topic **or** a first-person wording may carry a health detail the rules do not know
  (`app/privacy/policy.py`, `may_reveal_health`).

## E6: not worse on any set

| Set (`a5_rules`) | Leak before | Leak after | Over-redaction before = after | Health recall before | after |
|---|---|---|---|---|---|
| main (`run.py --fast`) | 0.0% | 0.0% | 0.0% | 46/46 | 46/46 |
| Beta on cases.jsonl | 0.0% | 0.0% | 0.0% | 46/46 | 46/46 |
| v1 (`holdout.jsonl`) | 9.0% | 9.0% | 0.0% | 76/82 | 76/82 |
| v2 (`holdout2.jsonl`) | 21.5% | 21.5% | 0.0% | 97/113 | 97/113 |
| v3 (`holdout3.jsonl`) | 27.4% | 27.4% | 0.0% | 102/149 | 102/149 |
| v4 (`holdout4.jsonl`) | 45.1% | 45.1% | 0.0% | 127/196 | 127/196 |
| v5 (`holdout5.jsonl`) | 37.4% | **36.2%** | 12.8% | 156/199 | **158/199** |

Every other metric of these runs (333 in the main run, 40 to 66 per Beta run, the `b1_policy` configuration,
health sensitivity and specificity) is identical. The two v5 items now found: V188 "my sprained foot", V191
"I've been diagnosed with CAP".

Z22 course sets (`course_sets.py`, 222 metrics) and `ece.py` (23 metrics): identical before and after (ECE with
`ece` 4.0% leak, CS with `computer_science` 0.0%, life science 13.3%, general 0.0%; the ECE set 0.0%).

These runs use the rules only; the local model's check needs a model and is measured separately (E6 v4 Beta:
cloud exposure 15.8% -> 2.7%, `results/beta.md`).

## How often the local model's check runs

Questions of every E6 set and of the course question sets (`eval/course-rag-packs/questions`, paraphrases)
that the rules leave cloud-bound, and how many of them the check reads (the latency cost: one short call,
0.3 s on vLLM in MODEL_CONNECTIONS.md):

| | Questions | Cloud-bound | Read before | Read after |
|---|---|---|---|---|
| All sets | 1692 | 1162 | 502 | 513 |
| Course questions (CS50x, circuits, algorithms, signals; 182) | 182 | 182 | 0 | 1 |
| Course questions (biology, genetics, pathology, pharmacology; 119) | 119 | 119 | 17 | 20 |

The eleven new reads are general questions with a new condition word (-itis, -oma) or "I have a ..." wording;
the check answers them "not personal" and they still go to the cloud. Personal-health questions the rules leave
cloud-bound and the check did not read: 4 before, 3 after ("hey i think i have a migran ..." is now read).

## The check on the real local model

The deployment's trusted local vLLM (Qwen3.5-9B, thinking off), with the prompt on main, eight fictional
redacted texts as the check sees them:

| Text | Expected | Flagged | Time |
|---|---|---|---|
| "I'm <PERSON_1>, student number <STUDENT_ID_1>. I have a perianal abscess and need to submit Assignment 4 late ..." | personal | yes | 344 ms |
| "I have a pilonidal sinus, can I hand in the lab later?" | personal | yes | 229 ms |
| "Can I get an extension because my week was rough? I spent two nights in the ER." | personal | yes | 229 ms |
| "I'm not feeling well since Monday, I keep throwing up. When is the quiz due?" | personal | yes | 229 ms |
| "How is an abscess treated?" | general | no | 229 ms |
| "Can I get an extension because my laptop broke?" | general | no | 229 ms |
| "I have a question about recursion in Python." | general | no | 230 ms |
| "Compare memory safety in C, Rust and Go for systems programming today." | general | no | 229 ms |

## The check's prompt for every course type, on the real model

The prompt said "a student's message to a health-course tutor". It now says "a course tutor ... about any
subject", counts a health detail "also when it is given as the reason for late or missed work", and says a
general health question stays general "even when the message also contains a name or a number". A first,
wider wording (injuries, treatments, "a broken laptop or a busy week" as examples) over-flagged general health
questions that carry a name or a number ("Student ID <ID> here. how bad is exercise induced asthma?") and was
dropped.

`run.py --beta --llm-check-only` (new: the rules, the policy and the check, without GLiNER and A4), the lab vLLM
(Qwen3.5-9B, temperature 0), configuration `b2_llm_classify` (the app: rules + check). Sensitivity / specificity
in % (personal-health questions kept local / other questions left cloud-eligible):

| Set | main (old trigger, old prompt) | wider trigger, old prompt | first new prompt | **this PR (wider trigger, revised prompt)** |
|---|---|---|---|---|
| main set | 96.7 / 98.5 | 96.7 / 98.2 | 98.4 / 92.3 | **96.7 / 97.5** |
| v1 | 100.0 / 80.0 | 100.0 / 80.0 | 100.0 / 80.0 | **100.0 / 85.0** |
| v2 | 98.8 / 59.1 | 98.8 / 63.6 | 98.8 / 68.2 | **97.5 / 77.3** |
| v3 | 98.2 / 75.6 | 99.1 / 73.3 | 99.1 / 62.2 | **98.2 / 72.2** |
| v4 | 97.7 / 78.1 | 99.2 / 78.1 | 100.0 / 68.5 | **99.2 / 78.1** |
| v5 | 98.4 / 76.0 | 98.4 / 76.0 | 99.2 / 69.3 | **98.4 / 77.3** |

Against main, over all six sets: personal-health questions caught 3 more, missed 2 more (net +1); general
questions kept local without need 13 more, 15 fewer (net 2 fewer). Per set: better or equal on v1, v4, v5;
the main set's specificity -1.0 point (3 questions with a name or e-mail next to a general question), v2 one
personal question less ("Marcus Chen says his uncle is having problems", a debatable label) but specificity
+18.2, v3 specificity -3.4 points (lecture or quiz messages with a name). `b3_policy_llm` specificity within
-1.3 to +2.5 points. Wider trigger alone (old prompt): v3 and v4 sensitivity +0.9 and +1.5, specificity at most
-2.3. The Z22 course sets cannot run through `run.py` (no `variant` field); the rules-only numbers above cover
them.

Fourteen fictional redacted texts on the same model with the revised prompt, 14 of 14 right, 199 to 210 ms:
the abscess sentence with placeholders, "a pilonidal sinus", "two nights in the ER", "I keep throwing up", "My
mom had a stroke ... Verilog lab", "I tore my ACL" (personal); "How is an abscess treated?", "extension because
my laptop broke", "three other deadlines this week", "a memory leak", "the ECG signal in the DSP assignment",
"a fever of questions about pointers", recursion, memory safety (general).

## Negatives checked by unit tests

`tests/test_privacy.py::test_z22d_general_questions_stay_cloud_safe`: "How is an abscess treated?", bronchitis
vs pneumonia, fracture mechanics, "how patients are diagnosed with sleep apnea", "a diploma", stress fractures
in long bones, the stages of melanoma, "I broke my laptop screen", "treated for the midterm conflict", "a
sprained ankle case study". `tests/test_generate.py`: "I have a question about recursion" and "I have a bug in
my loop" do not trigger the check.
