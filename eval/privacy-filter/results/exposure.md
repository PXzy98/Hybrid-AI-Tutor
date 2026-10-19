# E6: cloud exposure per configuration

Share of labelled questions (positive, hard, French, multi-turn) that the filter would send to the cloud with PII still in them. *Any PII*: any unprotected entity; *identifier*: a name, student number, e-mail, phone or other ID; *health*: the question states a personal health detail but is not kept local.

## main set (development, 404)

| Configuration | Questions | Sent to cloud | Exposed: any PII | identifier | personal health |
|---|---|---|---|---|---|
| presidio_default | 274 | 274 | 57.3% | 27.0% | 22.3% |
| ours_sm | 274 | 225 | 14.6% | 8.8% | 4.4% |
| ours_lg | 274 | 225 | 9.9% | 4.0% | 4.4% |
| app_mvp | 274 | 225 | 8.0% | 2.2% | 4.4% |
| a5_rules | 274 | 218 | 5.1% | 2.2% | 1.8% |
| a2_trf | 274 | 225 | 8.4% | 2.6% | 4.4% |
| a3_gliner_only | 274 | 210 | 24.1% | 5.8% | 9.9% |
| a3_rules_gliner | 274 | 186 | 2.2% | 1.1% | 1.1% |
| a4_rules_llm | 274 | 214 | 1.8% | 0.4% | 1.1% |

## held-out v1 (dev, 102)

| Configuration | Questions | Sent to cloud | Exposed: any PII | identifier | personal health |
|---|---|---|---|---|---|
| presidio_default | 89 | 89 | 91.0% | 59.6% | 69.7% |
| ours_sm | 89 | 54 | 37.1% | 7.9% | 30.3% |
| ours_lg | 89 | 54 | 33.7% | 3.4% | 30.3% |
| app_mvp | 89 | 54 | 33.7% | 3.4% | 30.3% |
| a5_rules | 89 | 33 | 10.1% | 2.2% | 6.7% |
| a2_trf | 89 | 54 | 31.5% | 1.1% | 30.3% |
| a3_gliner_only | 89 | 57 | 40.4% | 4.5% | 40.4% |
| a3_rules_gliner | 89 | 23 | 1.1% | 0.0% | 2.2% |
| a4_rules_llm | 89 | 29 | 6.7% | 1.1% | 4.5% |

## held-out v2 (test, 102)

| Configuration | Questions | Sent to cloud | Exposed: any PII | identifier | personal health |
|---|---|---|---|---|---|
| presidio_default | 93 | 93 | 92.5% | 54.8% | 86.0% |
| ours_sm | 93 | 58 | 48.4% | 7.5% | 48.4% |
| ours_lg | 93 | 58 | 48.4% | 3.2% | 48.4% |
| app_mvp | 93 | 58 | 48.4% | 3.2% | 48.4% |
| a5_rules | 93 | 33 | 21.5% | 1.1% | 21.5% |
| a2_trf | 93 | 58 | 48.4% | 1.1% | 48.4% |
| a3_gliner_only | 93 | 54 | 48.4% | 5.4% | 51.6% |
| a3_rules_gliner | 93 | 25 | 17.2% | 0.0% | 20.4% |
| a4_rules_llm | 93 | 23 | 11.8% | 0.0% | 12.9% |
