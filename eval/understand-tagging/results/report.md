# E1: understand-step tagging (design §11)

Model `qwen3.5:9b` on `http://192.168.2.25:11434` · 40 cases × 2 · thinking off, temperature 0, JSON schema with the topic's IDs. Cases are a DRAFT set (to be extended to 120–150 by the team).

| Metric | Value | Target (ideal / marginal) | Verdict |
|---|---|---|---|
| KC top-1 accuracy (74 questions with a KC) | 92% (68/74) | ≥ 85% / 75% | ✅ ideal |
| No-KC accuracy (6 off-topic) | 6/6 | — | informative |
| Misconception precision | 88% (14/16) | ≥ 80% / 70% | ✅ ideal |
| Misconception recall | 100% (14/14) | — | informative |
| Confusion accuracy | 88% | — | informative |
| Question-type accuracy | 70% | — | informative |
| Latency p50 / p95 | 1.05 s / 1.14 s | p50 ≤ 0.6 s | ❌ above target |
| Failed calls (step would be skipped) | 0 | 0 | ✅ |

## KC errors

- U08: gold ['HBP.2'] · predicted ['HBP.1'] · My reading was high once at the pharmacy, so that means I have high blood pressure, right?
- U10: gold ['HBP.2'] · predicted ['HBP.1'] · What is white coat hypertension?
- U15: gold ['HBP.3'] · predicted ['HBP.6'] · Can young people get high blood pressure too?
- U08: gold ['HBP.2'] · predicted ['HBP.1'] · My reading was high once at the pharmacy, so that means I have high blood pressure, right?
- U10: gold ['HBP.2'] · predicted ['HBP.1'] · What is white coat hypertension?
- U15: gold ['HBP.3'] · predicted ['HBP.6'] · Can young people get high blood pressure too?

## Misconception differences

- U35: gold ['HBP.MC11'] · predicted ['HBP.MC2', 'HBP.MC11'] · I only take my pills on days when I feel bad, that's fine isn't it?
- U35: gold ['HBP.MC11'] · predicted ['HBP.MC2', 'HBP.MC11'] · I only take my pills on days when I feel bad, that's fine isn't it?

Decision rule (design §11 E1): below marginal → keep `learner.weak_evidence: false` and topic-only retrieval.
