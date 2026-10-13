# E1: understand-step tagging (design §11)

Model `gemma4:e4b` on `http://192.168.2.25:11434` · 40 cases × 2 · thinking off, temperature 0, JSON schema with the topic's IDs. Cases are a DRAFT set (to be extended to 120–150 by the team).

| Metric | Value | Target (ideal / marginal) | Verdict |
|---|---|---|---|
| KC top-1 accuracy (74 questions with a KC) | 100% (74/74) | ≥ 85% / 75% | ✅ ideal |
| No-KC accuracy (6 off-topic) | 6/6 | — | informative |
| Misconception precision | 100% (14/14) | ≥ 80% / 70% | ✅ ideal |
| Misconception recall | 100% (14/14) | — | informative |
| Confusion accuracy | 99% | — | informative |
| Question-type accuracy | 80% | — | informative |
| Latency p50 / p95 | 0.35 s / 0.41 s | p50 ≤ 0.6 s | ✅ ideal |
| Failed calls (step would be skipped) | 0 | 0 | ✅ |

## KC errors

- none

## Misconception differences

- none

Decision rule (design §11 E1): below marginal → keep `learner.weak_evidence: false` and topic-only retrieval.
