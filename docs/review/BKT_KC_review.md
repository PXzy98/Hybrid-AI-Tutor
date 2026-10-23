# Learner model review: BKT and the KC design (G1-100)

For: Dr. Abbas (client, medical content) and Dr. Al Ridhawi (advisor, method).
Prepared 22 Oct 2026 by Group 1. About 30 minutes; sections 6 and 7 list what we need from each of you.

Supporting files:
- `content/topics/high_blood_pressure/{kcs,items,misconceptions}.yaml`: the draft content.
- `docs/review/high_blood_pressure_review.csv`: the same content as one spreadsheet, with `reviewed_by` and
  `reviewer_comment` columns to fill in.
- `eval/learner-sim/results/report.md`: the E2 simulation (BKT vs rule).

## 1. Summary

- The learner model estimates, for each knowledge component (KC), the probability that the student has mastered
  it, and turns it into a level: basic (< 0.40), intermediate (0.40–0.70) or advanced (> 0.70), with ±0.05
  hysteresis. The tutor uses that level to choose how deep to explain and which check question to ask.
- **Proposal: keep Bayesian Knowledge Tracing (BKT) as the default model**, with the rule model as the fallback
  (one setting in the dashboard, `learner.knowledge: bkt | rule`).
- In our simulation the rule model was more accurate. We still propose BKT, for the reasons in section 3, and
  ask Dr. Al Ridhawi whether this departure from our pre-registered decision is acceptable.
- Only High Blood Pressure has real content (6 KCs, 24 check questions, 12 misconceptions). None of it has been
  medically reviewed yet. The other four topics are placeholders.

## 2. The two knowledge models

| | BKT (default) | Rule (fallback) |
|---|---|---|
| Idea | Hidden "mastered / not yet" state per KC, updated by Bayes' rule after each graded answer | Accuracy over the last 5 graded answers on the KC |
| Parameters | p_init 0.20, learn 0.10, slip 0.10, guess 0.25 (same for every KC for now) | last_n 5 |
| Evidence | Check-question answers (strong). Weak evidence from the question text is off in the MVP | Same |
| Strength | Standard in the literature; parameters can be fitted from real answers; handles guessing and slips | Simple; adapts fast; copes with forgetting |
| Weakness | Does not model forgetting; default parameters are guesses | No uncertainty model; parameters have no learning interpretation |

## 3. E2 result and why we still propose BKT

E2: 200 simulated students × 40 interactions on High Blood Pressure. The simulated students forget and have
their own slip, guess and learning rates, so the simulation is not built to favour BKT.

| Model | MAE vs true mastery (lower is better) | Next-answer AUC (ceiling 0.62) | Level correct |
|---|---|---|---|
| BKT | 0.260 | 0.522 | 43.3% |
| Rule | **0.203** | **0.551** | **61.2%** |

BKT − rule MAE: +0.057 (95% CI ± 0.006). Our pre-registered rule was "switch to rule unless BKT is clearly
better", so by that rule we should switch. We propose to keep BKT as the default anyway, because:

1. **The difference comes from the default parameters, not from BKT itself.** Changing one parameter at a time
   moves BKT's MAE from 0.210 to 0.324; with guess = 0.35 it is close to the rule model (0.210 vs 0.203). The
   parameters were never fitted, because there are no real students yet.
2. **BKT can be fitted once real answers exist** (from the check-question log, which stores only KC, item,
   score and time). The rule model has nothing to fit.
3. **The simulation is our own model of students.** It includes forgetting, which favours a "last 5 answers"
   rule. We cannot yet tell how close it is to real nursing students.
4. **BKT is the established method** in intelligent tutoring systems, which makes the design easier to justify
   and compare with published work.
5. **The switch costs nothing.** The rule model is implemented, tested (the whole test suite runs with both)
   and can be selected in the instructor dashboard at any time.

What would make us switch: after fitting BKT on the first real answers, if the rule model still predicts the
next answer better (AUC) and gives better levels, we switch to rule.

## 4. KC structure (High Blood Pressure)

Each KC has a difficulty and prerequisites. The recommender suggests the next KC whose prerequisites are all at
P(mastery) ≥ 0.70 and which is not yet mastered (< 0.90).

| KC | Name | Difficulty | Prerequisites |
|---|---|---|---|
| HBP.1 | What blood pressure numbers mean | basic | none |
| HBP.2 | How high blood pressure is classified and diagnosed | basic | HBP.1 |
| HBP.3 | Risk factors and causes | basic | HBP.1 |
| HBP.4 | Why it matters (heart, brain, kidney and eye complications) | intermediate | HBP.2 |
| HBP.5 | Lifestyle management (salt, diet, activity, alcohol, weight) | intermediate | HBP.3 |
| HBP.6 | Medication and adherence (general principles only) | advanced | HBP.2, HBP.4 |

Authoring rules we followed: general health education only, no drug names or doses, and no numeric diagnostic
thresholds, because those depend on the guideline (not chosen yet).

Other topics (asthma, migraine, pneumonia, type 2 diabetes): one placeholder KC each, no questions. The design
target is 4–6 KCs per topic (20–30 in total), drafted the same way and reviewed by Dr. Abbas.

## 5. Check-question bank (High Blood Pressure)

- 24 multiple-choice questions, 4 per KC: 9 basic, 9 intermediate, 6 advanced.
- Each has one correct answer and an explanation. Wrong options that reveal a known misconception carry its ID
  (12 misconceptions, each with a correction the tutor can give).
- Onboarding asks one diagnostic question per KC (the basic one), prerequisites first. If a student gets a KC
  wrong, the KCs that depend on it are not assessed (a correct answer there is more likely a guess). The other
  questions are asked as checks after answers; a question answered in the last 24 hours is not asked again.
- Status: drafted with an LLM and checked by the team; **not medically reviewed**. Until they are, students only
  see them in demo mode (`content.serve_unreviewed`).

## 6. Questions for Dr. Abbas (content)

1. Which guideline should the content follow (for example Hypertension Canada)? This decides whether we may
   include numeric thresholds in HBP.2.
2. Are these the right six KCs for nursing students? Anything missing (for example measurement technique as its
   own KC, or special populations), too broad or too narrow?
3. Are the difficulty levels and prerequisites right?
4. Please mark each question, explanation and misconception in `high_blood_pressure_review.csv`: approve, change
   (comment), or remove. Approved rows get `reviewed_by` and are served to students.
5. Should the medication KC (HBP.6) stay at "general principles only"?
6. In which order should we do the other four topics, and are 4–6 KCs per topic about right?

## 7. Questions for Dr. Al Ridhawi (method)

1. Is it acceptable to keep BKT as the default against our pre-registered E2 rule, given the reasons in section
   3, and report this openly as a deviation?
2. Should we change the default parameters now (guess 0.35 and learn 0.05 did better in the sweep), or keep
   literature defaults until we can fit them on real data?
3. Is fitting BKT on the first real answers, then comparing it with the rule model on next-answer AUC, a sound
   plan for the final evaluation? What minimum amount of data would you accept?
4. Should BKT parameters differ per KC difficulty (`learner.bkt_by_level`) once fitted?

## 8. Decisions (to fill in at the meeting)

| # | Question | Decision | Who | Follow-up |
|---|---|---|---|---|
| 1 | Default knowledge model | | | |
| 2 | BKT default parameters | | | |
| 3 | Guideline | | | |
| 4 | HBP KC changes | | | |
| 5 | Question bank review | | | |
| 6 | Order of the next topics | | | |
