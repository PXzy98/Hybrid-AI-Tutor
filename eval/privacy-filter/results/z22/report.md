# Z22: privacy filter test sets per course type, and E6 on current main (2026-11-20)

Numbers from `run.py --fast`, `run.py --beta --fast` (rules only, `a5_rules`, no model calls) and
`course_sets.py` on main at 97f3898. All test data is fictional. No privacy rule was changed.

## 1. Did E6 change since the last report? No

| Set | Positives / negatives | Leak, last report = now | Over-redaction, last report = now |
|---|---|---|---|
| main | 208 / 112 | 0.0% | 0.0% |
| v1 | 89 / 13 | 9.0% | 0.0% |
| v2 | 93 / 9 | 21.5% | 0.0% |
| v3 | 186 / 18 | 27.4% | 0.0% |
| v4 | 184 / 20 | 45.1% | 0.0% |
| v5 | 163 / 39 | 37.4% | 12.8% |

Every per-type recall is identical as well. The committed `beta_holdout3` / `beta_holdout4` results are older
rounds, so v3 and v4 were re-run at 0a6eddd (the last E6 report): they match current main. Z25 (#112) and S16
(#111) did not affect E6. The main `results/report.md` and `holdout_test` (v2) files are pre-Beta runs; their
older numbers (v2 leak 47.3%) differ only because of the Beta rounds before 2026-11-02.

## 2. New held-out sets per course type

Written blind (only the profile YAML files were read, not the recognizers); built by `make_course_sets.py`,
scored by `course_sets.py` with the course's profile and, for comparison, with `general`.

| Set | Positives / negatives | Profile | Leak | Over-redaction |
|---|---|---|---|---|
| ECE (`ece_holdout.jsonl`) | 25 / 16 | ece | 24.0% (general profile: 52.0%) | 6.2% |
| Computer science (`cs_holdout.jsonl`) | 16 / 14 | computer_science | 12.5% (general: 43.8%) | 7.1% |
| Life science (`life_holdout.jsonl`) | 15 / 15 | life_science (medical_science: same) | 13.3% | 13.3% |
| General (`general_holdout.jsonl`) | 15 / 10 | general | 6.7% | 10.0% |

The life-science leak is two out-of-scope items (a lab IP address and a repository URL, for which
`life_science` has no recognizer); in scope it is 0 of 13.

### Recall per entity

PERSON, STUDENT_ID, EMAIL, PHONE, ADDRESS, POSTAL_CODE, DATE_OF_BIRTH, GRADE and HEALTH_CARD are found 100% in
every set, except PERSON 83% on ECE. Weak spots:

| Entity | ECE | Computer science | General |
|---|---|---|---|
| SECRET | 50% | 78% | 0% (1 span) |
| INTERNAL_ADDRESS | 83% | 100% | n/a |
| REPO_URL | 75% | 100% | n/a |

### Misses (an identifier stayed in the text)

- EH005: `AWS_SECRET_ACCESS_KEY=` followed by a 40-character key.
- CH001: `aws_secret_access_key='...'` in a Python call.
- EH014: `API_TOKEN="tok_..."`.
- EH018: the password in `mqtt://user:PASSWORD@10.30.2.9:1883`.
- CH009: `'Bearer ...'` inside a Python dict.
- GH008: "the password for the library is X" (a password in prose).
- EH012: `172.16.8.203`.
- EH010: `git@github.com:account/repo.git` (only the e-mail-like part is found).
- EH002: a name after "My TA".

### Over-redaction (a course term replaced by a placeholder; nothing leaks)

- Eponyms: Mealy, Smith chart, Hardy-Weinberg, Michaelis-Menten, Mendel, Linnaeus, Krebs.
- Thinkers: Kant, Rawls.
- Code terms: Django taken as PERSON; "C" in "my C code" taken as GRADE.

This is the largest utility problem: it hits three of the four sets, and life science loses 5 of its 15 clean
questions.

## 3. Suggestions for a later rule change (not implemented; a rule change needs a full E6 re-run)

1. An allow-list per course type for eponyms, thinkers and framework or language names.
2. Secret shapes: the AWS secret key after `secret_access_key`; TOKEN / KEY / SECRET assignments with other
   prefixes, also inside dicts; the password in URL user info; "password for X is V" in prose.
3. The whole 172.16.0.0/12 range, with and without a port.
4. SCP-style repository addresses `git@host:account/repo.git`.
5. A name after a role word (TA, partner, prof).
6. Decide whether `life_science` and `general` get the lab address and repository URL recognizers.

Still open in Z22: a fresh held-out medical set, and the rule changes above.
