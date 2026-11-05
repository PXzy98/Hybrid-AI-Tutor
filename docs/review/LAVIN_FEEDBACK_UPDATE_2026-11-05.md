# Lavin MCQ Review — targeted revision, 2026-11-05

## Advisor feedback
Lavin reported no apparent medical inaccuracies or inappropriate content in the original questions. The overall difficulty was more suitable for an undergraduate course than for medical school. She recommended more plausible wrong options and greater Basic/Intermediate/Advanced differentiation. She also provided 13 item-level comments in the returned CSVs.

Audience is still pending confirmation: this draft keeps an undergraduate diagnostic level. Changes made after the email have NOT yet been re-approved medically.

## Changes
- 84 MCQs preserved across five medical topics; item IDs, KC IDs and level labels unchanged.
- 30 revised items: all 13 annotated questions, plus 17 other weak-distractor items.
- All reviewer comments preserved in the CSV files.
- Three answer-key changes: PNE.3-q3 D->C, PNE.4-q2 B->D, T2D.4-q2 C->D.
- Misconception IDs remain attached to the corresponding distractor choice.
- Every revised question still has reviewed_by null/blank. No student data or BKT parameters were created.

## Topic notes
- Asthma: replace unrelated distractors with credible symptom and assessment mistakes.
- Pneumonia: distinguish a bacterial cause, use an all-of-the-above question on warning symptoms, clarify why a classroom quiz cannot decide treatment.
- High blood pressure: interpret persistent raised diastolic readings and apply modifiable risk-factor knowledge.
- Type 2 diabetes: more substantive insulin/glucose question and organ-system combinations.
- Migraine: make symptom comparison and aura items different, and strengthen advanced self-management choices.

## Implementation
- Updated five per-topic CSVs and ALL_TOPICS_LAVIN_REVIEW.csv.
- Synchronized the 84 diagnostic items with content/topics/.../items.yaml.
- LAVIN_REVISION_LOG.csv records the 30 modified IDs, reasons and three answer-key updates.
- test_lavin_mcq_review.py verifies YAML/CSV alignment and retained reviewer comments.
- No release or merge into main: the work remains on a draft review branch.

## Next
1. Confirm with the client if the intended audience is undergraduate or medical school.
2. Have Lavin re-check the revised items, especially PNE.3-q3, PNE.4-q2, T2D.1-q3, T2D.4-q2, HBP.1-q4 and the migraine case questions.
3. Only after explicit sign-off mark these revised questions approved for student use.
4. BKT testing with a simulated student is separate; Lavin's review comments are not simulated student answers.

Supporting general sources (not an expert sign-off on the revisions):
https://medlineplus.gov/pneumonia.html
https://medlineplus.gov/migraine.html
https://medlineplus.gov/diabetestype2.html
https://medlineplus.gov/highbloodpressure.html
https://medlineplus.gov/asthma.html
