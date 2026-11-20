# Retrieval evaluation on the open course packs (S14, paraphrased and misspelled questions)

Retrieval of k=4 passages by `IndexedCourseRetriever` (word and character TF-IDF), index built behind the real privacy scan. *Scoped*: restricted to the question's module plus the course-level files, as the product does when a module is chosen. *Course-wide*: `module_id=None`. A hit at rank r means the r-th passage comes from a gold file; hit@1, hit@k and MRR are over passages. Questions without a module (logistics, course-level) are the same in both modes.

## harvard_cs50x

Course type `computer_science`; 1467 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 16 | 0.94 | 1.00 | 0.97 | 0.88 | 0.94 | 0.91 |
| application | 0 | - | - | - | - | - | - |
| logistics | 16 | 0.38 | 0.56 | 0.45 | 0.38 | 0.56 | 0.45 |
| all | 32 | 0.66 | 0.78 | 0.71 | 0.62 | 0.75 | 0.68 |

| Variant | n | scoped hit@1 | scoped hit@4 | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|
| misspelled | 16 | 0.69 | 0.75 | 0.69 | 0.75 | 0.71 |
| paraphrase | 16 | 0.62 | 0.81 | 0.56 | 0.75 | 0.65 |

Logistics questions asked from inside a module (the middle one): n=16, hit@1 0.38, hit@4 0.56, MRR 0.45.

Top score (course-wide): answerable median 0.25, 10th percentile 0.17; 0 questions not in the material: mean -, max -; chance that an answerable question outscores an unanswerable one -.

## mit_6_002_circuits

Course type `ece`; 1217 passages; index built whole course.

| Type | n | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|---|
| concept | 16 | 1.00 | 1.00 | 1.00 | 0.44 | 0.94 | 0.66 |
| application | 0 | - | - | - | - | - | - |
| logistics | 16 | 0.69 | 0.81 | 0.73 | 0.69 | 0.81 | 0.73 |
| all | 32 | 0.84 | 0.91 | 0.87 | 0.56 | 0.88 | 0.70 |

| Variant | n | scoped hit@1 | scoped hit@4 | course-wide hit@1 | course-wide hit@4 | course-wide MRR |
|---|---|---|---|---|---|---|
| misspelled | 16 | 0.81 | 0.94 | 0.62 | 0.94 | 0.77 |
| paraphrase | 16 | 0.88 | 0.88 | 0.50 | 0.81 | 0.63 |

Logistics questions asked from inside a module (the middle one): n=16, hit@1 0.69, hit@4 0.81, MRR 0.73.

Top score (course-wide): answerable median 0.32, 10th percentile 0.20; 0 questions not in the material: mean -, max -; chance that an answerable question outscores an unanswerable one -.

## All packs

| Pack | scoped hit@1 | scoped hit@4 | scoped MRR | course-wide hit@1 | course-wide hit@4 | course-wide MRR | unanswerable max top score |
|---|---|---|---|---|---|---|---|
| harvard_cs50x | 0.66 | 0.78 | 0.71 | 0.62 | 0.75 | 0.68 | - |
| mit_6_002_circuits | 0.84 | 0.91 | 0.87 | 0.56 | 0.88 | 0.70 | - |

## Misses (course-wide, no gold file in the top results)

- `cs50-p01b` (logistics): gold `syllabus.md`; top result `assignments/pset_0.md` (score 0.18); scoped rank None
- `cs50-p02a` (logistics): gold `syllabus.md`; top result `assignments/pset_7.md` (score 0.23); scoped rank None
- `cs50-p02b` (logistics): gold `syllabus.md`; top result `assignments/pset_1.md` (score 0.23); scoped rank None
- `cs50-p04b` (logistics): gold `syllabus.md`; top result `assignments/pset_2.md` (score 0.18); scoped rank None
- `cs50-p05a` (logistics): gold `syllabus.md`; top result `assignments/pset_9.md` (score 0.37); scoped rank None
- `cs50-p05b` (logistics): gold `syllabus.md`; top result `assignments/pset_1.md` (score 0.31); scoped rank None
- `cs50-p07a` (logistics): gold `syllabus.md`; top result `assignments/pset_5.md` (score 0.12); scoped rank None
- `cs50-p13a` (concept): gold `modules/06_week_5_data_structures.md`; top result `modules/08_week_7_sql.md` (score 0.11); scoped rank 2
- `circ-p01a` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.58); scoped rank None
- `circ-p01b` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.22); scoped rank None
- `circ-p02a` (logistics): gold `calendar.md`; top result `syllabus.md` (score 0.37); scoped rank None
- `circ-p11a` (concept): gold `modules/04_lecture_4_the_digital_abstraction.pdf`; top result `modules/05_lecture_5_inside_the_digital_gate.pdf` (score 0.39); scoped rank 1
