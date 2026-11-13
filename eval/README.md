# Evaluation

Design: `docs/System_Design_v3.md` §11 (pre-registered targets and decision rules). Run everything from the
repository root with the project venv. Every harness has a **smoke mode** (fake models, tiny N) that CI runs on
each push, and a **full mode** against the real servers, run on request.

| Folder | Question (design §11) | Full run | Smoke (CI) | Report |
|---|---|---|---|---|
| `model-boundary-test/` | Local model capability boundary (chose `qwen3.5:9b`, thinking off) | — | — | done, Oct 6 2026 |
| `understand-tagging/` | **E1** Can the local model tag questions? | `run.py [--model M] [--repeat N]` | — | `results/report.md` |
| `learner-sim/` | **E2** Does BKT beat the rule method? | `run.py` (~3 min, no LLM) | `run.py --smoke` | `results/report.md` + SVG charts |
| `personalization/` | **E3** Does personalization fit better without losing accuracy? | `run.py` (~40 min with local models) | `run.py --smoke` | `results/report.md`, `abbas_sample.csv` |
| `privacy-filter/` | **E6** Does the privacy filter find the PII in student questions? Benchmark vs Presidio, upgrades (trf, GLiNER, local LLM), ablation, held-out sets, answer quality after redaction | `run.py` (~10 min with Ollama; `--fast` ~1 min), `exposure.py`, `utility.py`; see its README | `run.py --smoke` | `results/report.md`, `results/holdout_test/report.md`, `results/exposure.md`, `results/utility.md` |
| `privacy-audit/` | **E4** Does any profile or identity data reach the cloud? `--e6`: the E6 questions end to end, incl. "no personal health question reaches the cloud" | `run.py`, `run.py --e6` | `run.py --smoke` (exit 1 on any leak) | `results/report.md`, `results/e6/report.md` |
| `routing-ece/` | **T4** How do the shipped routers (lr, svm) route questions of the ECE and computer science packs? Labelled questions in `data/routing/ece_cs_questions.jsonl`; accuracy, confusion, cloud share per pack and type; in-memory retraining experiment | `run.py` (~1 min, no model, no network; local encoder) | - | `results/report.md`, `results/metrics.json`, `results/candidate/` |
| `course-rag-packs/` | **S11** Does the course index find the right file for student questions on the open course packs (medical science, life science, ECE, computer science)? | `run.py` (~5 min for eight packs, no model, no network; needs the unpacked packs) | `run.py --smoke` (~6 min, not in CI: needs the packs) | `results/report.md`, `results/metrics.json` |

```powershell
.venv\Scripts\python eval\understand-tagging\run.py --repeat 2
.venv\Scripts\python eval\learner-sim\run.py
.venv\Scripts\python eval\privacy-audit\run.py
.venv\Scripts\python eval\personalization\run.py
```

Every harness takes `--out <folder>` (default: its own `results/`). The full runs of E1, E3 and E4 need the Ollama
server (`OLLAMA_URL` in `.env`); E2 needs nothing.

## E2 — `learner-sim/`

Simulated students with a hidden true mastery go through the **real** learner model, recommender and item
selection (`sim.py` explains the student model: learning in [0.05, 0.20], forgetting 0.02 per step, slip/guess
drawn away from the BKT defaults). Configurations: bkt and rule, each with weak evidence off and on, plus a
one-at-a-time sweep of the BKT parameters. Weak signals are mis-tagged at the E1 error rate (read from the E1
report; `--noise` overrides). Metrics: MAE against the true mastery, next-answer AUC (with the oracle AUC as the
ceiling), level-band accuracy. The report applies the decision rule and prints the recommended
`learner.knowledge`. Options: `--students`, `--interactions`, `--seed`, `--no-sweep`.

## E3 — `personalization/`

Four personas (novice; intermediate with a misconception; advanced; mixed prerequisites, defined in
`common/harness.py`) are created as real student accounts through `admin/students`, onboarded and given scripted
check answers. Each asks the 20 questions in `questions.jsonl` twice: personalization on, and off
(`learner.personalize: false`). A blind pairwise judge compares the two answers in random A/B order.

- Judge: any OpenAI-compatible API. Set `JUDGE_BASE_URL`, `JUDGE_MODEL`, `JUDGE_API_KEY`; the default is the
  Ollama server's OpenAI endpoint (`<OLLAMA_URL>/v1`) with `gemma4:e4b`, a different model from the one that
  writes the answers. The judge only sees fictional personas.
- `abbas_sample.csv`: 30 blind pairs for Dr. Abbas, with empty rating columns. `abbas_key.csv` says which side
  was personalized; keep it away from the rater.
- Options: `--questions N`, `--personas novice,advanced`, `--judge-model`, `--seed`.

## S11 — `course-rag-packs/`

Run `python scripts/fetch_open_courses.py unpack` first. Each pack of `questions/*.jsonl` (about 30 questions
written from the pack material: concept, application, logistics, and 3 whose answer is not in the material,
`gold: []`) is staged with `stage_demo_course` and indexed by `IndexedCourseRetriever` behind the privacy scan of
its course type; a file the scan refuses is skipped and listed. Each question is retrieved with k=4 scoped to its
module and course-wide; the report gives hit@1, hit@4 and MRR per type and course, the top score of the
unanswerable questions, the misses and a short analysis (`analysis_text.py`). Question fields: `id`, `question`,
`type`, `module_order` (null for course-level questions), `gold` (pack-relative files; never `instructor_only/`),
`evidence` (patterns that must occur in a gold file; `run.py --check` verifies them). Options: `--packs a,b`,
`--k`, `--out`, `--smoke` (3 questions per course; exit 1 if hit@4 is below 0.5).

## E4 — `privacy-audit/`

All personas ask the E3 questions, the E1 cases and questions with planted PII (`pii_questions.jsonl`: own name
and username, student numbers, e-mail, phone, other people's names, a grade, a health detail). Every question is
forced to the cloud route. The recording cloud client is installed through config
(`LLM__CLOUD__AUDIT_LOG=<file>`; `LLM__CLOUD__AUDIT_ECHO=true` answers locally so nothing leaves the machine;
`--real-cloud` uses the configured provider instead). The audit checks every captured request for fields outside
the allow-list, identity (usernames, display names), profile data (student IDs, item and misconception IDs,
misconception texts) and typed PII, and checks the database (outside `account`) and the logs for identity and raw
typed PII. **Any leak gives exit code 1**, so the run can gate CI or a release.

The same switches work on a normal server, for an audit of a manual session:

```powershell
$env:LLM__CLOUD__AUDIT_LOG = "eval\privacy-audit\results\manual.jsonl"; $env:LLM__CLOUD__AUDIT_ECHO = "true"
```
