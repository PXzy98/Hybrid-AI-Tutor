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

Rule: **a class number is shown only when its undisclosed contributions come from at least the minimum group of
students** (`learner.class_summary_min_group`, 5), or when none of its contributions was disclosed. Otherwise the
number is hidden ("hidden: too few students who do not share"). Concretely, for each aggregate the code lists
its contributions (one per student and datum: a quiz attempt, a KC band, a misconception, a week's questions),
splits them into disclosed and undisclosed, and suppresses when `0 < students with an undisclosed contribution <
min_group`. Counts of students (enrolled, active) are not affected.

**Disclosed means shown, datum by datum and version by version.** A contribution is identified by the student,
the datum key and its **event range**: the smallest and the largest ID of the stored events it is computed from
(evidence rows for a KC band or a misconception, the quiz attempt, the request-log rows of a week's questions).
Events are never changed, only added, so a new answer or question gives the datum a new range; and an individual
band computed from the events since the agreement (`visible_since`) has another range than the class summary's
band computed from the whole history, so seeing the first never discloses the second. A contribution counts as
disclosed for the rest of the term once an instructor of the course has seen that version in an individual view, whether or not the student still shares and
whatever mode the course is in now. Opening a student's overview does not disclose the student's other data: a
quiz attempt from before the student agreed (`visible_since`) is not shown and stays undisclosed, so a quiz
average that includes it is still checked. A newer version is undisclosed until it is shown: if a student stops sharing and then asks more questions in the
same week, that week's count has a new version that was never shown, so the class number that includes it is
checked again. Hiding the individual views does not take back what was seen: after
reading five students' bands in a course of six, switching back to mode A (or the administrator switching
individual views off) would otherwise let the instructor read the class band counts and compute the sixth. So
the rule applies in mode A too, for the whole term.

**Both orders.** Hiding later class numbers is not enough: an instructor can first note a class number while
nothing is disclosed (the average of a quiz six students took), then open those students' results and compute
the last one. So the rule is symmetric:

- every class number shown to an instructor is recorded in a **release log**: which number (kind and key, for
  example `quiz_average:quiz 12` or `band_counts:KC C.3`) and the contributions it was computed from
  (pseudonymous student ID, datum key and event range); no values, no text;
- before an individual view shows a datum, the code checks every released number that the datum went into: if
  showing it would leave `0 < students with an undisclosed contribution < min_group` in that number, the datum is
  hidden in the individual view ("hidden: part of a class number already shown"), while the rest of the overview
  is shown;
- and, as above, a class number is not released when it would break the same condition.

In practice a course that wants individual views should switch to mode B at the start of term, before class
numbers are read; the manual says so.

The record of what was disclosed is the audit log of individual views (see Audit above), not the acknowledgement
columns: `visibility_ack_at` and `visible_since` are cleared when a student stops sharing and, since #151, for
every course while individual views are switched off, so they cannot say what was already seen. Each audit entry
names the course, the student's pseudonymous ID and the keys and event ranges of the data shown (quiz, KC,
misconception, week); no values. The entries stay until the end of term, when the course's student data is removed and the next term
starts with nothing disclosed.

**A simpler alternative to decide before the code.** The rules above keep class numbers wherever they cannot be
used to infer an undisclosed contribution, but they need a release log, event ranges in every aggregate and in
the audit, and a check in every class number; each review round found a further way to subtract. A simpler rule
that is easier to verify: in a course in mode B, compute every class number only from students who never shared
this term (and hide it below the minimum group), or show no class numbers in mode B at all. Both give the
instructor less, and both remove differencing without logs. Z and Prof. Abbas choose one of the three before
V23 is implemented.

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
- Differencing after B -> A: with 6 students, the instructor views 5 overviews in mode B, the course is switched
  back to mode A; the class band counts, quiz averages, weak topics and usage numbers stay hidden for the rest of
  the term. The same after the administrator switches individual views off (acknowledgements cleared, #151) and
  on again. A course where no individual view was ever opened behaves as in mode A.
- Differencing, aggregate first: with 6 students who took a quiz and `min_group` 5, the instructor reads the quiz
  average (nothing disclosed yet), then opens the overviews of the students who share: the first score is shown
  (5 undisclosed contributors remain), every further score is hidden (it would leave 4), while the KC bands that
  were never part of a released number are shown. The release log holds no values and no question text.
- Differencing, mixed consent windows: 6 students take a quiz; 5 had agreed before their attempt, the sixth
  agrees only afterwards. The instructor opens all six overviews: five scores are shown, the sixth student's
  attempt is not (it predates the agreement) and stays undisclosed; the quiz average is then hidden, because
  one undisclosed contribution remains.
- Differencing with a consent window: six students share; one of them has answers from before the agreement.
  The instructor views all six KC bands (each computed since the agreement): the class band counts, computed
  from the whole history, stay hidden, because that student's whole-history band has a range that was never
  shown.
- Differencing after sharing stops: six students share and the instructor views all six current-week question
  counts; one student stops sharing and asks two more questions; the instructor refreshes the other five
  overviews: the class question count of that week is hidden, because the stopped student's week has a new
  version that was never shown.
- The overview never contains a question, an answer, the V15 instruction or a survey answer.
- Every individual view is audited, and the student sees the count of views.
- Copy to the next term and end of term carry no agreement.

## Not decided here

- Whether teaching assistants may see shared students (there is no TA role).
- Whether the instructor may message a shared student from PACT (no messaging exists).
- Prof. Abbas's agreement for any course with real students.
