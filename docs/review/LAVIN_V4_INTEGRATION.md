# S7 — Lavin-reviewed question-bank staging on the v4 baseline

This branch is based on v4 main commit 7e943a6. It is **not approved for student release**.

## What was integrated
- Five medical topics, 26 knowledge components, 84 four-choice diagnostic items and 32 misconception corrections, with the existing question and KC identifiers preserved.
- Lavin's original item-level CSV comments and the 2026-11-05 revision log.
- 30 draft item revisions addressing weak distractors and insufficient difficulty variation.
- A learner-side validation guard: an unreviewed item submitted directly to onboarding cannot update the learner model when content.serve_unreviewed is false.
- Alignment tests for review CSVs, answers, misconceptions, and the learner's draft gating.

## What Lavin did and did not approve
Lavin's November 5 email found no medically inaccurate or inappropriate material in the **original** questions. She said the difficulty was closer to undergraduate courses than to medical school, and suggested better distractors. Her review does not constitute a second sign-off on the revised 30 items. All items and misconceptions still have reviewed_by set to null.

Before student use:
1. Confirm the intended level with the client and Lavin.
2. Send the revised items back for confirmation.
3. Confirm source permissions, especially for any new medical teaching material.
4. Do not enable CONTENT__SERVE_UNREVIEWED in a student-facing deployment.

## Z4 course catalog migration dependency
The v4 design imports content/topics YAML into the General Medical Knowledge course's five modules when Z4 is implemented. Z4 removes the old reviewed_by column. This branch should be coordinated with Zhenyan before Z4 snapshots or imports the content files. The new database needs an explicit accepted/published state; draft status must survive migration.

Do not cherry-pick the older BKT feature branch into main: it carries outdated code. Review this v4-based branch and merge or import only the approved content when the platform migration is ready.

## Tests
Run from backend/ with a clean local environment:
- python -m pytest -q tests/test_bkt_questionnaires.py tests/test_lavin_mcq_review.py
- python -m pytest -q
- TEST_LEARNER_KNOWLEDGE=rule python -m pytest -q
- python -m ruff check . ../scripts

Use only fictional student accounts for diagnostic functional tests. Do not treat a medical expert's answers as representative student performance data.
