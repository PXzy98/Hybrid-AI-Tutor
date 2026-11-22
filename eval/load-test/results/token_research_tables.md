The last column counts calls above 1024 tokens (for the tier 2 drafts: above 2048).

| Kind | Calls | Median | p95 | Max | Limit | Cut at limit | Cut and looping | Over 1024 |
|---|---|---|---|---|---|---|---|---|
| answers, S11 | 64 | 303 | 912 | 1156 | 2048 | 0 / 64 | 0 | 2 / 64 |
| answers, paraphrase | 20 | 218 | 695 | 726 | 2048 | 0 / 20 | 0 | 0 / 20 |
| answers, all plain | 84 | 300 | 868 | 1156 | 2048 | 0 / 84 | 0 | 2 / 84 |
| answers, asked for detail and a table | 64 | 1065 | 1950 | 2048 | 2048 | 1 / 64 | 0 | 35 / 64 |
| understand | 84 | 26 | 39 | 48 | 200 | 0 / 84 | 0 | - |
| draft: kcs | 15 | 320 | 535 | 640 | 4096 | 0 / 15 | 0 | 0 / 15 |
| draft: check_items | 15 | 1163 | 1460 | 1545 | 4096 | 0 / 15 | 0 | 0 / 15 |
| draft: misconceptions | 15 | 521 | 816 | 817 | 4096 | 0 / 15 | 0 | 0 / 15 |
| quiz draft, 5 questions | 15 | 760 | 816 | 829 | 2048 | 0 / 15 | 0 | 0 / 15 |
| quiz draft, 12 questions | 6 | 1702 | 1801 | 1801 | 2048 | 0 / 6 | 0 | 6 / 6 |

Cut-offs and the same request with a limit of 4096:

| Call | Tokens | Loop flag | At 4096: tokens | At 4096: still cut |
|---|---|---|---|---|
| alg-06-d-r3 | 2048 | False | 1936 | False |

| Length | At once | OK / sent | Call p50 (s) | Slowest (s) | First token p50 (s) | Tokens/s per call | Total tokens/s |
|---|---|---|---|---|---|---|---|
| 300 | 1 | 3 / 3 | 7.0 | 7.0 | 0.2 | 43.9 | 42.9 |
| 300 | 8 | 16 / 16 | 8.6 | 8.7 | 0.8 | 38.4 | 277.3 |
| 300 | 16 | 32 / 32 | 9.9 | 17.9 | 1.3 | 35.3 | 271.2 |
| 900 | 1 | 3 / 3 | 20.8 | 20.8 | 0.2 | 43.7 | 43.4 |
| 900 | 8 | 16 / 16 | 23.5 | 23.7 | 0.8 | 39.5 | 305.2 |
| 900 | 16 | 32 / 32 | 27.1 | 48.7 | 1.4 | 36.0 | 296.6 |
| 2048 | 1 | 3 / 3 | 47.1 | 47.1 | 0.2 | 43.7 | 43.5 |
| 2048 | 8 | 16 / 16 | 53.1 | 71.2 | 0.8 | 37.7 | 232.9 |
| 2048 | 16 | 32 / 32 | 80.8 | 127.2 | 1.3 | 34.0 | 271.6 |

| Limit | Calls | Finish: length | Completion median | Reasoning median | Reasoning max |
|---|---|---|---|---|---|
| 600 | 8 | 0 | 229 | 81 | 195 |
| 2000 | 8 | 0 | 214 | 90 | 223 |
