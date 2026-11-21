# Z22b: low-risk privacy rule changes (2026-11-20)

Rules that only redact more, decided in docs/v5-plan.md section 10 after the Z22 report
([../z22/report.md](../z22/report.md)). Rules only (`a5_rules`), no model calls; all test data is fictional.
Before = main at b64de05, after = this branch; both runs on the same machine with the same commands:

```
run.py --fast
run.py --beta --fast                                   (cases.jsonl)
run.py --beta --fast --cases holdout{,2,3,4,5}.jsonl   (v1 to v5)
course_sets.py                                         (Z22 sets; course_sets_metrics.json here)
```

## What changed

In `backend/app/privacy/recognizers/engineering.py`:

| Rule | Recognizer (profiles) | Example (fictional) |
|---|---|---|
| A credential name with a prefix or suffix (`AWS_SECRET_ACCESS_KEY=`, `API_TOKEN="..."`, `aws_secret_access_key='...'`, dict entries); the value must look like a credential (8+ characters with a digit or symbol, or 20+ in mixed case; not a placeholder, call or index) | `secret_token` (base: every course) | `AWS_SECRET_ACCESS_KEY=wJalr...` |
| `Bearer <token>` | `secret_token` | `{'Authorization': 'Bearer FAKEtoken...'}` |
| The password in URL user info | `secret_token` | `mqtt://user:Rt7Fake!Pass@10.30.2.9:1883` |
| "the password for X is V" in prose | `secret_token` | "My Wi-Fi password for the library is Campus!Fake2026" |
| Private IPv4 addresses before a full stop. 172.16.0.0/12 was already in the pattern; the miss was the sentence's full stop after the address. Now only a digit, `.digit` or `/digit` after the address rules it out (all private ranges) | `internal_address` (ece, computer_science) | "... at 172.16.8.203." |
| SCP-style remotes `git@host:account/repo(.git)` | `repo_url` (ece, computer_science) | `git@github.com:account/repo.git` |

## E6: not worse on any set

| Set | Leak before | Leak after | Over-redaction before | Over-redaction after |
|---|---|---|---|---|
| main (`run.py --fast`, `a5_rules`) | 0.0% | 0.0% | 0.0% | 0.0% |
| Beta on cases.jsonl | 0.0% | 0.0% | 0.0% | 0.0% |
| v1 (`holdout.jsonl`) | 9.0% | 9.0% | 0.0% | 0.0% |
| v2 (`holdout2.jsonl`) | 21.5% | 21.5% | 0.0% | 0.0% |
| v3 (`holdout3.jsonl`) | 27.4% | 27.4% | 0.0% | 0.0% |
| v4 (`holdout4.jsonl`) | 45.1% | 45.1% | 0.0% | 0.0% |
| v5 (`holdout5.jsonl`) | 37.4% | 37.4% | 12.8% | 12.8% |

All 126 metrics of the main run (recall per type, precision, leak and over-redaction per configuration) and all
12 metrics of each Beta run are identical before and after: the E6 sets have no text of these shapes.

## Z22 course sets

| Set, profile | Leak before | Leak after | Over-redaction before = after |
|---|---|---|---|
| ECE, `ece` | 24.0% | **4.0%** | 6.2% |
| ECE, `general` | 52.0% | 44.0% | 6.2% |
| Computer science, `computer_science` | 12.5% | **0.0%** | 7.1% |
| Computer science, `general` | 43.8% | 31.2% | 7.1% |
| Life science, `life_science` / `medical_science` / `general` | 13.3% | 13.3% | 13.3% |
| General, `general` | 6.7% | **0.0%** | 10.0% |

Recall per type with the course's profile: SECRET 50% -> 100% (ECE), 78% -> 100% (CS), 0% -> 100% (general);
INTERNAL_ADDRESS 83% -> 100% and REPO_URL 75% -> 100% (ECE).

The eight Z22 misses decided for this task are now found: EH005, CH001, EH014, EH018, CH009, GH008, EH012,
EH010. Left for Z22c (design first): EH002 (a name after "My TA", the remaining ECE leak), the two life-science
items outside the profile's scope (a lab address and a repository URL; whether `life_science` and `general`
get those recognizers), and the over-redaction of course terms that look like names.

## Negatives checked by unit tests

`tests/test_privacy_z11.py::test_z22b_course_text_without_secrets_is_kept`: `primary_key=True`,
`max_tokens=4096`, `cache_key: user_profile_settings`, `sort_key = lambda ...`, `API_KEY=YOUR_API_KEY_HERE`,
"the bearer token scheme", `token_count = len(tokens)`, "the password for the quiz is given in class",
`172.16.0.0/12` and the public 172.32.1.1, 8.8.8.8, a version number 3.172.16.4; after the review of the PR also `cache_key=request.path`, `primary_key="student.id"`, `token_count=10000000`, `sort_key: ...`, `partition_key = ...`, `max_token`, `page_token`. A prefixed name counts only when its last part is a credential word, and a name ending in `key` also needs a credential word before it (`api`, `secret`, `access`, ...); dotted code expressions and plain numbers are not values. The E6 and Z22 numbers above are the same after this change. Behaviour that is not new and
not changed here: a dotted version that is also a private address (10.2.1.4) is still redacted.
