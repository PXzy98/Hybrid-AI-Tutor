# S10 — Class insights aggregate core

Status: **implemented and verified offline; production S10 remains blocked by S8/Z4**.

Input is fictional per-course event labels (KC and misconception IDs, pseudonymous
student IDs), never student question text. The function returns only label counts:
no per-student records, no free-text fields, and no student IDs. It suppresses the
entire cohort and every individual label with fewer than five distinct students
(or the higher configured group threshold). Ranking is deterministic.

Before release, S8 supplies the real course-level learner signal data, Z4 provides
course-scoped tables and aggregation queries, and Z9/Z10 provide instructor-only
v2 endpoint authorization and audit. An instructor AI model must receive aggregate
labels and counts only. This module does not read the DB, call an LLM or return data
from a live class, and its tests use fictional identifiers.
