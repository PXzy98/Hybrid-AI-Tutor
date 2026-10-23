# E6: privacy filter evaluation

Does the privacy filter find the personal information in student questions, without hiding course terms, and
which upgrade is worth it? All data is fictional.

| File | What |
|---|---|
| `make_question_bank.py` → `question_bank.json` | 62 PII-free carrier questions written by qwen, reviewed by hand |
| `make_cases.py` → `cases.jsonl` | main set, 404 cases: 208 positive, 112 negative, 30 hard, 15 French, 21 multi-turn, 18 out-of-scope; templates + question bank |
| `make_holdout.py` → `holdout_raw.jsonl`, `holdout2_raw.jsonl` | held-out texts written by gemma4 (different model, no templates) |
| `holdout.jsonl`, `holdout2.jsonl` | the same texts labelled by hand; v1 = dev, v2 = test (written after the rules were frozen); see `holdout_review.md` |
| `run.py` | all configurations, metrics with Wilson intervals, ablation, misses → `results/<set>/report.md`, `metrics.json`, `predictions.jsonl`, SVG charts |
| `exposure.py` | what would actually reach the cloud per configuration and set → `results/exposure.md` |
| `generalize_eval.py` | the hypothetical rewrite (`privacy.health_detail_policy: generalize`) with the real local model, on every personal-health question of the main set and held-out v2: how many pass, identifiers left → `results/generalize.md` |
| `utility.py` | answer quality after redaction (placeholders, surrogates, hypothetical rewrite), judged by a second model → `results/utility.md` |
| `spot_check.md` | 50 random labels of the main set checked |

```
.venv\Scripts\python eval\privacy-filter\run.py                       # main set, all configurations (~10 min with Ollama)
.venv\Scripts\python eval\privacy-filter\run.py --fast                # rules only, ~1 min
.venv\Scripts\python eval\privacy-filter\run.py --cases eval\privacy-filter\holdout2.jsonl --out eval\privacy-filter\results\holdout_test
.venv\Scripts\python eval\privacy-filter\exposure.py
.venv\Scripts\python eval\privacy-filter\utility.py                   # ~30 min, local model + judge
.venv\Scripts\python eval\privacy-audit\run.py --e6                   # end to end through the API (E4 harness)
```

Configurations: `presidio_default` (benchmark), `ours_sm`, `ours_lg`, `app_mvp` (MVP recognizers + identity
terms), `a5_rules` (all recognizers, now the app configuration), `a2_trf` (spaCy transformer), `a3_gliner_only`,
`a3_rules_gliner`, `a4_rules_llm` (rules + local qwen second pass on the sanitized text). The extra libraries for
A2/A3 (torch, gliner, spacy-transformers, protobuf, `en_core_web_trf`) are evaluation-only and not project
dependencies.

**Read the main-set numbers as optimistic**: the rules were developed on that set. The held-out test set
(`results/holdout_test/`) is the honest estimate.
