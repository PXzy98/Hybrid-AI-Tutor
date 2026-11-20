# Routing test with the lab vLLM (asked by Prof. Ismaeel), 2026-11-20

Settings: `config.yaml` as merged (semantic router, default method lr, threshold 0.6, uncertainty margin 0.08,
so a question goes to the cloud when cloud probability >= 0.52, when it is outside the training support
(similarity < 0.25) or when the evidence step finds the passages insufficient). Local model: Qwen3.5-9B on the
lab vLLM; cloud model: the one in the developer `.env`. Only public course questions were used.

## 1. Routing evaluation (`run.py`, no model)

Re-run today; the numbers are identical to `report.md` (the evaluation does not depend on the model server).

| Router | Rows scored | Accuracy vs. policy label | Cloud share | Label cloud share | Cloud recall | Local recall | Outside support | Evidence head acc. |
|---|---|---|---|---|---|---|---|---|
| Shipped LR, ECE and CS packs | 143 | 0.60 | 0.48 | 0.19 | 0.70 | 0.58 | 0.46 | 0.90 |
| Shipped SVM, ECE and CS packs | 143 | 0.61 | 0.50 | 0.19 | 0.78 | 0.57 | 0.46 | 0.90 |
| Seed (medical) hold-out, seed-only training | 97 | 0.96 | 0.27 | - | - | - | - | - |
| ECE and CS held-out rows, seed + new rows (experiment, not shipped) | 58 | 0.86 | 0.17 | - | 0.60 | 0.92 | - | - |

The medical set is the seed hold-out of the same harness (`data/routing/seed.jsonl`); there is no separate
runnable medical routing harness. The router is accurate on medical questions and sends about half of the
ECE and CS questions to the cloud, mostly because they are outside the medical training support (see
`report.md`); retraining with the new rows is the open improvement (candidate weights in `candidate/`).

## 2. Manual check with the local model (`manual_check.py`)

The router decides (with the evidence step on passages from the unpacked pack, inside the course's scope as in
the app), and a question routed locally is answered by the lab vLLM. A question routed to the cloud is recorded
but not sent: the pack passages are real (public) course material, and rule 6 allows only fictional data on
hosted models (`--call-cloud` exists for when the project allows it). A first run on 2026-11-20 did send the three
cloud-routed public questions with their pack passages to the cloud model; that is no longer the default.

| Question | Route | Cloud prob. | In support | Evidence | Answered by | Answer time (s) |
|---|---|---|---|---|---|---|
| what is pseudocode and why write it before real code? (CS50x) | local | 0.01 | yes | sufficient | Qwen3.5-9B | 9.3 |
| which cs50 helper functions can I use to read an int or a float? (CS50x) | local | 0.00 | yes | not required | Qwen3.5-9B | 6.4 |
| what does the sum of the voltages around a loop have to equal? (6.002) | local | 0.02 | yes | not required | Qwen3.5-9B | 3.7 |
| Prove that the average running time of quicksort is O(n log n) with a full recurrence analysis ... (CS50x) | cloud | 0.09 | no | unavailable | not sent | - |
| when can I treat a circuit as a lumped circuit ...? (6.002) | cloud | 0.89 | no | unavailable | not sent | - |
| What changed in the most recent standard for USB power delivery this year? (6.002) | cloud | 0.02 | yes | insufficient | not sent | - |

The local path works (4 to 9 s per answer); a hard derivation and a question outside the material are routed to
the cloud. Two observations: the lumped-circuit question is a basic concept question but goes to the cloud
(outside the training support, a known effect of the medical-only seed); and the USB question goes to the cloud
because the evidence step finds the course passages insufficient, which is the intended behaviour for a question
outside the material. Details: `manual_check.json`.
