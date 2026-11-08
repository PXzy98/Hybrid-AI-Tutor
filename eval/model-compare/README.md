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

## Results (2026-11-08)

| | 9B | 27B |
|---|---|---|
| Check items (84, multiple choice), without RAG / with RAG | 100% / 100% | 100% / 100% |
| Open questions with RAG, judged better (20 pairs; 6 ties) | 4 | 10 |
| Hosted cost per open answer (529 prompt tokens, about 120 answer tokens) | $0.00008 | $0.00040 |
| Median hosted answer time (open question) | 1.3 s | 2.3 s |
| Weights, 4-bit / KV cache per 8k-token request (estimate) | 5.0 GiB / 0.25 GiB | 15.1 GiB / 0.50 GiB |

The whole run cost $0.10. The judge was `anthropic/claude-sonnet-5.5` (another family), blind, with the order
of the two answers randomized.

## What it means

- The check items are too easy to compare the models: both get every item right even without RAG (ceiling
  effect). A harder item set is needed to measure the difference on graded questions.
- On open questions the 27B answers were judged better more often (10 vs 4). The judge's reasons are staying
  on the question, using the passages fully, and not adding claims the passages do not support. Both models
  lost pairs for unsupported claims, the 9B more often. With 20 questions and one judge this is a direction,
  not a precise measurement.
- Both fit on one 24 GB GPU with 4-bit weights. Qwen3.5 uses full attention in only every fourth layer, so the
  KV cache is small: the estimate for the 27B is about 19 GiB with 4 parallel 8k-token requests. A 48 GB GPU
  leaves room for more parallel students. Confirm with the vLLM load test before buying.

**Suggestion for the decision (Z):** the 27B in 4-bit on a 24 GB GPU for a pilot class, if the load test on
the real server confirms the number of parallel requests. Keep the 9B as the fallback where only smaller GPUs
are available.
