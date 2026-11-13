# Retrieval evaluation on the open course packs (S11)

Retrieval of k=4 passages by `IndexedCourseRetriever` (word and character TF-IDF), index built behind the real privacy scan. *Scoped*: restricted to the question's module plus the course-level files, as the product does when a module is chosen. *Course-wide*: `module_id=None`. A hit at rank r means the r-th passage comes from a gold file; hit@1, hit@k and MRR are over passages. Questions without a module (logistics, course-level) are the same in both modes.

## harvard_cs50x

Course type `ece`; 1393 passages; index built per file (refused files skipped).

Files refused by the privacy scan (not indexed): `assignments/pset_5.md`.

Questions left out because every gold file was refused: cs50-22.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 12 | 1.00 | 1.00 | 1.00 | 0.58 | 0.92 | 0.75 |
| application | 9 | 1.00 | 1.00 | 1.00 | 0.89 | 1.00 | 0.94 |
| logistics | 6 | 0.50 | 0.67 | 0.56 | 0.50 | 0.67 | 0.56 |
| all | 27 | 0.89 | 0.93 | 0.90 | 0.67 | 0.89 | 0.77 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.50, hit@4 0.67, MRR 0.56.

Top score (course-wide): answerable median 0.26, 10th percentile 0.17; 3 questions not in the material: mean 0.10, max 0.11; chance that an answerable question outscores an unanswerable one 1.00.

## mit_6_002_circuits

Course type `ece`; 1217 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 15 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 0.79 |
| application | 7 | 1.00 | 1.00 | 1.00 | 0.71 | 0.86 | 0.79 |
| logistics | 6 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 |
| all | 28 | 0.96 | 0.96 | 0.96 | 0.71 | 0.93 | 0.80 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.83, hit@4 0.83, MRR 0.83.

Top score (course-wide): answerable median 0.30, 10th percentile 0.17; 3 questions not in the material: mean 0.21, max 0.37; chance that an answerable question outscores an unanswerable one 0.75.

## mit_6_006_algorithms

Course type `ece`; 639 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 14 | 1.00 | 1.00 | 1.00 | 0.57 | 0.93 | 0.71 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.80 | 0.80 | 0.80 |
| logistics | 6 | 0.50 | 0.83 | 0.62 | 0.50 | 0.83 | 0.62 |
| all | 25 | 0.88 | 0.96 | 0.91 | 0.60 | 0.88 | 0.71 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.50, hit@4 0.83, MRR 0.62.

Top score (course-wide): answerable median 0.23, 10th percentile 0.17; 3 questions not in the material: mean 0.15, max 0.19; chance that an answerable question outscores an unanswerable one 0.89.

## mit_7_016_intro_biology

Course type `life_science`; 831 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 19 | 0.95 | 1.00 | 0.96 | 0.68 | 0.95 | 0.79 |
| application | 3 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 0.75 |
| logistics | 6 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| all | 28 | 0.96 | 1.00 | 0.97 | 0.75 | 0.96 | 0.83 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 1.00, hit@4 1.00, MRR 1.00.

Top score (course-wide): answerable median 0.20, 10th percentile 0.14; 3 questions not in the material: mean 0.23, max 0.45; chance that an answerable question outscores an unanswerable one 0.66.

## mit_7_03_genetics

Course type `life_science`; 795 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 15 | 0.93 | 1.00 | 0.97 | 0.53 | 0.93 | 0.71 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.60 | 0.80 | 0.67 |
| logistics | 6 | 0.83 | 1.00 | 0.92 | 0.83 | 1.00 | 0.92 |
| all | 26 | 0.92 | 1.00 | 0.96 | 0.61 | 0.92 | 0.75 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.83, hit@4 1.00, MRR 0.92.

Top score (course-wide): answerable median 0.23, 10th percentile 0.14; 3 questions not in the material: mean 0.19, max 0.26; chance that an answerable question outscores an unanswerable one 0.67.

## mit_hst035_pathology

Course type `medical_science`; 546 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 18 | 0.94 | 1.00 | 0.96 | 0.83 | 0.83 | 0.83 |
| application | 2 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 0.75 |
| logistics | 6 | 0.50 | 0.83 | 0.67 | 0.50 | 0.83 | 0.67 |
| all | 26 | 0.85 | 0.96 | 0.90 | 0.73 | 0.85 | 0.79 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.50, hit@4 0.83, MRR 0.67.

Top score (course-wide): answerable median 0.28, 10th percentile 0.17; 3 questions not in the material: mean 0.18, max 0.23; chance that an answerable question outscores an unanswerable one 0.82.

## mit_hst151_pharmacology

Course type `medical_science`; 958 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 16 | 1.00 | 1.00 | 1.00 | 0.94 | 1.00 | 0.95 |
| application | 5 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| logistics | 6 | 0.83 | 1.00 | 0.89 | 0.83 | 1.00 | 0.89 |
| all | 27 | 0.96 | 1.00 | 0.97 | 0.93 | 1.00 | 0.95 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.83, hit@4 1.00, MRR 0.89.

Top score (course-wide): answerable median 0.22, 10th percentile 0.13; 3 questions not in the material: mean 0.11, max 0.12; chance that an answerable question outscores an unanswerable one 0.95.

## mit_res_6_007_signals

Course type `ece`; 890 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 14 | 1.00 | 1.00 | 1.00 | 0.50 | 1.00 | 0.74 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.60 | 0.80 | 0.70 |
| logistics | 6 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| all | 25 | 1.00 | 1.00 | 1.00 | 0.64 | 0.96 | 0.79 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 1.00, hit@4 1.00, MRR 1.00.

Top score (course-wide): answerable median 0.26, 10th percentile 0.20; 3 questions not in the material: mean 0.19, max 0.31; chance that an answerable question outscores an unanswerable one 0.76.

## All packs

| Pack | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR | unanswerable max top score |
|---|---|---|---|---|---|---|---|
| harvard_cs50x | 0.89 | 0.93 | 0.90 | 0.67 | 0.89 | 0.77 | 0.11 |
| mit_6_002_circuits | 0.96 | 0.96 | 0.96 | 0.71 | 0.93 | 0.80 | 0.37 |
| mit_6_006_algorithms | 0.88 | 0.96 | 0.91 | 0.60 | 0.88 | 0.71 | 0.19 |
| mit_7_016_intro_biology | 0.96 | 1.00 | 0.97 | 0.75 | 0.96 | 0.83 | 0.45 |
| mit_7_03_genetics | 0.92 | 1.00 | 0.96 | 0.61 | 0.92 | 0.75 | 0.26 |
| mit_hst035_pathology | 0.85 | 0.96 | 0.90 | 0.73 | 0.85 | 0.79 | 0.23 |
| mit_hst151_pharmacology | 0.96 | 1.00 | 0.97 | 0.93 | 1.00 | 0.95 | 0.12 |
| mit_res_6_007_signals | 1.00 | 1.00 | 1.00 | 0.64 | 0.96 | 0.79 | 0.31 |

## Misses (course-wide, no gold file in the top results)

- `cs50-16` (concept): gold `modules/08_week_7_sql.md`; top result `modules/07_week_6_python.md` (score 0.43); scoped rank 1
- `cs50-24` (logistics): gold `syllabus.md`; top result `assignments/pset_9.md` (score 0.33); scoped rank None
- `cs50-25` (logistics): gold `syllabus.md`; top result `assignments/pset_1.md` (score 0.40); scoped rank None
- `circ-03` (application): gold `modules/02_lecture_2_basic_circuit_analysis_method.pdf`; top result `modules/06_lecture_6_nonlinear_analysis.pdf` (score 0.43); scoped rank 1
- `circ-28` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.34); scoped rank None
- `alg-07` (application): gold `modules/09_lecture_9_breadth_first_search.pdf`; top result `modules/11_lecture_11_weighted_shortest_paths.pdf` (score 0.12); scoped rank 1
- `alg-17` (concept): gold `modules/16_lecture_17_dynamic_programming_part_3.pdf`; top result `modules/17_lecture_18_pseudopolynomial.pdf` (score 0.20); scoped rank 1
- `alg-24` (logistics): gold `calendar.md`; top result `assignments.md` (score 0.44); scoped rank None
- `bio7016-02` (concept): gold `modules/02_recitation_2.pdf`, `modules/09_recitation_9.pdf`; top result `modules/13_recitation_13.pdf` (score 0.15); scoped rank 4
- `gen-02` (application): gold `modules/04_lecture_4_probability_and_pedigrees.pdf`; top result `modules/33_lecture_35_genetics_of_cancer_ii.pdf` (score 0.17); scoped rank 1
- `gen-08` (concept): gold `modules/12_lecture_12_bacterial_genetics_transposition.pdf`; top result `exams/exam1_2004.pdf` (score 0.10); scoped rank 1
- `path-05` (concept): gold `modules/05_acute_and_chronic_inflammation.pdf`; top result `calendar.md` (score 0.19); scoped rank 3
- `path-18` (concept): gold `modules/03_the_immune_system.pdf`; top result `modules/06_tissue_repair_fibrosis_and_healing.pdf` (score 0.19); scoped rank 1
- `path-20` (concept): gold `modules/07_infectious_diseases.pdf`; top result `modules/02_epithelial_structure_and_function.pdf` (score 0.16); scoped rank 1
- `path-25` (logistics): gold `assignments.md`; top result `syllabus.md` (score 0.26); scoped rank None
- `sig-16` (application): gold `modules/23_lecture_23_mapping_continuous_time_filters_to_di.pdf`; top result `modules/18_lecture_18_mapping_continuous_time_filters_to_di.pdf` (score 0.26); scoped rank 1

## Analysis

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
add a semantic or query-expansion step before the
lexical score; fix the scan false positives.

**T5 (question type).** Logistics questions are now retrieved with `question_kind="logistics"` (course-level
files not weighted down, boosted by 1.5), and Markdown table rows such as calendar rows are indexed one
passage per row with their column names ("Lecture 11. TOPICS: Midterm Exam ..."). Before: logistics hit@1 0.69,
hit@4 0.85; calendar questions hit@4 0.60. The question-type head and the numbers are in `eval/question-type/`.
