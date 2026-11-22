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
| Class statistics with some students shared | Class numbers use only data never shown individually; individual views show only data recorded while the student shared (see "Differencing"; option B, chosen by Z on 2026-11-22) | otherwise the class totals reveal the refusers |
| Never shown, in any mode | question text (it is never stored, rule 1); the answers the tutor gave; conversations; the student's own answer instruction (V15); the end-of-term survey answers (stay anonymous); anything from before the agreement | rule 1; the survey only works when it is anonymous; V15 is the student's private setting |
| Audit | Every individual view (overview, plan, quiz results) is written to the audit log, as today; the student can see that their data was viewed (count and dates, not who) | transparency for the student |

## What the instructor sees of a student who shares

The existing overview, with nothing new: progress bands per knowledge component and their trend, open
misconceptions, the number of check questions answered, quiz scores, the answer style (example or idea first,
short or detailed) when it was set after the agreement, the last active date, and the learning plan the
instructor writes. The instructor can then use **Draft extra material** (V8) for the class, not for one student;
targeted material for one student stays out of scope ("Not this term").

## Differencing (the main new rule; decided 2026-11-22)

Class statistics and individual views must never cover the same data: if 6 students answered a quiz and the
instructor sees 5 of the scores, the class average minus those 5 is the sixth score. The same holds for band
counts per KC, misconception counts, weak topics (V8), quiz results and the usage statistics (V2).

Rule (option B, see "How this rule was decided"): **the two sides use disjoint data, decided per stored event.**

- An event (an evidence row, a quiz attempt, a request-log row) belongs to the **shared side** when it was
  recorded inside one of the student's sharing windows in this course (from the agreement to the stop). Only the
  shared side ever appears in an individual view.
- Every other event, of every student, is on the **class side**: the events of students who never shared, and the
  events a sharing student made before the agreement or after stopping. Class numbers (class summary, V2
  statistics, weak topics, insights, quiz results, the end-of-term export) are computed from the class side only;
  a KC band counted in a class number is the band replayed from that student's class-side events.
- A class number is hidden when fewer than the minimum group (`learner.class_summary_min_group`, 5) of students
  contribute class-side events to it, as in mode A.

Because an event is on exactly one side, no class number contains anything an individual view shows, and no
individual view shows anything a class number contains: subtracting one from the other gives nothing, in any order
and in any mode. A student who starts sharing does not leave the class numbers (their earlier events stay on the
class side, so a total does not shrink); their new events go to the shared side only. A student who stops sharing
adds new events to the class side again, like any student who does not share. Class numbers still change over
time as students act; that is the same in mode A and is covered by the minimum group.

**The sharing windows are kept for the term.** The side of an event is decided from a per-course record of each
student's windows (start and end), kept until the end of term and never cleared by a mode change or by the
administrator switching individual views off (#151 clears `visibility_ack_at` and `visible_since`, which say only
the current state). Once a course has had any sharing window, the class numbers keep excluding those windows for
the rest of the term, in mode A too. End of term removes the course's student data, the windows with it.

This makes the class statistics poorer when many students share, and individual views show only what was
recorded while the student shared. That is the price of letting the others refuse safely; the instructor manual
says so and advises switching a course to mode B at the start of term.

## Changes to the code (when the switch is on)

1. **Students page**: one state "Shared" or "Not shared" per student (today: "Visible", "Not visible", "Not
   joined yet", and the detail explains why). A student who stopped sharing and one who never agreed show the
   same "Not shared"; the API returns `visible_to_instructor` only (it already does) and no reason.
2. **Differencing**: a `sharing_window` table (course, student, start, end; kept until the end of term), and the
   class-side filter on every class number: `admin/summary.py` (class summary, bands replayed from class-side
   evidence), `learner/statistics.py` (V2), `learner/weak_topics.py` (V8), `learner/quizzes.py` (`quiz_results`
   averages and per-question rates), the insights (tier 3) and the end-of-term export; individual views read the
   shared side only (they already read only `visible_since` onwards).
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
- Disjoint sides: for every class number and every individual view in a course with sharing students, no event
  is used by both (a property test over a generated course: random agreements, stops and answers).
- Opt-in does not shrink a total: six students, a week's question total read; one student then agrees: the total
  of that past week is unchanged (their earlier questions stay on the class side) and their later questions
  appear only in their overview.
- Aggregate first: a quiz average read before anyone shares stays the same after five students agree, and their
  overviews show only attempts made after agreeing.
- Mode and switch changes: after B -> A, and after the administrator switches individual views off and on, the
  class numbers still exclude the shared windows of this term; a course that never had a sharing window behaves
  as in mode A.
- Stopping: a student who stops sharing and asks more questions adds them to the class side only; the windows
  survive #151's clearing of the acknowledgement columns.
- Minimum group: a class number with fewer than 5 students contributing class-side events is hidden.
- The overview never contains a question, an answer, the V15 instruction or a survey answer.
- Every individual view is audited, and the student sees the count of views.
- Copy to the next term and end of term carry no agreement.

## How this rule was decided (2026-11-22)

The design went through six rounds of automated review (Codex, PR #153). Each round found a new way to subtract a
class number from what the instructor saw individually; the record is kept here because the reasons matter for
anyone who changes the rule later.

| Round | Rule at that point | Hole found | Answer |
|---|---|---|---|
| 1 | Hide a class number in a course **in mode B** when fewer than 5 contributing students do not share | Read five students' bands in mode B, switch the course back to mode A, read the class band counts, subtract | count students as *disclosed* for the rest of the term, in any mode (record: the audit log, not the acknowledgement columns that #151 clears) |
| 2 | Disclosed students, any mode | Read a class number first (nothing disclosed yet), then open the individual views and subtract | a *release log* of every class number shown, and a check before each individual datum is shown (both orders) |
| 3 | Disclosed students, release log | A student's quiz attempt from before the agreement is never shown, yet opening their overview counted them as disclosed, so the quiz average was released; also an arithmetic slip in a test (with 6 contributors and a minimum of 5 only one score may be shown) | track disclosure per datum, not per student; fix the test |
| 4 | Disclosure per datum | A changing datum (a week's question count) after a student stops sharing: the old view counted as disclosure of the new value | give each contribution a version (the newest event ID) |
| 5 | Versioned contributions | An individual band is computed since the agreement, the class band from the whole history: same newest event, different data | identify a contribution by its event range |
| 6 | Option B by student: class numbers only from students who never shared | A past total read with six students, recomputed from five after one opts in: the difference is the new sharer's earlier data | decide by event, not by student (the rule above) |

After round 5 the patched rule needed a release log, event ranges in every class number and in the audit log, and
a check before every individual datum, and each round still found a further case. Three options were compared:

| Option | What the instructor gets | Cost |
|---|---|---|
| A. Keep patching the disclosure rule | the most class numbers | release log, versioned contributions, checks everywhere; hard to prove complete |
| B. Class numbers only from data never shown individually | fewer class numbers when many share | one filter per class number and a table of sharing windows; the two sides are disjoint by construction |
| C. No class numbers in mode B | none in mode B | simplest; the class overview is lost exactly where individual views exist |

Z chose option B on 2026-11-22. The first form of B (by student) failed in round 6, so the rule decides per event.
Its argument is structural (each event is on one side), so it does not depend on the order in which the instructor
reads things or on mode changes; the property test above checks it on generated courses.

## Not decided here

- Whether teaching assistants may see shared students (there is no TA role).
- Whether the instructor may message a shared student from PACT (no messaging exists).
- Prof. Abbas's agreement for any course with real students.
