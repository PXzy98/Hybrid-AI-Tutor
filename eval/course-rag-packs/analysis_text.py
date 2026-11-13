"""Hand-written analysis appended to results/report.md by run.py (written from the run of 2026-11-12)."""
# ruff: noqa: E501  (Markdown text)

ANALYSIS = """## Analysis

Written by hand from the run that produced the tables above (the question sets and the packs may change; rerun
before quoting numbers). The questions were written from the pack material in a student's wording, so lexical
overlap with the notes is still higher than for real students: read the numbers as an upper bound.

**What works.** Concept and application questions about a chosen module are found: with the module scope on,
hit@4 is 0.9 or better in every course. Scoping matters most between neighbouring lectures of one topic: for
`bio7016-08` (proofreading by DNA polymerase) the right recitation is rank 4 course-wide and rank 1 scoped, and
for `bio7016-22` (HIV, helper T cells) likewise.

**Change made from this evaluation.** In module-scoped retrieval, course-level files now count 0.55 of their
score (`COURSE_LEVEL_WEIGHT` in `backend/app/rag/course_retriever.py`). Over all eight courses, scoped hit@1
went from 0.82 to 0.92 and hit@4 from 0.94 to 0.97 (weights 1.0, 0.85, 0.7 and 0.55 compared). Logistics
questions asked from inside every module still find their course-level answer as often as before (hit@4 0.87
at every weight). The examples below were written before that change; pattern 1 is now much rarer in scoped
retrieval, and unchanged course-wide.

**Failure patterns, with examples.**

1. **Course-level documents and practice exams outrank the lecture.** They are always searched, and homework
   and old quizzes repeat the lecture's words. `circ-03` (node method): course-wide the right lecture is not in
   the top 4 (quizzes and another lecture win), scoped it is rank 4 behind two quizzes and a homework. `circ-10`
   and `circ-13` are rank 3 behind a quiz or homework; `bio7016-03` (enzymes) and `bio7016-16` (optogenetics) are
   rank 3 behind exams.
2. **Logistics questions about the calendar are not found.** `hst151-26` (which session is the midterm),
   `circ-28` (when is homework 4 due) and `bio7016-26` (which lectures are on exam 2) return the syllabus or a
   lecture, never `calendar.md`: the calendar is a terse table with no sentence vocabulary, and "session" or
   "due" match the syllabus better.
3. **Syllabus facts lose against repeated boilerplate.** `cs50-24` (textbook) and `cs50-25` (correctness versus
   style) return problem sets first (scores 0.08 and 0.27): every problem set repeats "check50", "style" and
   submission text, and the one-line syllabus statement scores lower.
4. **Vocabulary gap.** `cs50-16` (how attackers trick a website's database through input) never reaches the SQL
   week, even scoped (course-wide top: Python week 6, 0.44): the notes say "SQL injection attack", the student
   says "trick the database". `bio7016-02` (what a membrane is made of) returns assignments and exams. The index
   is purely lexical (word and character TF-IDF); there is no semantic matching.
5. **Absolute scores do not tell "not in the material".** The unanswerable `bio7016-30` (medical extension)
   has top score 0.30 (`assignments.md`) and `circ-30` (head TA office hours) 0.25 (`syllabus.md`), above the
   10th percentile of answerable questions; see the chance-of-outscoring figures in the tables. A fixed score
   threshold cannot be used to say "I have no material on this".
6. **Privacy-scan refusals remove material.** Seven HST.151 files (including lectures 5 and 6), four HST.035
   files (lectures 9, 10 and 12), two CS50x problem sets, and one file each in 6.006 (lecture 3), 7.03 and
   RES.6-007 are refused as student data (known false positives, `data/demo_courses/README.md`). Questions
   about them cannot be answered (`hst151-09`, `cs50-22`, `alg-02`, and five HST.035 questions, left out of
   the metrics). The whole-course rebuild fails closed on the first such file, so the harness had to scan
   and skip file by file; six of the eight packs could not be indexed whole.
7. **Near-duplicate lectures compete.** `sig-16` (continuous to discrete filters) and `alg-17` (dynamic
   programming III) return the neighbouring lecture with the same title words first (`sig-16`: lecture 18
   before 23; `alg-17`: lecture 18 before 17 course-wide, though scoped it is rank 1). Scoping by module
   fixes this when the student has chosen one.

**Suggestions (not done here).** Down-weight practice exams and homework in course-wide retrieval too (or search
them only when asked for);
index calendar rows with their session and date words; add a semantic or query-expansion step before the
lexical score; fix the scan false positives.
"""
