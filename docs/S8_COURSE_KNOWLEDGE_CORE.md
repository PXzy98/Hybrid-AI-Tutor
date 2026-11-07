# S8 Course-level knowledge tracing core — 2026-11-05

Owner: Siyun. Implemented in `backend/app/learner/knowledge/course_core.py`.
Pure per-course learner state and synthetic test evidence; no database, no question text,
no student records in this branch.

- Per student/course ability, updated from graded answers with a bounded Elo-like online rule.
- Per-KC Bayesian Knowledge Tracing with diagnostic (no practice learning), strong
  (posterior plus learning), and weak signals (likelihood only).
- Validated acyclic prerequisites; effective dependent mastery is lowered when
  prerequisites are weak without corrupting the raw KC posterior.
- Course/student boundary validation and immutable update result.

The v4 guide proposes an Elo/IRT-like ability and BKT/PFA. The exact hyperparameters
here are engineering defaults, **not calibrated or validated with actual students**.
Z4 must provide course-specific evidence persistence, KC graph and settings;
S8 must wire the production `KnowledgeModel` and compare it against the existing
BKT using real or approved synthetic evaluation protocols. This file alone does not
complete the production S8 task.

## Update after review (2026-11-07)

- The ability layer now enters the estimate: a KC the student has not been observed on starts from the
  prior's log-odds shifted by `ability_weight × ability` (`prior_for`); `ability_weight=0` is plain BKT.
- `predict_correct(state, kc)` gives P(correct) from the effective mastery (with prerequisites).
- `CourseKnowledgeCore.from_settings` reads `learner.bkt_defaults` and `learner.weak_likelihood`
  instead of fixed numbers.
- Simulated comparison with plain BKT: `eval/learner-sim/course_model_compare.py`, results in
  `eval/learner-sim/results/course_model.md` (layered MAE 0.175 vs 0.211 for plain BKT; on KCs not
  practised yet 0.175 vs 0.183; next-answer AUC 0.530 vs 0.524). Simulation only, not real students.

Still open (needs Z4): course-scoped persistence of the state and evidence, and wiring behind the
`KnowledgeModel` interface with `course_id`.
