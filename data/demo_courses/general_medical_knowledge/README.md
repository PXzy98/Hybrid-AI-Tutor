# Demonstration course materials

All materials here are original, fictional example documents for functional testing. They are not a real university syllabus, not professor-provided lecture notes and not medical approval.

The existing MedlinePlus source snapshots remain in data/medical_rag/raw/. They are not copied into this folder; verify licensing/attribution before external distribution.

The Z4 course importer can map manifest module codes to database IDs once it is implemented. Do not upload them into a real student-facing class before instructor and medical review.

## Loading the pack into a course

`app.rag.demo_courses.stage_demo_course(pack, data_root, course_id)` copies the course-level documents to
`courses/<course_id>/materials/_course/` and each module's note plus its bundled MedlinePlus reading to
`courses/<course_id>/materials/<module_id>/`, the layout `IndexedCourseRetriever.rebuild` indexes.
`backend/tests/test_s5_demo_course_materials.py` checks that the syllabus and project brief are retrieved.
