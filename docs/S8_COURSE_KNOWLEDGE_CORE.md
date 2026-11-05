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
