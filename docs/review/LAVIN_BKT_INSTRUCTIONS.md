# BKT Question Bank — Draft for Lavin's Medical Review

**Project:** Privacy-Aware Hybrid AI Tutor Using Local and Cloud Models
**Prepared for:** Lavin Kazemi (medical content advisor)
**Status:** DRAFT — none of these question items or misconception corrections is medically approved.
**Sources for initial topic drafting:** MedlinePlus topic pages referenced in `content/topics/<topic>/kcs.yaml`. These are general educational references, not necessarily the final course textbooks or the client's course-specific guidelines.

## What is in this package?

| Topic | Knowledge Components (KCs) | MCQ items | Initial onboarding questions | Misconceptions |
|---|---:|---:|---:|---:|
| High Blood Pressure | 6 | 24 | 6 | 12 |
| Type 2 Diabetes | 5 | 15 | 5 | 5 |
| Asthma | 5 | 15 | 5 | 5 |
| Migraine | 5 | 15 | 5 | 5 |
| Pneumonia | 5 | 15 | 5 | 5 |
| **Total** | **26** | **84** | **26** | **32** |

Use `ALL_TOPICS_LAVIN_REVIEW.csv` to review everything in one spreadsheet, or a separate `<topic>_review.csv` to review one subject at a time. The separate CSVs contain exactly the same review data as the consolidated file.

## How to review

Open the CSV in Excel (UTF-8 encoding) or Google Sheets. Rows are marked:
- **TOPIC:** Topic name and the intended educational reference / guideline.
- **KC:** Knowledge component, definition, assigned level, and prerequisite KC IDs.
- **ITEM:** Four-option multiple-choice question with answer key, explanation, difficulty and any distractor-to-misconception link.
- **MISCONCEPTION:** Student misconception and the correction that could later be shown by the tutor.

Please add notes in **`reviewer_comment`**. In particular, could you check:
1. Whether each topic's **KC breakdown and prerequisites** match the intended course and student level.
2. Medical accuracy, clarity and absence of ambiguous correct answers for each **MCQ**.
3. Whether the **basic / intermediate / advanced** difficulty tags are reasonable.
4. Whether the distractors reflect meaningful student misunderstandings rather than merely obviously wrong alternatives.
5. Whether **misconception explanations** are medically sound and safe to display to students.
6. Which **course guidelines/textbooks and source dates** we should use instead of the temporary general MedlinePlus reference.

Please **leave `reviewed_by` blank** in the spreadsheet. The development team will mark items as approved in YAML **only after** explicit medical review. An unreviewed item must not be presented as medically validated.

## How the software uses the questions

1. The student picks a medical topic in **Personalize your tutor**.
2. With consent, the app presents **one basic MCQ per KC** in prerequisite order (5 questions per newly added topic; 6 for blood pressure).
3. Correct/incorrect answers become **diagnostic evidence** for BKT. Prerequisite-dependent KCs are not assessed when a required earlier KC was answered incorrectly.
4. During tutoring, follow-up **Check Questions** are selected from the remaining basic/intermediate/advanced items. These provide strong evidence for updating the student's mastery model.
5. The student UI **never receives the correct answer key or misconception mapping** before answering.
6. Unreviewed items are disabled in the normal application configuration. `CONTENT__SERVE_UNREVIEWED=true` is exclusively for internal development demonstrations with fictional users.

## Review is not user testing

This is a request for **medical content validation**, not a real student survey or approval for a clinical study. The separate optional four-rating **Student Feedback Survey** assesses perceived answer helpfulness, relevance, clarity and source confidence. It does not initialize BKT or establish medical accuracy.

**Return requested:** A copy of the annotated CSV(s), or written feedback identifying question/KC IDs to adjust. Please do not attach real patient information.
