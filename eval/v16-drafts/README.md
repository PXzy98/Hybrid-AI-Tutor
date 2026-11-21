# V16: instructor AI draft quality before and after

Five drafts per kind with the code before #119 (`a64ebb2`, the parent of `9d7d35d`) and with main, the same
inputs for both, drafted in-process by the lab vLLM (Qwen3.5-9B), scored with one rubric. A side run compares
the local and the cloud model on a short fictional module (V16's cloud option). Results and conclusion:
[results/report.md](results/report.md).

## Run

Unpack the open course packs once (`python scripts/fetch_open_courses.py unpack`) and put `VLLM_BASE_URL`
(and, for the cloud run, `CLOUD_BASE_URL`, `CLOUD_API_KEY`, `CLOUD_MODEL`) in your own `.env`. From the
repository root:

```
git worktree add --detach ../pact-before 9d7d35d^                      # the "before" code
python eval/v16-drafts/prepare_inputs.py                                # results/inputs.json (no model call)
python eval/v16-drafts/run_drafts.py --backend backend --label after
python eval/v16-drafts/run_drafts.py --backend ../pact-before/backend --label before
python eval/v16-drafts/run_drafts.py --backend backend --label cloud --cloud
python eval/v16-drafts/score.py --blind blind.txt                       # scoring sheet without versions
python eval/v16-drafts/score.py                                         # the tables, from results/scores.json
```

In a worktree without its own `.env` or unpacked packs, pass `--env-file <main checkout>/.env` and
`--packs <main checkout>/data/demo_courses`.

`run_drafts.py` imports the `app` package of the `--backend` it is given, so each version drafts with its own
prompts, validators and KC checks. It calls the draft cores the job `ai_draft.generate` calls (and, for quiz
questions, the request and parser of `quiz.draft`) through `FakeGateway` around the app's own vLLM client;
there is no database, retriever or job queue in the loop. 35 local calls per version (7 kinds x 5 modules),
12 for the cloud run (6 kinds x local and cloud), at most 4 at a time.

## Files

- `prepare_inputs.py`: stages and indexes three packs (`harvard_cs50x`, `mit_6_002_circuits`,
  `mit_hst151_pharmacology`; never `instructor_only/`) and retrieves the passages of five modules per kind as
  the draft jobs do; adds three existing KCs per module.
- `run_drafts.py`: drafts every kind of every module with one version; `--cloud` drafts the fictional module
  with both models (only fictional text goes to the cloud model, and through the app's cloud gate).
- `score.py`: blind scoring sheet, automatic checks, the report's tables.
- `results/inputs.json`, `results/drafts_*.jsonl` (every draft and the model's raw answer),
  `results/scores.json` (the reviewer's scores with reasons), `results/report.md`.

**License.** `inputs.json` and the drafts of the course packs contain or are derived from MIT OpenCourseWare
and Harvard CS50x material, CC BY-NC-SA 4.0 (non-commercial, credit the source, share alike; see each pack's
`README.md` in `data/demo_courses/`). The fictional module is written for this test.
