# E6 for engineering courses (task Z11)

47 fictional ECE questions (22 positive, 25 negative), `ece_cases.jsonl`; every key is a fake made for this set. Protected = at least 80% of the characters covered by findings. The rules were written with this set in view: read the numbers as optimistic until a held-out ECE set exists.

| Profile | Leak: positive | Over-redaction: negative | Course terms lost | Recall EMAIL_ADDRESS | Recall INTERNAL_ADDRESS | Recall PERSON | Recall REPO_URL | Recall SECRET | Recall STUDENT_ID |
|---|---|---|---|---|---|---|---|---|---|
| general | 40.9% | 0.0% | 1 | 100% | 0% | 100% | 0% | 100% | 100% |
| ece | 0.0% | 0.0% | 1 | 100% | 100% | 100% | 100% | 100% | 100% |

## `general`: misses and false findings

Misses: ECE010 INTERNAL_ADDRESS, ECE010 INTERNAL_ADDRESS, ECE011 INTERNAL_ADDRESS, ECE011 INTERNAL_ADDRESS, ECE012 INTERNAL_ADDRESS, ECE013 INTERNAL_ADDRESS, ECE014 INTERNAL_ADDRESS, ECE015 REPO_URL, ECE016 REPO_URL, ECE017 REPO_URL, ECE020 INTERNAL_ADDRESS, ECE020 REPO_URL

False findings: ECE013 keep "Docker"

## `ece`: misses and false findings

Misses: none

False findings: ECE013 keep "Docker"
