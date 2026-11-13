"""T5 in retrieval: calendar tables as row passages, and logistics questions preferring course-level files.
Fictional course material only."""
import pytest

from app.rag.course_retriever import (
    COURSE_LEVEL_WEIGHT,
    LOGISTICS_COURSE_LEVEL_BOOST,
    IndexedCourseRetriever,
)
from app.rag.tables import split_tables

CALENDAR = """# Fictional Studies 101: calendar

> Source: invented for the tests.

| LEC # | TOPICS | KEY DATES |

| 1 | Welcome and course organisation | |

| 2 | Glimmerwave sampling | Problem set 1 out |

| 3 | Quartzzyme kinetics | Problem set 1 due |

| 4 | Midterm Exam | |
"""

MARKDOWN_TABLE = """## Grading

| Component | Weight |
|---|---|
| Homework | 30% |
| Final exam | 70% |

Closing words.
"""


def _material(root, cid, module, name, body):
    path = root / "courses" / str(cid) / "materials" / str(module) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")


# ----------------------------------------------------------------------------- split_tables


def test_calendar_rows_carry_their_column_names():
    text, rows = split_tables(CALENDAR)
    assert [r for _, r in rows] == [
        "Lecture 1. TOPICS: Welcome and course organisation",
        "Lecture 2. TOPICS: Glimmerwave sampling. KEY DATES: Problem set 1 out",
        "Lecture 3. TOPICS: Quartzzyme kinetics. KEY DATES: Problem set 1 due",
        "Lecture 4. TOPICS: Midterm Exam",
    ]
    assert {heading for heading, _ in rows} == {"Fictional Studies 101: calendar"}
    assert "|" not in text and "invented for the tests" in text  # the rest of the file stays text


def test_table_with_a_separator_row():
    text, rows = split_tables(MARKDOWN_TABLE)
    assert rows == [("Grading", "Component: Homework. Weight: 30%"),
                    ("Grading", "Component: Final exam. Weight: 70%")]
    assert "Closing words." in text and "Homework" not in text


def test_session_abbreviation_and_counter_values():
    _, rows = split_tables("| SES # | TOPICS |\n| 12 | Review |\n| L7 | Lab |\n| Intro | Notes |")
    assert [r for _, r in rows] == ["Session 12. TOPICS: Review", "Session L7. TOPICS: Lab",
                                    "Session: Intro. TOPICS: Notes"]


def test_text_without_tables_and_single_row_tables_are_unchanged():
    plain = "# Title\nNo table here | with a pipe.\n"
    assert split_tables(plain) == (plain.rstrip("\n"), [])
    only_header = "| A | B |\nafter"
    assert split_tables(only_header) == (only_header, [])


def test_a_long_row_is_split_by_cell_and_repeats_its_first_cell():
    cells = [f"Reading {n}: " + "word " * 25 for n in range(8)]
    _, rows = split_tables("| LEC # | " + " | ".join(f"C{n}" for n in range(8)) + " |\n| 9 | "
                           + " | ".join(cells) + " |")
    assert len(rows) > 1 and all(len(r) <= 650 for _, r in rows)
    assert all(r.startswith("Lecture 9") for _, r in rows)


# ------------------------------------------------------------- calendar rows in the index


def test_calendar_questions_find_their_row(tmp_path):
    _material(tmp_path, 1, "_course", "calendar.md", CALENDAR)
    _material(tmp_path, 1, "_course", "syllabus.md", "# Syllabus\nThis course has a final exam and homework.")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    rag.rebuild(1)
    midterm = rag.retrieve(1, None, "which lecture is the midterm exam?", 2)
    assert midterm[0].source.endswith("calendar.md")
    assert midterm[0].text == "Fictional Studies 101: calendar\nLecture 4. TOPICS: Midterm Exam"
    due = rag.retrieve(1, None, "when is problem set 1 due", 1)[0]
    assert "Lecture 3" in due.text and "KEY DATES: Problem set 1 due" in due.text
    calendar = [p for p in rag._snapshot(1).passages if p.source.endswith("calendar.md")]
    assert len(calendar) == 5  # the introduction and 4 rows


# ------------------------------------------------------------ logistics: course-level first


def _same_text_course(tmp_path):
    same = "Glimmerwave sampling explained with a worked example."
    _material(tmp_path, 303, "_course", "homework.md", f"# Homework\n{same}")
    _material(tmp_path, 303, 9, "lecture.md", f"# Lecture\n{same}")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    rag.rebuild(303)
    return rag


def test_logistics_questions_do_not_weight_course_level_files_down(tmp_path):
    rag = _same_text_course(tmp_path)
    homework = "course/303/_course/homework.md"
    course_wide = {x.source: x.score for x in rag.retrieve(303, None, "Glimmerwave sampling", 2)}
    concept = rag.retrieve(303, 9, "Glimmerwave sampling", 2)
    logistics = rag.retrieve(303, 9, "Glimmerwave sampling", 2, question_kind="logistics")
    assert [x.source for x in concept][0] == "course/303/9/lecture.md"
    assert {x.source: x.score for x in concept}[homework] == pytest.approx(
        course_wide[homework] * COURSE_LEVEL_WEIGHT, abs=1e-5)
    assert [x.source for x in logistics][0] == homework  # the course-level file now comes first
    assert {x.source: x.score for x in logistics}[homework] == pytest.approx(
        course_wide[homework] * LOGISTICS_COURSE_LEVEL_BOOST, abs=1e-5)
    module_score = {x.source: x.score for x in logistics}["course/303/9/lecture.md"]
    assert module_score == pytest.approx(course_wide["course/303/9/lecture.md"], abs=1e-5)  # unchanged


def test_logistics_boost_applies_to_course_wide_questions_too(tmp_path):
    rag = _same_text_course(tmp_path)
    kinds = {kind: rag.retrieve(303, None, "Glimmerwave sampling", 2, question_kind=kind)
             for kind in ("concept", "logistics")}
    assert kinds["logistics"][0].source.endswith("homework.md")
    assert kinds["logistics"][0].score > kinds["concept"][0].score


def test_default_kind_is_concept(tmp_path):
    rag = _same_text_course(tmp_path)
    assert rag.retrieve(303, 9, "Glimmerwave sampling", 2) == rag.retrieve(
        303, 9, "Glimmerwave sampling", 2, question_kind="concept")


# ------------------------------------------------------------- regressions (review of PR #80)


def test_escaped_pipes_and_code_spans_stay_inside_their_cell():
    text = "| Task | When |\n|---|---|\n| Compute a \\| b | Friday 5pm |\n| Run `x | y` | Monday |"
    _, rows = split_tables(text)
    assert [r for _, r in rows] == ["Task: Compute a | b. When: Friday 5pm",
                                    "Task: Run `x | y`. When: Monday"]


def test_two_tables_separated_by_a_blank_line_keep_their_own_headers():
    text = ("| Week | Topic |\n|---|---|\n| 1 | Sets |\n\n"
            "| Item | Weight | Notes |\n|---|---|---|\n| Quiz | 10% | best of 3 |")
    _, rows = split_tables(text)
    assert [r for _, r in rows] == ["Week 1. Topic: Sets", "Item: Quiz. Weight: 10%. Notes: best of 3"]


def test_calendar_rows_without_separator_still_use_the_first_row_as_header():
    _, rows = split_tables("| LEC # | TOPICS |\n\n| 1 | Intro |\n\n| 2 | Limits |")
    assert [r for _, r in rows] == ["Lecture 1. TOPICS: Intro", "Lecture 2. TOPICS: Limits"]


def test_no_cell_is_dropped_when_a_row_is_longer_or_shorter_than_the_header():
    _, rows = split_tables("| A | B |\n|---|---|\n| 1 | two | three | four |\n| solo | |")
    assert [r for _, r in rows] == ["A 1. B: two | three | four", "A: solo"]
