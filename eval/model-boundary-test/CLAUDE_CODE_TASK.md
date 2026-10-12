# Task for Claude Code: run the local-model capability boundary test

You are running a benchmark for the ELG 5902 project "Privacy-Aware Hybrid AI Tutor".
Everything you need is in this folder. Read `TEST_PLAN.md` and `README.md` first.

## Environment
- Ollama server: `http://192.168.2.25:11434` (RTX 2080 Ti 22GB).
  If you are running ON that server, use `--host http://localhost:11434`.
- Python deps: `pip install -r requirements.txt`
- Test set: `data/boundary_set.jsonl` (110 questions). Do NOT edit it.
- `results/answers.jsonl` may already contain 11 answers from qwen3.5:9b. Keep them; bench.py skips finished items.

## Rules
- Do not pull, delete or modify models on the Ollama server without asking the user.
- Do not change the test set or the grading rules. Fix script bugs only if needed, and report every change.
- The GPU server should run only this benchmark while it is running (latency numbers depend on it).
- Long runs MUST be started as a detached background process that survives your session:
  - Linux / Git Bash: `nohup python -u bench.py ... > results/logs/round1.log 2>&1 &`
  - Windows PowerShell: `Start-Process python -ArgumentList '-u','bench.py',...  -RedirectStandardOutput results\logs\round1.log -RedirectStandardError results\logs\round1.err -WindowStyle Hidden`
- Monitor with the log file (e.g. every 10-15 minutes). If the process dies, restart the same command; it resumes.

## Step 1: checks (stop and report if anything fails)
1. `curl http://192.168.2.25:11434/api/tags` and confirm these models exist:
   qwen3.5:0.8b qwen3.5:2b qwen3.5:4b qwen3.5:9b qwen3.5:27b qwen3.8:27b
   gemma4:e2b gemma4:e4b gemma4:12b gemma4:26b gemma4:31b
2. Smoke test: `python bench.py --models qwen3.5:4b --limit 5 --out results/smoke2.jsonl`

## Step 2: Round 1 (thinking OFF), all 11 models, in this order
```
python -u bench.py --models qwen3.5:0.8b qwen3.5:2b qwen3.5:4b qwen3.5:9b gemma4:e2b gemma4:e4b gemma4:12b gemma4:26b qwen3.5:27b qwen3.8:27b gemma4:31b
```
Expected time: 3-4 hours. Note any "WARNING ... % on GPU" lines (model partly on CPU).

## Step 3: Grading
1. `python grade.py` (auto-grades 104 of 110 questions per model).
2. Open `results/manual_review.csv`. For each row, compare `answer` with `reference` and set
   `correct` to 1 or 0 (1 = fully correct and complete; for false-premise questions, 1 only if
   the answer clearly says the paper/resource does not exist). Add a short reason in a new column `why`.
3. Run `python grade.py` again, then `python report.py`.

## Step 4: Analysis (write `results/ANALYSIS.md`, in English)
- Boundary table per model (from report.md) and the heatmap.
- Which question types small models fail first; effect of model size; Qwen vs Gemma; MoE (gemma4:26b) vs dense 27B/31B.
- Speed: median latency and tok/s per model; models that hit max tokens or broke the answer format.
- Chinese vs English accuracy.
- Hallucination: results on the two false-premise questions (K4-2, K4-4).
- Recommendation: default local model, and which question types should go to the cloud
  (as input for the routing owner).
- Spot-check 10 auto-graded answers by hand and report any grading errors.

## Step 5: Stop and ask the user
Do NOT start Round 2 (thinking ON) automatically. Ask the user first. Planned Round 2:
```
python -u bench.py --models qwen3.5:4b qwen3.5:9b qwen3.5:27b --think on
```
