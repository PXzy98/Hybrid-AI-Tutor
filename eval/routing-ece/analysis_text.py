"""Hand-written analysis appended to results/report.md by run.py (written from the run of 2026-11-13)."""
# ruff: noqa: E501  (Markdown text)

ANALYSIS = """## Analysis

Written by hand from the run above; rerun before quoting numbers. Sample sizes are small (143 scored rows,
27 of them "hard"), the labels are the policy labels of the seed rule written by one author, and the evidence
step is not simulated, so read these as a first estimate.

**Acceptance criterion "engineering questions are not all sent to the cloud": met, but the cloud share is far
above the label.** With the shipped routers 48% (LR) and 50% (SVM) of the scored questions go to the cloud
(per pack 33% to 58%), against 19% labelled cloud. Of the 116 questions labelled local, 49 (LR) or 50 (SVM) are
sent to the cloud; 6 to 8 of the 27 hard ones are routed local.

**Cause: the out-of-distribution gate, not the classifier.** 46% of the rows are outside the training support
(nearest training question below similarity 0.25; the seed has only medical questions), and they are all sent
to the cloud. The cloud head alone (probability >= 0.5, no gate) reaches accuracy 0.84 (LR) and 0.85 (SVM)
against 0.60 and 0.61 with the gate. The gate hits application questions hardest (72% unreliable, accuracy 0.25
and 0.22, short numeric or code questions such as "how do I swap two integers using pointers"), then concept
questions (36%), while logistics questions are mostly inside the support (11% unreliable, accuracy 0.89).
CS50x and 6.006 (58% unreliable) are further from the medical seed than circuits and signals (31 to 34%).

**Hard questions:** cloud recall 0.70 (LR) and 0.78 (SVM) with the gate; the signals pack is worst (0.29 and
0.43): long derivation questions in signals vocabulary are inside the support but scored below the 0.52 cut.

**Evidence head:** 0.90 accuracy overall but only 0.61 on logistics questions: about 40% of "when is homework 4
due"-type questions are not flagged as needing the course material, so they would be answered without it.

**Retraining (in memory).** Adding the training share of the new data (92 rows, split by pack and type) to the
seed training split lifts held-out accuracy on the new rows from 0.55 to 0.86 (LR) and 0.55 to 0.84 (SVM), cuts
the cloud share on them from 0.52 to 0.17, and leaves the seed hold-out unchanged (0.96 and 0.96 to 0.97).
Leave-one-pack-out (training on the other three packs) gives 0.69 to 0.89 accuracy; CS50x is the weakest
(cloud recall 0.14: its hard questions look like its application questions), so a new course type should bring
its own questions before it is trusted. The candidate weights (seed + all scored new rows, 495 rows) are in
`results/candidate/`; they are better on both evaluation sets, but the shipped files in `data/routing/models/`
were **not** replaced in this change. To adopt them: `python eval/routing-ece/run.py --write-training-file`,
then from `backend/`: `python -m app.routing.train --data ../data/routing/seed_plus_ece_cs.jsonl`, and rerun
`python -m pytest -q tests/test_semantic_routing.py`.

**Caveats.** The labels are intended policy, not measured local-model ability: whether a local model really
fails the "hard" questions is not tested. The 17 uncertain rows (all current-information rows and nine borderline
derivations) are excluded. A better fix than retraining alone may be to relax the unreliability gate for
engineering courses (it is a route to the cloud, so it also decides what leaves the machine).
"""
