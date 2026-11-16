# S8 reference: existing E2 simulated-learner smoke (2026-11-05)

**SMOKE ONLY — 8 fictional students x 8 interactions, five health topics. Not evidence of model superiority or clinical validity.**
This runs the existing v3 BKT-vs-Rule E2 simulation, not the new v4 course ability or persistence implementation.

# E2: BKT vs rule on simulated students (design §11 E2)

8 students × 8 interactions per topic · seed 2026 · weak-signal tagging noise 8% (E1 report (eval\understand-tagging\results\report.md)) · forgetting 0.02/step · student slip ∈ [0.10, 0.25], guess ∈ [0.20, 0.40], learning ∈ [0.05, 0.20] (BKT defaults: slip 0.10, guess 0.25, learn 0.10).

Topics simulated: asthma, high_blood_pressure, migraine, pneumonia, type2_diabetes. Skipped (no complete item bank yet): none.

## asthma

| Config | MAE | Next-answer AUC (oracle) | Band accuracy | Items reused (24 h rule) |
|---|---|---|---|---|
| bkt | 0.163 | 0.620 (0.611) | 66.2% | 22 |
| rule | 0.151 | 0.579 (0.590) | 72.8% | 36 |
| bkt+weak | 0.165 | 0.630 (0.642) | 62.8% | 23 |
| rule+weak | 0.148 | 0.598 (0.641) | 74.1% | 36 |

The oracle AUC predicts each answer from the student's true P(correct): the ceiling set by slip and guess. Items reused: every item of the KC was answered within 24 h (no simulated time passes), so the least recently answered one was asked again.

BKT − rule MAE per student: +0.012 (95% CI ± 0.026). Needed for BKT: ≤ −0.03 and AUC not lower (AUC difference +0.040).

**Decision:** `learner.knowledge: rule` (switch to rule). Weak evidence for rule: **keep (lowers MAE)** (0.151 off vs 0.148 on).



## high_blood_pressure

| Config | MAE | Next-answer AUC (oracle) | Band accuracy | Items reused (24 h rule) |
|---|---|---|---|---|
| bkt | 0.151 | 0.495 (0.694) | 77.1% | 27 |
| rule | 0.147 | 0.418 (0.570) | 75.0% | 38 |
| bkt+weak | 0.161 | 0.466 (0.524) | 72.7% | 21 |
| rule+weak | 0.145 | 0.547 (0.620) | 77.9% | 24 |

The oracle AUC predicts each answer from the student's true P(correct): the ceiling set by slip and guess. Items reused: every item of the KC was answered within 24 h (no simulated time passes), so the least recently answered one was asked again.

BKT − rule MAE per student: +0.004 (95% CI ± 0.033). Needed for BKT: ≤ −0.03 and AUC not lower (AUC difference +0.077).

**Decision:** `learner.knowledge: rule` (switch to rule). Weak evidence for rule: **keep (lowers MAE)** (0.147 off vs 0.145 on).



## migraine

| Config | MAE | Next-answer AUC (oracle) | Band accuracy | Items reused (24 h rule) |
|---|---|---|---|---|
| bkt | 0.163 | 0.620 (0.611) | 66.2% | 22 |
| rule | 0.151 | 0.579 (0.590) | 72.8% | 36 |
| bkt+weak | 0.165 | 0.630 (0.642) | 62.8% | 23 |
| rule+weak | 0.148 | 0.587 (0.632) | 74.4% | 36 |

The oracle AUC predicts each answer from the student's true P(correct): the ceiling set by slip and guess. Items reused: every item of the KC was answered within 24 h (no simulated time passes), so the least recently answered one was asked again.

BKT − rule MAE per student: +0.012 (95% CI ± 0.026). Needed for BKT: ≤ −0.03 and AUC not lower (AUC difference +0.040).

**Decision:** `learner.knowledge: rule` (switch to rule). Weak evidence for rule: **keep (lowers MAE)** (0.151 off vs 0.148 on).



## pneumonia

| Config | MAE | Next-answer AUC (oracle) | Band accuracy | Items reused (24 h rule) |
|---|---|---|---|---|
| bkt | 0.163 | 0.620 (0.611) | 66.2% | 22 |
| rule | 0.151 | 0.579 (0.590) | 72.8% | 36 |
| bkt+weak | 0.165 | 0.654 (0.680) | 61.9% | 22 |
| rule+weak | 0.146 | 0.613 (0.659) | 75.0% | 36 |

The oracle AUC predicts each answer from the student's true P(correct): the ceiling set by slip and guess. Items reused: every item of the KC was answered within 24 h (no simulated time passes), so the least recently answered one was asked again.

BKT − rule MAE per student: +0.012 (95% CI ± 0.026). Needed for BKT: ≤ −0.03 and AUC not lower (AUC difference +0.040).

**Decision:** `learner.knowledge: rule` (switch to rule). Weak evidence for rule: **keep (lowers MAE)** (0.151 off vs 0.146 on).



## type2_diabetes

| Config | MAE | Next-answer AUC (oracle) | Band accuracy | Items reused (24 h rule) |
|---|---|---|---|---|
| bkt | 0.163 | 0.620 (0.611) | 66.2% | 22 |
| rule | 0.151 | 0.579 (0.590) | 72.8% | 36 |
| bkt+weak | 0.165 | 0.630 (0.642) | 62.8% | 23 |
| rule+weak | 0.148 | 0.598 (0.641) | 74.1% | 36 |

The oracle AUC predicts each answer from the student's true P(correct): the ceiling set by slip and guess. Items reused: every item of the KC was answered within 24 h (no simulated time passes), so the least recently answered one was asked again.

BKT − rule MAE per student: +0.012 (95% CI ± 0.026). Needed for BKT: ≤ −0.03 and AUC not lower (AUC difference +0.040).

**Decision:** `learner.knowledge: rule` (switch to rule). Weak evidence for rule: **keep (lowers MAE)** (0.151 off vs 0.148 on).



## Recommendation

`learner.knowledge: rule`

Runtime 4 s. **Smoke run: too small to decide anything.**
