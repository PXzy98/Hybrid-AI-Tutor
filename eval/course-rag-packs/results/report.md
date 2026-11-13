# Retrieval evaluation on the open course packs (S11)

Retrieval of k=4 passages by `IndexedCourseRetriever` (word and character TF-IDF), index built behind the real privacy scan. *Scoped*: restricted to the question's module plus the course-level files, as the product does when a module is chosen. *Course-wide*: `module_id=None`. A hit at rank r means the r-th passage comes from a gold file; hit@1, hit@k and MRR are over passages. Questions without a module (logistics, course-level) are the same in both modes.

## harvard_cs50x

Course type `ece`; 1275 passages; index built per file (refused files skipped).

Files refused by the privacy scan (not indexed): `assignments/pset_5.md`, `assignments/pset_9.md`.

Questions left out because every gold file was refused: cs50-22.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 12 | 0.67 | 0.92 | 0.79 | 0.58 | 0.92 | 0.75 |
| application | 9 | 1.00 | 1.00 | 1.00 | 0.89 | 1.00 | 0.94 |
| logistics | 6 | 0.33 | 0.67 | 0.46 | 0.33 | 0.67 | 0.46 |
| all | 27 | 0.70 | 0.89 | 0.79 | 0.63 | 0.89 | 0.75 |

Top score (course-wide): answerable median 0.23, 10th percentile 0.15; 3 questions not in the material: mean 0.10, max 0.11; chance that an answerable question outscores an unanswerable one 0.96.

## mit_6_002_circuits

Course type `ece`; 1158 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 15 | 0.87 | 1.00 | 0.91 | 0.67 | 1.00 | 0.79 |
| application | 7 | 0.86 | 1.00 | 0.89 | 0.71 | 0.86 | 0.79 |
| logistics | 6 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 |
| all | 28 | 0.86 | 0.96 | 0.89 | 0.71 | 0.93 | 0.80 |

Top score (course-wide): answerable median 0.27, 10th percentile 0.17; 3 questions not in the material: mean 0.17, max 0.25; chance that an answerable question outscores an unanswerable one 0.89.

## mit_7_016_intro_biology

Course type `life_science`; 788 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 19 | 0.84 | 0.95 | 0.88 | 0.68 | 0.95 | 0.79 |
| application | 3 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 0.75 |
| logistics | 6 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 |
| all | 28 | 0.86 | 0.93 | 0.88 | 0.71 | 0.93 | 0.79 |

Top score (course-wide): answerable median 0.20, 10th percentile 0.14; 3 questions not in the material: mean 0.18, max 0.30; chance that an answerable question outscores an unanswerable one 0.68.

## mit_hst151_pharmacology

Course type `medical_science`; 669 passages; index built per file (refused files skipped).

Files refused by the privacy scan (not indexed): `assignments/0310_oral_notes.pdf`, `assignments/0310_oral_slides.pdf`, `assignments/case_topic_desc.pdf`, `assignments/ps2005.pdf`, `exams/2005_final.pdf`, `modules/05_antiinflammatory_drugs.pdf`, `modules/06_vasoactive_drugs_i.pdf`.

Questions left out because every gold file was refused: hst151-09.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 15 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| application | 5 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| logistics | 6 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 |
| all | 26 | 0.96 | 0.96 | 0.96 | 0.96 | 0.96 | 0.96 |

Top score (course-wide): answerable median 0.22, 10th percentile 0.12; 3 questions not in the material: mean 0.12, max 0.17; chance that an answerable question outscores an unanswerable one 0.90.

## All packs

| Pack | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR | unanswerable max top score |
|---|---|---|---|---|---|---|---|
| harvard_cs50x | 0.70 | 0.89 | 0.79 | 0.63 | 0.89 | 0.75 | 0.11 |
| mit_6_002_circuits | 0.86 | 0.96 | 0.89 | 0.71 | 0.93 | 0.80 | 0.25 |
| mit_7_016_intro_biology | 0.86 | 0.93 | 0.88 | 0.71 | 0.93 | 0.79 | 0.30 |
| mit_hst151_pharmacology | 0.96 | 0.96 | 0.96 | 0.96 | 0.96 | 0.96 | 0.17 |

## Misses (course-wide, no gold file in the top results)

- `cs50-16` (concept): gold `modules/08_week_7_sql.md`; top result `modules/07_week_6_python.md` (score 0.44); scoped rank None
- `cs50-24` (logistics): gold `syllabus.md`; top result `assignments/pset_1.md` (score 0.08); scoped rank None
- `cs50-25` (logistics): gold `syllabus.md`; top result `assignments/pset_1.md` (score 0.27); scoped rank None
- `circ-03` (application): gold `modules/02_lecture_2_basic_circuit_analysis_method.pdf`; top result `modules/06_lecture_6_nonlinear_analysis.pdf` (score 0.43); scoped rank 4
- `circ-28` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.25); scoped rank None
- `bio7016-02` (concept): gold `modules/02_recitation_2.pdf`, `modules/09_recitation_9.pdf`; top result `modules/13_recitation_13.pdf` (score 0.15); scoped rank None
- `bio7016-26` (logistics): gold `calendar.md`; top result `modules/07_recitation_7.pdf` (score 0.16); scoped rank None
- `hst151-26` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.25); scoped rank None

## Analysis

Written by hand from the run that produced the tables above (the question sets and the packs may change; rerun
before quoting numbers). The questions were written from the pack material in a student's wording, so lexical
overlap with the notes is still higher than for real students: read the numbers as an upper bound.

**What works.** Concept and application questions about a chosen module are found: with the module scope on,
hit@4 is 0.9 or better in every course. Scoping matters most between neighbouring lectures of one topic: for
`bio7016-08` (proofreading by DNA polymerase) the right recitation is rank 4 course-wide and rank 1 scoped, and
for `bio7016-22` (HIV, helper T cells) likewise.

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
6. **Privacy-scan refusals remove material.** Seven HST.151 files (including lectures 5 and 6) and two CS50x
   problem sets are refused as student data (known false positives, `data/demo_courses/README.md`), so questions
   about them cannot be answered (`hst151-09`, `cs50-22`, left out of the metrics). The whole-course rebuild fails
   closed on the first such file, so the harness had to scan and skip file by file.

**Suggestions (not done here).** Down-weight practice exams and homework (or search them only when asked for);
index calendar rows with their session and date words; add a semantic or query-expansion step before the
lexical score; fix the scan false positives.

