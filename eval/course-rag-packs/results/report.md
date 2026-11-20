# Retrieval evaluation on the open course packs (S11)

Retrieval of k=4 passages by `IndexedCourseRetriever` (word and character TF-IDF), index built behind the real privacy scan. *Scoped*: restricted to the question's module plus the course-level files, as the product does when a module is chosen. *Course-wide*: `module_id=None`. A hit at rank r means the r-th passage comes from a gold file; hit@1, hit@k and MRR are over passages. Questions without a module (logistics, course-level) are the same in both modes.

## harvard_cs50x

Course type `computer_science`; 1467 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 12 | 1.00 | 1.00 | 1.00 | 0.83 | 1.00 | 0.89 |
| application | 10 | 1.00 | 1.00 | 1.00 | 0.90 | 1.00 | 0.93 |
| logistics | 6 | 0.67 | 0.83 | 0.75 | 0.67 | 0.83 | 0.75 |
| all | 28 | 0.93 | 0.96 | 0.95 | 0.82 | 0.96 | 0.88 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.67, hit@4 0.83, MRR 0.75.

Top score (course-wide): answerable median 0.33, 10th percentile 0.25; 3 questions not in the material: mean 0.11, max 0.14; chance that an answerable question outscores an unanswerable one 1.00.

## mit_6_002_circuits

Course type `ece`; 1217 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 15 | 1.00 | 1.00 | 1.00 | 0.87 | 1.00 | 0.92 |
| application | 7 | 1.00 | 1.00 | 1.00 | 0.86 | 1.00 | 0.91 |
| logistics | 6 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 | 0.83 |
| all | 28 | 0.96 | 0.96 | 0.96 | 0.86 | 0.96 | 0.90 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.83, hit@4 0.83, MRR 0.83.

Top score (course-wide): answerable median 0.36, 10th percentile 0.24; 3 questions not in the material: mean 0.24, max 0.46; chance that an answerable question outscores an unanswerable one 0.76.

## mit_6_006_algorithms

Course type `computer_science`; 639 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 14 | 1.00 | 1.00 | 1.00 | 0.57 | 0.86 | 0.69 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.80 | 0.80 | 0.80 |
| logistics | 6 | 0.67 | 0.83 | 0.71 | 0.67 | 0.83 | 0.71 |
| all | 25 | 0.92 | 0.96 | 0.93 | 0.64 | 0.84 | 0.71 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.67, hit@4 0.83, MRR 0.71.

Top score (course-wide): answerable median 0.28, 10th percentile 0.23; 3 questions not in the material: mean 0.14, max 0.22; chance that an answerable question outscores an unanswerable one 0.99.

## mit_7_016_intro_biology

Course type `life_science`; 831 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 19 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| application | 3 | 1.00 | 1.00 | 1.00 | 0.67 | 1.00 | 0.83 |
| logistics | 6 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| all | 28 | 1.00 | 1.00 | 1.00 | 0.96 | 1.00 | 0.98 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 1.00, hit@4 1.00, MRR 1.00.

Top score (course-wide): answerable median 0.30, 10th percentile 0.23; 3 questions not in the material: mean 0.23, max 0.41; chance that an answerable question outscores an unanswerable one 0.74.

## mit_7_03_genetics

Course type `life_science`; 795 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 15 | 0.87 | 1.00 | 0.92 | 0.80 | 0.87 | 0.83 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.60 | 1.00 | 0.77 |
| logistics | 6 | 0.67 | 0.83 | 0.75 | 0.67 | 0.83 | 0.75 |
| all | 26 | 0.85 | 0.96 | 0.90 | 0.73 | 0.89 | 0.80 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.67, hit@4 0.83, MRR 0.75.

Top score (course-wide): answerable median 0.35, 10th percentile 0.21; 3 questions not in the material: mean 0.31, max 0.51; chance that an answerable question outscores an unanswerable one 0.64.

## mit_hst035_pathology

Course type `medical_science`; 546 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 18 | 1.00 | 1.00 | 1.00 | 0.89 | 1.00 | 0.93 |
| application | 2 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| logistics | 6 | 0.50 | 0.83 | 0.67 | 0.50 | 0.83 | 0.67 |
| all | 26 | 0.89 | 0.96 | 0.92 | 0.81 | 0.96 | 0.88 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.50, hit@4 0.83, MRR 0.67.

Top score (course-wide): answerable median 0.37, 10th percentile 0.21; 3 questions not in the material: mean 0.20, max 0.32; chance that an answerable question outscores an unanswerable one 0.89.

## mit_hst151_pharmacology

Course type `medical_science`; 958 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 16 | 1.00 | 1.00 | 1.00 | 0.94 | 1.00 | 0.97 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.80 | 1.00 | 0.90 |
| logistics | 6 | 0.83 | 1.00 | 0.89 | 0.83 | 1.00 | 0.89 |
| all | 27 | 0.96 | 1.00 | 0.97 | 0.89 | 1.00 | 0.94 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 0.83, hit@4 1.00, MRR 0.89.

Top score (course-wide): answerable median 0.28, 10th percentile 0.21; 3 questions not in the material: mean 0.14, max 0.19; chance that an answerable question outscores an unanswerable one 0.99.

## mit_res_6_007_signals

Course type `ece`; 890 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 14 | 1.00 | 1.00 | 1.00 | 0.71 | 1.00 | 0.83 |
| application | 5 | 1.00 | 1.00 | 1.00 | 0.80 | 0.80 | 0.80 |
| logistics | 6 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| all | 25 | 1.00 | 1.00 | 1.00 | 0.80 | 0.96 | 0.87 |

Logistics questions asked from inside a module (the middle one): n=6, hit@1 1.00, hit@4 1.00, MRR 1.00.

Top score (course-wide): answerable median 0.34, 10th percentile 0.25; 3 questions not in the material: mean 0.21, max 0.42; chance that an answerable question outscores an unanswerable one 0.75.

## All packs

| Pack | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR | unanswerable max top score |
|---|---|---|---|---|---|---|---|
| harvard_cs50x | 0.93 | 0.96 | 0.95 | 0.82 | 0.96 | 0.88 | 0.14 |
| mit_6_002_circuits | 0.96 | 0.96 | 0.96 | 0.86 | 0.96 | 0.90 | 0.46 |
| mit_6_006_algorithms | 0.92 | 0.96 | 0.93 | 0.64 | 0.84 | 0.71 | 0.22 |
| mit_7_016_intro_biology | 1.00 | 1.00 | 1.00 | 0.96 | 1.00 | 0.98 | 0.41 |
| mit_7_03_genetics | 0.85 | 0.96 | 0.90 | 0.73 | 0.89 | 0.80 | 0.51 |
| mit_hst035_pathology | 0.89 | 0.96 | 0.92 | 0.81 | 0.96 | 0.88 | 0.32 |
| mit_hst151_pharmacology | 0.96 | 1.00 | 0.97 | 0.89 | 1.00 | 0.94 | 0.19 |
| mit_res_6_007_signals | 1.00 | 1.00 | 1.00 | 0.80 | 0.96 | 0.87 | 0.42 |

## Misses (course-wide, no gold file in the top results)

- `cs50-24` (logistics): gold `syllabus.md`; top result `assignments/pset_9.md` (score 0.24); scoped rank None
- `circ-28` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.37); scoped rank None
- `alg-07` (application): gold `modules/09_lecture_9_breadth_first_search.pdf`; top result `modules/11_lecture_11_weighted_shortest_paths.pdf` (score 0.20); scoped rank 1
- `alg-16` (concept): gold `modules/06_lecture_6_binary_trees_part_1.pdf`; top result `modules/07_lecture_7_binary_trees_part_2_avl.pdf` (score 0.26); scoped rank 1
- `alg-17` (concept): gold `modules/16_lecture_17_dynamic_programming_part_3.pdf`; top result `modules/17_lecture_18_pseudopolynomial.pdf` (score 0.27); scoped rank 1
- `alg-24` (logistics): gold `calendar.md`; top result `assignments.md` (score 0.56); scoped rank None
- `gen-08` (concept): gold `modules/12_lecture_12_bacterial_genetics_transposition.pdf`; top result `modules/19_lecture_19_eukaryotic_genes_and_genomes_i.pdf` (score 0.14); scoped rank 3
- `gen-20` (concept): gold `modules/01_lecture_1_physical_structure_of_the_gene.pdf`; top result `calendar.md` (score 0.53); scoped rank 2
- `gen-26` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.57); scoped rank None
- `path-25` (logistics): gold `assignments.md`; top result `syllabus.md` (score 0.32); scoped rank None
- `sig-10` (application): gold `modules/17_lecture_17_interpolation.pdf`; top result `modules/16_lecture_16_sampling.pdf` (score 0.30); scoped rank 1

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

**S14 (paraphrases, misspellings, semantic step).** The tables above are from the run after S14 (2026-11-20);
the analysis text before this paragraph describes the run of 2026-11-12. Retrieval now stems words, adds
corrected spellings and logistics synonyms to the question, weights homework and exam files by 0.8 in
course-wide concept questions and adds the router's sentence encoder as a semantic score. Over the eight packs
course-wide hit@1 went 0.71 -> 0.82 and hit@4 0.93 -> 0.95, scoped hit@1 0.93 -> 0.94 and hit@4 stays 0.98.
Five questions fell out of the top 4 (listed in `s14-comparison.md`). The paraphrase and misspelling set is in
`paraphrase_questions/` with its report in `results/paraphrase/`; before and after in `results/s14-comparison.md`.
