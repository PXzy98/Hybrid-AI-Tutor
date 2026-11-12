# Demo and test courses

**Every test, evaluation and demo of v4 uses the eight open courses below** (decided 2026-11-12, after the
advisor suggested using open online course material). They replace ELG 5902, whose material needed
permission.

## First step: unpack

The repository stores one zip per course in `archives/` (about 88 MB). Unpack them once:

```bash
python scripts/fetch_open_courses.py unpack            # all eight, into data/demo_courses/<pack>/
python scripts/fetch_open_courses.py unpack harvard_cs50x   # or some of them
```

The unpacked folders are git-ignored; never commit them. Each has its own `README.md` (source, author,
license, file list) and a `manifest.json`.

## The courses

| Area | Pack | Course | Course type | Modules | Course-level material |
|---|---|---|---|---|---|
| Medical science | `mit_hst151_pharmacology` | MIT HST.151 Principles of Pharmacology (2005) | `medical_science` | 16 | syllabus, calendar, assignments, exams |
| Medical science | `mit_hst035_pathology` | MIT HST.035 Principle and Practice of Human Pathology (2003) | `medical_science` | 12 | syllabus, calendar, homework |
| Life science | `mit_7_03_genetics` | MIT 7.03 Genetics (2004) | `life_science` | 33 | syllabus, calendar, problem sets, exams |
| Life science | `mit_7_016_intro_biology` | MIT 7.016 Introductory Biology (2018) | `life_science` | 22 | syllabus, calendar, assignments, exams |
| ECE | `mit_6_002_circuits` | MIT 6.002 Circuits and Electronics (2007) | `ece` | 25 | syllabus, calendar, homework, quizzes and finals |
| ECE | `mit_res_6_007_signals` | MIT RES.6-007 Signals and Systems (2011) | `ece` | 26 | introduction, problem sets |
| Computer science | `mit_6_006_algorithms` | MIT 6.006 Introduction to Algorithms (2020) | `ece` | 19 | syllabus, calendar, problem sets, quizzes and final |
| Computer science | `harvard_cs50x` | Harvard CS50x Introduction to Computer Science (2026) | `ece` | 11 | syllabus, problem sets, final project |

- **Modules**: one lecture (or recitation) per module; PDFs, except CS50x (Markdown notes).
- **Course-level material** (`documents` in the manifest): uploaded to the course, not to a module. Used
  for logistics questions ("when is problem set 3 due?", "how is the course graded?") and as examples for
  instructor AI and quizzes. RES.6-007 has no syllabus or calendar page, and CS50x is self-paced (no
  calendar, no exams).
- **`instructor_only/`** (`instructor_only` in the manifest): solutions and answer keys. **Never upload
  them as course material**: the tutor would give students the answers. They are kept to check generated
  quizzes and answers.
- Computer science courses use the `ece` privacy profile (keys, tokens and repository URLs in code) until a
  separate profile is needed.

`general_medical_knowledge/` is the fictional v3 course (the five MedlinePlus topics). It stays for the v3
migration and its tests; new work uses the packs above. `elg5902/` holds no material.

## Using a pack

- **Layout**: `manifest.json` lists `documents` (course level), `modules` (one file each, `demo_note`) and
  `instructor_only`. `app.rag.demo_courses.stage_demo_course(pack, data_dir, course_id)` copies the
  documents and modules (never `instructor_only`) into the course retriever's layout
  (`courses/<course_id>/materials/...`, course-structure.md section 7).
- **Through the API** (demo scripts, T9): create the course with the pack's `course_type`, one module per
  manifest module in `module_order`, upload each module file to its module and each document to the course.
- **Test questions**: write them from these packs. They are public material, so they may be sent to hosted
  model APIs (rule 6 still applies: no student data).
- **Rebuilding**: `python scripts/fetch_open_courses.py download [pack ...]` downloads again (existing PDFs
  are kept), then `python scripts/fetch_open_courses.py archive [pack ...]` rewrites the zips. Commit only
  the zips. `backend/tests/test_open_course_packs.py` checks the zips: two courses per area, license and
  attribution, files present, solutions never staged.

## License

All eight courses are published by their authors under
[CC BY-NC-SA 4.0](https://creativecommons.org/licenses/by-nc-sa/4.0/):

- **non-commercial** use only. If the system is ever used commercially, these packs must be removed;
- credit the source (each pack's `README.md`, and the header of every converted Markdown file);
- what we change in them (for example converted Markdown) is shared under the same license;
- the authors and their institutions do not endorse this project.

PDFs are unchanged; web pages were converted to Markdown with navigation, images and videos removed.

## Known issues (to fix, not to work around)

Checked with the backend's own parser and `scan_document()` on 2026-11-12. The scan refuses 16 files as
containing student data; all are false positives, and they are refused on upload until the scan is fixed
(owner: Z, privacy):

| Course | Files | Reported as | Cause |
|---|---|---|---|
| HST.035 Pathology | modules 9, 10, 12; `assignments/homework5.pdf` | `STUDENT_ID` | ISBNs and other long numbers |
| RES.6-007 Signals | `assignments/problem_set_10.pdf` | `STUDENT_ID` | long numbers |
| HST.151 Pharmacology | modules 5, 6; `assignments/0310_oral_*.pdf`, `case_topic_desc.pdf`, `ps2005.pdf`; `exams/2005_final.pdf` | `HEALTH_DETAIL` | clinical teaching text and cases |
| 7.03 Genetics | `exams/exam3_2004.pdf` | `HEALTH_DETAIL` | genetics cases |
| 6.006 Algorithms | module 3 | `HEALTH_DETAIL` | teaching text |
| CS50x | `assignments/pset_5.md` | `GRADE` | grades in a programming exercise |
| CS50x | `assignments/pset_9.md` | `SECRET` | example keys in teaching code |

Left out on purpose: MIT 6.006 lecture 16 (no extractable text) and MIT 7.03 lecture 33 (three large
scanned files).
