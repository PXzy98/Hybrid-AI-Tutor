# Z2: Qwen3.5 9B vs 27B

Same course questions for both models, both with RAG (the app's medical retriever, 4 passages), temperature 0,
thinking off, called through OpenRouter. The course's own model server was not reachable from the development
machine on 2026-11-08, so this measures quality and hosted cost, not local latency or throughput
(`eval/load-test/run.py` measures those on the server). Full results: [results/report.md](results/report.md).

```
.venv\Scripts\python eval\model-compare\run.py            # full run; answers are cached in results/answers.jsonl
.venv\Scripts\python eval\model-compare\run.py --smoke    # 3 items, 2 questions
```

Needs `OPENROUTER_API_KEY` (environment or `.env`). Only course content is sent: the demo course's check
items and the 20 course questions of `eval/medical_rag_cases.json`, no student data. Tests:
`backend/tests/test_model_compare.py` (no model call).

## Results (2026-11-08, second run after the review of #51)

| | 9B | 27B |
|---|---|---|
| Check items (84, multiple choice), without RAG / with RAG | 100% / 100% | 100% / 100% |
| Open questions with RAG: better in both verdicts (20 pairs; 12 ties or split) | 2 | 6 |
| Hosted cost per open answer (529 prompt tokens, about 120 answer tokens) | $0.00002 | $0.00036 |
| Median hosted answer time (open question) | 1.1 s | 2.1 s |
| Weights, 4-bit / KV cache per 8k-token request (estimate) | 5.0 GiB / 0.25 GiB | 15.1 GiB / 0.50 GiB |

All runs together cost $0.16. The judge is `anthropic/claude-sonnet-5.5` (another family), blind; each pair is
judged twice, once in each order, and a model wins only when both verdicts agree.

**Why both orders.** The first run judged each pair once (random order) and gave 27B 10 wins to 4. Judging both
orders showed a strong position effect: with the 27B answer second it was picked 16 times out of 20; with the
9B answer second, the 9B was picked 8 times and the 27B 6 times. Only 8 of the 20 pairs got the same verdict in
both orders. The single-verdict numbers mostly measured that effect.

## What it means

- The check items are too easy to compare the models: both get every item right even without RAG (ceiling
  effect). A harder item set is needed to measure the difference on graded questions.
- On open questions the difference is small. Where the judge is consistent, the 27B is better 6 times and the
  9B 2 times; for the other 12 questions there is no robust difference. The judge's reasons are staying on the
  question, using the passages fully, and not adding claims the passages do not support. With 20 questions this
  is a weak direction, not a measurement of how much better the 27B is.
- Both fit on one 24 GB GPU with 4-bit weights. Qwen3.5 uses full attention in only every fourth layer, so the
  KV cache is small: the estimate for the 27B is about 19 GiB with 4 parallel 8k-token requests. A 48 GB GPU
  leaves room for more parallel students. Confirm with the vLLM load test before buying.
- The 9B answers in about half the time and costs much less; on this evidence it is a reasonable default.

**Suggestion for the decision (Z):** keep the 9B as the default for now; plan for the 27B (4-bit, 24 GB GPU) only
if a harder question set or instructor spot checks (tier 4, Z12) show a clear gain for the course, and the load
test on the real server confirms the number of parallel requests.
