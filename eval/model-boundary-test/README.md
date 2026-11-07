# model-boundary-test

Tests the capability boundary of small local models: which types and difficulty levels of questions models of
different sizes can still answer correctly. The full plan is in **TEST_PLAN.md**.

## Quick start

```bash
# On the server 192.168.2.25 (needs OLLAMA_HOST=0.0.0.0:11434)
bash pull_models.sh            # Windows server: .\pull_models.ps1

# On your own computer
pip install -r requirements.txt
python bench.py --models qwen3.5:4b --limit 5 --out results/smoke.jsonl     # smoke test
python bench.py --models qwen3.5:2b qwen3.5:4b qwen3.5:9b gemma4:e4b gemma4:12b gemma4:26b qwen3.5:27b
python bench.py --models qwen3.5:4b qwen3.5:9b qwen3.5:27b --think on       # thinking comparison
python grade.py              # automatic grading; open questions go to results/manual_review.csv, fill in 1/0 by hand and run again
python report.py             # writes results/report.md and results/boundary_heatmap.png
```

- Change the server address with `--host` or the environment variable `OLLAMA_URL`.
- After an interruption just run again; finished questions are skipped.
- Open questions can also be graded by a judge model: `python grade.py --judge-model gpt-4o` (needs
  `OPENAI_API_KEY`), or a local model: `--judge-model qwen3.5:27b --base-url http://192.168.2.25:11434/v1`.

## Files

| File | Purpose |
|---|---|
| `data/boundary_set.jsonl` | 110 test questions (5 dimensions × 4 levels × 5 questions, plus 10 Chinese/English paired questions) |
| `data/boundary_set_review.csv` | The same questions as a table, for team members to check |
| `bench.py` | Asks Ollama, records answers, latency, tok/s and GPU use |
| `grade.py` | Automatic grading (multiple choice, numeric, short answer, format rules) + grading of open questions |
| `report.py` | Builds the boundary table, heat map, Chinese/English comparison and the list of wrong answers |
| `pull_models.sh` / `.ps1` | Pulls the models; the argument `all` also pulls the optional models |
