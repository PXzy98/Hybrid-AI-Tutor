# E6 utility: answer quality after redaction (offline experiment)

45 fictional questions (30 with identifiers only, 15 with a personal health detail). Answers by `qwen3.5:9b`, judged by `gemma4:e4b` against the answer to the original question (1–5, 5 = as good as the reference).

| Version | Questions | Mean score | Score ≥ 4 | Artefacts flagged | Placeholders left after restore |
|---|---|---|---|---|---|
| identifiers only · placeholder | 30 | 4.37 | 80% | 9 | 0 |
| identifiers only · surrogate | 30 | 4.50 | 77% | 5 | 0 |
| personal health · placeholder | 15 | 3.07 | 13% | 9 | 0 |
| personal health · surrogate | 15 | 2.53 | 7% | 10 | 2 |
| personal health · hypothetical | 15 | 4.47 | 100% | 6 | 0 |

Hypothetical rewrite (B3): 0 of 15 rewrites still contained PII or a personal health statement and were rejected (those questions would stay local).

Judge failures (score 0) are excluded. B2 and B3 are offline experiments; the app uses placeholders (B1).
