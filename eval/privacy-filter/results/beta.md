# E6 Beta: privacy filter upgrade (2026-11-02)

Goal: lower what reaches the cloud without over-fitting the rules to the test data. Primary metric: **cloud
exposure**, the share of labelled questions the filter would send to the cloud with PII still in them (as in
`exposure.py`). Utility cost: general questions kept local without need ("left cloud-eligible") and
over-redaction of questions without PII.

## How over-fitting was avoided

| Set | Role | Used for |
|---|---|---|
| main set (404), v1 (102) | development | every rule change was checked here |
| v2 (102) | **seen**: its misses were read while planning | reported, not a clean test |
| v3 (204, gemma4:26b + qwen3.8:27b) | clean test of round 1 | generated and hand-labelled after the round-1 rules were frozen, run once |
| v4 (204, gemma4:31b + qwen3.5:35b) | clean test of round 2 | generated and hand-labelled after the round-2 rules were frozen, run once |
| v5 (202, gemma4:12b + nemotron-cascade-2) | clean test of round 3 (final) | generated and hand-labelled after the round-3 rules were frozen, run once |

Round 2 fixed general gaps seen on v3 (bare grades, lower-case names after a title or label, local phone
numbers, eponym triads), so v3 is "seen" for round 2 and v4 is its test. Labels: `labels3.txt`, `labels4.txt`
(debatable cases listed at the top); provenance: `holdout_review.md`.

## Configurations (`run.py --beta`)

- `a5_rules`: all recognizers, including the Beta ones (`health_context`, `grade_context`, `person_context`,
  `contact_extra`, the wider vocabulary in `health_detail`, ID context in `student_id`).
- `b1_policy`: + `privacy.local_if_identified_health_topic` (a name/number together with a health topic stays
  local).
- `b2_llm_classify`: + `privacy.llm_check` (the local model answers yes/no on the redacted text of a cloud-bound
  question that mentions a health topic; fails closed).
- `b3_policy_llm`: both.
- `a4_rules_llm`: + the local model listing leftover PII (extraction, every question).
- `b4_gliner_ids`: + GLiNER restricted to names, numbers and contacts.

## v5: clean test of round 3 (final)

Round 3 fixed general gaps seen on v4 (lower-case sign-offs and "x here", "subject score is X" grades, more
eponym nouns, a BP reading typo), checked for regressions on the main set and v1-v4 (no set got worse). v5 was then
written by gemma4:12b and nemotron-cascade-2, hand-labelled in `labels5.txt` and run once. v5 is easier than v4
(the old filter already leaked less), so compare rows within the table, not across sets.

| Configuration | Exposure: any PII | identifier | personal health | Personal health kept local | General left cloud-eligible | Over-redaction | p95 latency |
|---|---|---|---|---|---|---|---|
| main before Beta | 8.0% | 0.0% | 7.4% | 90.6% | 92.0% | 15.4% | ~10 ms |
| **round-3 rules** (`a5_rules`) | 6.1% | 0.0% | 5.5% | 92.9% | 89.3% | 12.8% | 12 ms |
| + policy (`b1`) | 3.7% | 0.0% | 3.1% | 96.1% | 53.3% | 12.8% | 11 ms |
| **+ LLM check (`b2`)** | **1.8%** | 0.0% | **1.2%** | **98.4%** | 76.0% | 12.8% | 1.4 s |
| + policy + LLM (`b3`) | 1.2% | 0.0% | 0.6% | 99.2% | 50.7% | 12.8% | 1.4 s |
| + LLM extraction (`a4`) | 3.7% | 0.0% | 3.1% | 96.1% | 84.0% | 23.1% | 4.5 s (every question) |
| + GLiNER ids (`b4`) | 6.1% | 0.0% | 5.5% | 92.9% | 89.3% | 43.6% | 107 ms |

Round-3 rules on the seen sets (no regressions): v3 exposure 18.3% (round 1) -> 15.6%, over-redaction 11.1% -> 0%;
v4 15.8% (round 2) -> 14.7%, over-redaction 5% -> 0%.

Over-redaction left on v5 (5 of 39 negatives): questions about a hypothetical person whose vitals are named
("a patient with pneumonia ... their oxygen levels", "someone has a migraine", "a patient with a blood pressure of
150/95", "is 130 over 80 a good bp reading"), and "i got pneumonia vaccine". These over-redact (and keep the
question local) but leak nothing. A rule for hypothetical subjects is the next step; it needs a v6 to measure.

## v4: clean test of round 2

| Configuration | Exposure: any PII | identifier | personal health | Personal health kept local | General left cloud-eligible | Over-redaction | p95 latency |
|---|---|---|---|---|---|---|---|
| main before Beta | 22.8% | 7.6% | 17.4% | 75.6% | 94.5% | 10.0% | ~10 ms |
| round-1 rules | 16.3% | 4.3% | 12.5% | 82.4% | 93.2% | 10.0% | ~10 ms |
| **round-2 rules** (`a5_rules`) | 15.8% | 4.3% | 12.5% | 82.4% | 93.2% | 5.0% | ~10 ms |
| + policy (`b1`) | 6.5% | 2.2% | 4.9% | 93.1% | 39.7% | 5.0% | ~10 ms |
| **+ LLM check (`b2`)** | **2.7%** | 2.2% | **0.5%** | **99.2%** | 79.5% | 5.0% | ~1.4 s |
| + policy + LLM (`b3`) | 2.2% | 1.6% | 0.5% | 99.2% | 39.7% | 5.0% | ~1.4 s |
| + LLM extraction (`a4`) | 3.8% | 0.0% | 3.8% | 94.7% | 91.8% | 5.0% | ~3.2 s (every question) |
| + GLiNER ids (`b4`) | 13.0% | 0.5% | 12.5% | 82.4% | 93.2% | 35.0% | ~110 ms |

## v3: clean test of round 1

| Configuration | Exposure: any PII | identifier | personal health | Personal health kept local | General left cloud-eligible | Over-redaction |
|---|---|---|---|---|---|---|
| main before Beta | 26.3% | 6.5% | 19.9% | 67.5% | 93.3% | 11.1% |
| round-1 rules | 18.3% | 3.2% | 14.5% | 76.3% | 92.2% | 11.1% |
| + policy | 7.0% | 2.2% | 4.3% | 93.0% | 31.1% | 11.1% |
| + LLM check | 4.3% | 1.6% | 1.1% | 98.2% | 80.0% | 11.1% |
| + policy + LLM | 3.2% | 1.6% | 0.5% | 99.1% | 31.1% | 11.1% |
| + LLM extraction | 8.6% | 0.5% | 7.5% | 87.7% | 88.9% | 22.2% |
| + GLiNER ids | 17.2% | 0.0% | 14.5% | 76.3% | 92.2% | 16.7% |

Development sets (round-1 rules): v1 exposure 10.1% → 3.4% (rules) → 0.0% (+ LLM check); main set 4.4% → 1.5% →
0.7%; v2 (seen) 20.4% → 8.6% → 1.1%. Full reports: `beta_holdout4/`, `beta_holdout3/`, `beta_holdout2/`,
`beta_dev_holdout/`, `beta_dev_cases/` (`report.md`, `metrics.json`, `predictions.jsonl`).

## Recommendation

- **Rules: always on** (they are the default). Over-redaction halved on v4; exposure down by a third.
- **`privacy.llm_check`: on wherever the local model runs** (`PRIVACY__LLM_CHECK=true`). The largest single gain
  (exposure 15.8% → 2.7%, personal health kept local 82% → 99%). Cost: about one in five general questions that
  mention a health topic is answered locally, and only such cloud-bound questions wait ~1.4 s. It runs at the
  cloud gate (`generate.py`), so local answers pay nothing. Off in `config.yaml` because CI has no local model.
- **`privacy.local_if_identified_health_topic`: off.** Little extra privacy over the LLM check, but 60% of the
  general questions with a name or number would be answered locally. In real use few students type their own
  name, so the cost there is lower than in these sets, which put identifiers in most messages on purpose.
- Not adopted: LLM extraction (slower on every question, more health misses) and GLiNER (over-redaction 17–35%).

## Known gaps (v4, round-2 rules; from `beta_holdout4/predictions.jsonl`)

Missed by the rules (`a5_rules`), besides health details:

- Names (25): lower-case names in a sign-off or "x here" ("- marco silva", "chen wei here"), single first
  names after "I'm" ("I'm Mateo"), hyphenated first names ("Jean-Pierre").
- Grades (16): a value after a subject rather than "my grade" ("asthma score is 45/F", "migraine unit mark
  dropped to 58.0", "pneumonia test result is 91/A", "grade is 78.5").
- Student numbers (13): all 13 are 10-digit numbers the generator wrote by mistake ("3009912345"); no real
  student number has that format, so they are left alone.
- Over-redaction: one eponym taken for a name ("McBurney point").

With the LLM check (`b2`), five labelled questions still reach the cloud with something left: four names in
grade or contact messages and one misspelled condition ("i think i have a migran"). None of the four name cases
contains a health detail. These shapes were found on the final test set, so fixing them needs a new held-out
set (v5) to measure the fix.
