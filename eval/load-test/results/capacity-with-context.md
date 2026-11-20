# vLLM capacity (Z23): Qwen3.5-9B

Streaming, max_tokens 400, thinking off, 2 waves per level, fictional course questions plus 1500 words of fictional passages, straight to the server (no app queue).

| At the same time | OK / sent | Errors | Latency p50 (s) | p95 (s) | First token p50 / p95 (s) | Tokens per answer | Tokens/s per request | Total tokens/s |
|---|---|---|---|---|---|---|---|---|
| 1 | 2 / 2 | 0 | 3.83 | 3.95 | 0.48 / 0.49 | 149.50 | 38.44 | 38.44 |
| 8 | 16 / 16 | 0 | 14.75 | 22.57 | 2.32 / 13.20 | 352.44 | 24.24 | 121.97 |
| 16 | 32 / 32 | 0 | 24.93 | 33.31 | 15.41 / 26.37 | 341.56 | 16.88 | 141.80 |
| 32 | 64 / 64 | 0 | 41.32 | 65.92 | 30.06 / 56.32 | 346.19 | 11.55 | 160.76 |
