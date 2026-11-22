# Individual view by the student's choice (task V23, design for review)

State: design only, agreed in principle by Z on 2026-11-21. **Prof. Abbas decided on 2026-11-17 that
instructors see class statistics only in this version; this design is switched off until he agrees.** The code
stays behind `learner.instructor_individual_view` (default `false`, V1); nothing here changes a deployment
where the switch is off.

## Goal

Where the client allows it, a student may choose to share their own progress with the course's instructors, so
the instructor can help them individually. A student who does not choose to share counts only in the class
statistics. The existing mode B code (course-structure.md 4.5, guide 4.8) is the base; this note says what must
change before it can be used.

## Decisions

| Topic | Decision | Why |
|---|---|---|
| Who switches it on | The administrator enables individual views for the deployment (`instructor_individual_view: true`); then an instructor may set **one course** to mode B. Default: off, every course in mode A | the client decides per deployment; the instructor per course |
| Default for the student | **Nothing is shared until the student agrees** (opt-in: "I agree to share"); the student can stop at any time and start again | a default of "shared unless you switch it off" is not consent: many students never open the setting |
| What is shared | Only data created **after** the student agreed (`visible_since`); stopping hides everything again, starting again starts a new window | as today |
| Refusing must be safe | The instructor cannot tell who refused: a student who never agreed and one who stopped look the same ("not shared"); no count of refusals is shown per student; the student's choice is never sent to the instructor in any other form | a choice only works when refusing has no cost (Z's reflection, 2026-11-18) |
| Class statistics with some students shared | No number may let the instructor compute the data of the students who did not share (see "Differencing") | otherwise the class totals reveal the refusers |
| Never shown, in any mode | question text (it is never stored, rule 1); the answers the tutor gave; conversations; the student's own answer instruction (V15); the end-of-term survey answers (stay anonymous); anything from before the agreement | rule 1; the survey only works when it is anonymous; V15 is the student's private setting |
| Audit | Every individual view (overview, plan, quiz results) is written to the audit log, as today; the student can see that their data was viewed (count and dates, not who) | transparency for the student |

## What the instructor sees of a student who shares

The existing overview, with nothing new: progress bands per knowledge component and their trend, open
misconceptions, the number of check questions answered, quiz scores, the answer style (example or idea first,
short or detailed) when it was set after the agreement, the last active date, and the learning plan the
instructor writes. The instructor can then use **Draft extra material** (V8) for the class, not for one student;
targeted material for one student stays out of scope ("Not this term").

## Differencing (the main new rule)

Class statistics count every student; individual views show the students who share. If 6 students answered a
quiz and 5 of them share, the class average minus the 5 visible scores is the sixth student's score. The same
holds for band counts per KC, misconception counts, weak topics (V8) and the usage statistics (V2).

Rule: **in a course in mode B, a class number is shown only when the students who do not share are themselves at
least the minimum group** (`learner.class_summary_min_group`, 5) in that number, or when nobody shares. Otherwise
the number is hidden ("hidden: too few students who do not share"). Concretely, for each aggregate the code
computes the contributing students, splits them into shared and not shared, and suppresses when
`0 < not_shared < min_group`. Counts of students (enrolled, active) are not affected; per-week and per-module
question counts are, because a shared student's activity is visible.

This makes the class statistics poorer when almost everybody shares. That is the price of letting the others
refuse safely, and the instructor manual says so.

## Changes to the code (when the switch is on)

1. **Students page**: one state "Shared" or "Not shared" per student (today: "Visible", "Not visible", "Not
   joined yet", and the detail explains why). A student who stopped sharing and one who never agreed show the
   same "Not shared"; the API returns `visible_to_instructor` only (it already does) and no reason.
2. **Differencing**: the suppression above in `admin/summary.py` (class summary), `learner/statistics.py` (V2),
   `learner/weak_topics.py` (V8), `learner/quizzes.py` (`quiz_results` averages and per-question rates), the
   insights (tier 3) and the end-of-term export.
3. **Student side**: the sharing card on My progress asks first ("Share my progress with the instructors of this
   course?") with what is shared and what never is; the privacy notice (V3) and the consent text use the
   mode B wording (`privacy.lineIndividual`, `privacy.point.instructorIndividual`, already there); the student sees
   how many times their overview was viewed and when.
4. **Defaults when a course is switched to mode B**: every student starts as not shared and is told on their next
   visit (the chat banner and My progress, as today); switching back to A hides everything at once (as today).
5. **Re-check the v5 additions in mode B**: course copy for next term (W12) never copies agreements; end of term
   exports only the overviews the instructor may see (as today) and deletes the agreements; the French texts;
   the AI assistant hand-over (V8) carries no student; the V15 instruction is never in an overview.
6. **Documents**: guide 4.8, course-structure.md 4.5, both manuals, the consent text, and this note's state.

## Tests (each one a test)

- Mode B cannot be chosen while the switch is off (exists, V1); with it on, only an instructor of the course sets
  it (access tests).
- A student who never agreed and one who stopped are indistinguishable in every instructor response (members,
  overview 404 body, quiz results, statistics).
- Nothing from before the agreement is shown; stopping hides it all; starting again shows only the new window
  (exists, extend to quizzes and V2).
- Differencing: with 6 students and 5 sharing, no class number a student contributes to is shown; with 5 not
  sharing, it is; with nobody sharing, every number behaves as in mode A.
- The overview never contains a question, an answer, the V15 instruction or a survey answer.
- Every individual view is audited, and the student sees the count of views.
- Copy to the next term and end of term carry no agreement.

## Not decided here

- Whether teaching assistants may see shared students (there is no TA role).
- Whether the instructor may message a shared student from PACT (no messaging exists).
- Prof. Abbas's agreement for any course with real students.
