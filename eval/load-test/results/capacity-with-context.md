# vLLM capacity (Z23): Qwen3.5-9B

Streaming, max_tokens 400, thinking off, 2 waves per level, fictional course questions plus 1500 words of fictional passages, straight to the server (no app queue).

| At the same time | OK / sent | Errors | Latency p50 (s) | p95 (s) | First token p50 / p95 (s) | Tokens per answer | Tokens/s per request | Total tokens/s |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 / 2 | 0 | 3.34 | 3.67 | 0.08 / 0.48 | 141.50 | 40.49 | 40.38 |
| 8 | 16 / 16 | 0 | 14.19 | 22.23 | 2.12 / 12.93 | 347.06 | 24.80 | 121.92 |
| 16 | 32 / 32 | 0 | 24.39 | 32.51 | 12.24 / 26.53 | 335.75 | 16.73 | 138.86 |
| 32 | 64 / 64 | 0 | 43.35 | 66.91 | 30.20 / 58.25 | 352.77 | 11.72 | 156.98 |
