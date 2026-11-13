# Routing evaluation on ECE and computer science questions (T4)

160 questions written from the packs `mit_6_002_circuits`, `mit_res_6_007_signals`, `mit_6_006_algorithms`, `harvard_cs50x` (40 each; kinds: concept, application, hard, logistics, current) and labelled with the seed labelling rule. 17 rows are `uncertain` (the label depends on a model judgement: all current-information rows and a few borderline derivations) and are excluded from the figures: 143 rows are scored. Labels are intended policy (`prototype_policy`), not measured local-model ability. *Route* is the capability gate of `SemanticRouter` (cloud when the question is outside the training support or cloud_probability >= 0.52), *accuracy* compares it with the label (cloud iff `cloud_required`); the evidence step (course index plus cross-encoders) is not simulated.

## Shipped LR router

**All scored rows**

| Group | n | accuracy | cloud share | label cloud share | cloud recall | local recall | unreliable | evidence head acc |
|---|---|---|---|---|---|---|---|---|
| all | 143 | 0.60 | 0.48 | 0.19 | 0.70 | 0.58 | 0.46 | 0.90 |

**Per pack**

| Group | n | accuracy | cloud share | label cloud share | cloud recall | local recall | unreliable | evidence head acc |
|---|---|---|---|---|---|---|---|---|
| harvard_cs50x | 36 | 0.61 | 0.58 | 0.19 | 1.00 | 0.52 | 0.58 | 0.94 |
| mit_6_002_circuits | 35 | 0.66 | 0.40 | 0.17 | 0.67 | 0.66 | 0.34 | 0.80 |
| mit_6_006_algorithms | 36 | 0.56 | 0.58 | 0.19 | 0.86 | 0.48 | 0.58 | 0.92 |
| mit_res_6_007_signals | 36 | 0.58 | 0.33 | 0.19 | 0.29 | 0.66 | 0.31 | 0.92 |

**Per type**

| Group | n | accuracy | cloud share | label cloud share | cloud recall | local recall | unreliable | evidence head acc |
|---|---|---|---|---|---|---|---|---|
| application | 36 | 0.25 | 0.75 | 0.00 | - | 0.25 | 0.72 | 0.92 |
| concept | 52 | 0.64 | 0.36 | 0.00 | - | 0.64 | 0.36 | 1.00 |
| hard | 27 | 0.70 | 0.70 | 1.00 | 0.70 | - | 0.63 | 0.96 |
| logistics | 28 | 0.89 | 0.11 | 0.00 | - | 0.89 | 0.11 | 0.61 |

Confusion (label -> route): local->local 67, local->cloud 49, cloud->local 8, cloud->cloud 19. Head only (no unreliability gate, cloud_probability >= 0.5): accuracy 0.84.

## Shipped SVM router

**All scored rows**

| Group | n | accuracy | cloud share | label cloud share | cloud recall | local recall | unreliable | evidence head acc |
|---|---|---|---|---|---|---|---|---|
| all | 143 | 0.61 | 0.50 | 0.19 | 0.78 | 0.57 | 0.46 | 0.90 |

**Per pack**

| Group | n | accuracy | cloud share | label cloud share | cloud recall | local recall | unreliable | evidence head acc |
|---|---|---|---|---|---|---|---|---|
| harvard_cs50x | 36 | 0.61 | 0.58 | 0.19 | 1.00 | 0.52 | 0.58 | 0.94 |
| mit_6_002_circuits | 35 | 0.66 | 0.46 | 0.17 | 0.83 | 0.62 | 0.34 | 0.80 |
| mit_6_006_algorithms | 36 | 0.56 | 0.58 | 0.19 | 0.86 | 0.48 | 0.58 | 0.89 |
| mit_res_6_007_signals | 36 | 0.61 | 0.36 | 0.19 | 0.43 | 0.66 | 0.31 | 0.94 |

**Per type**

| Group | n | accuracy | cloud share | label cloud share | cloud recall | local recall | unreliable | evidence head acc |
|---|---|---|---|---|---|---|---|---|
| application | 36 | 0.22 | 0.78 | 0.00 | - | 0.22 | 0.72 | 0.92 |
| concept | 52 | 0.64 | 0.36 | 0.00 | - | 0.64 | 0.36 | 1.00 |
| hard | 27 | 0.78 | 0.78 | 1.00 | 0.78 | - | 0.63 | 0.96 |
| logistics | 28 | 0.89 | 0.11 | 0.00 | - | 0.89 | 0.11 | 0.61 |

Confusion (label -> route): local->local 66, local->cloud 50, cloud->local 6, cloud->cloud 21. Head only (no unreliability gate, cloud_probability >= 0.5): accuracy 0.85.

## Retraining experiment (in memory)

Seed training split (403 rows) alone versus plus the training share of the new data (92 rows); evaluated on the held-out new rows (58 scored) and on the seed hold-out of the training script (97 rows). Shipped files are not touched.

**LR**

| Training data | new held-out accuracy | new cloud share | new local recall | new cloud recall | seed held-out accuracy | seed cloud share |
|---|---|---|---|---|---|---|
| seed only | 0.55 | 0.52 | 0.52 | 0.70 | 0.96 | 0.27 |
| seed + new | 0.86 | 0.17 | 0.92 | 0.60 | 0.96 | 0.27 |

Leave-one-pack-out (seed train + the other three packs, tested on the fourth):

| Held-out pack | accuracy | cloud share | local recall | cloud recall |
|---|---|---|---|---|
| harvard_cs50x | 0.69 | 0.17 | 0.83 | 0.14 |
| mit_6_002_circuits | 0.86 | 0.31 | 0.83 | 1.00 |
| mit_6_006_algorithms | 0.86 | 0.28 | 0.86 | 0.86 |
| mit_res_6_007_signals | 0.83 | 0.25 | 0.86 | 0.71 |

**SVM**

| Training data | new held-out accuracy | new cloud share | new local recall | new cloud recall | seed held-out accuracy | seed cloud share |
|---|---|---|---|---|---|---|
| seed only | 0.55 | 0.55 | 0.50 | 0.80 | 0.96 | 0.27 |
| seed + new | 0.84 | 0.19 | 0.90 | 0.60 | 0.97 | 0.26 |

Leave-one-pack-out (seed train + the other three packs, tested on the fourth):

| Held-out pack | accuracy | cloud share | local recall | cloud recall |
|---|---|---|---|---|
| harvard_cs50x | 0.69 | 0.17 | 0.83 | 0.14 |
| mit_6_002_circuits | 0.89 | 0.29 | 0.86 | 1.00 |
| mit_6_006_algorithms | 0.86 | 0.28 | 0.86 | 0.86 |
| mit_res_6_007_signals | 0.83 | 0.25 | 0.86 | 0.71 |

## Uncertain rows (not scored)

- `circ-026`
- `circ-027`
- `circ-031`
- `circ-039`
- `circ-040`
- `sig-027`
- `sig-029`
- `sig-039`
- `sig-040`
- `alg-028`
- `alg-031`
- `alg-039`
- `alg-040`
- `cs50-026`
- `cs50-031`
- `cs50-039`
- `cs50-040`


## Analysis

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

