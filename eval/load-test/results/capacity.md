# vLLM capacity (Z23): Qwen3.5-9B

Streaming, max_tokens 400, thinking off, 3 waves per level, fictional course questions, straight to the server (no app queue).

| At the same time | OK / sent | Errors | Latency p50 (s) | p95 (s) | First token p50 / p95 (s) | Tokens per answer | Tokens/s per request | Total tokens/s |
|---|---|---|---|---|---|---|---|---|
| 1 | 3 / 3 | 0 | 3.14 | 3.15 | 0.06 / 0.06 | 132.00 | 43.47 | 43.47 |
| 4 | 12 / 12 | 0 | 9.42 | 9.43 | 0.08 / 0.09 | 333.67 | 42.37 | 141.65 |
| 8 | 24 / 24 | 0 | 9.77 | 9.77 | 0.12 / 0.13 | 358.08 | 40.87 | 293.23 |
| 16 | 48 / 48 | 0 | 10.65 | 13.70 | 0.17 / 3.69 | 362.60 | 36.84 | 422.60 |
| 32 | 96 / 96 | 0 | 14.20 | 21.39 | 3.77 / 10.93 | 360.42 | 27.56 | 475.55 |
