"""v5 V2: class statistics for the instructor and usage counts for the admin. Counts only; a count that fewer
than the minimum group contributed is null. Fictional data; the models are fakes."""
import json
from datetime import UTC, datetime, timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.pipeline.steps.generate import LOCAL_CAPABILITY_NOTE
from app.storage.models import CourseMember, RequestLog
from tests.test_ask_v2 import PASSWORD, V2, World, _login

MIN = 5  # the floor; the fixture's setting is lower (3) and the floor wins
NAMES = ("cara", "dan", "eve", "fay", "gus", "hal")  # with alice: seven students of the course


@pytest.fixture
def world(make_client):
    with make_client({"learner": {"class_summary_min_group": 3}}) as client:
        w = World(client)  # alice is enrolled
        for name in NAMES:
            account, _ = w.services.accounts.create_student(name, name.title())
            w.students[name] = w.services.accounts.set_password(account.id, PASSWORD, must_change=False)
            with Session(w.services.engine) as db:
                db.add(CourseMember(course_id=w.course, account_id=account.id, role="student",
                                    status="active"))
                db.commit()
        yield w


def _ask(world, name: str, module_id: int | None = None) -> None:
    body = {"question": "What is Ohm's law?", **({"module_id": module_id} if module_id else {})}
    r = _login(world.app, name).post(f"{world.url}/ask", json=body)
    assert r.status_code == 200, r.text


def _stats(world) -> dict:
    return world.prof.get(f"{world.url}/statistics").json()


def test_course_statistics_count_questions_and_hide_small_groups(world):
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    _ask(world, "alice", world.module)
    _ask(world, "gus")  # one student about the whole course: hidden
    stats = _stats(world)
    assert stats["min_group"] == MIN and stats["students_enrolled"] == 7  # the floor, not the setting (3)
    assert stats["active_students"] == 6 and stats["active_students_7d"] == 6
    assert stats["questions_total"] == 7 and stats["questions_7d"] == 7
    assert stats["local_share"] == 1.0
    modules = {m["module_id"]: m for m in stats["modules"]}
    assert modules[None]["questions"] is None
    # the total is shown and "whole course" is hidden: Circuits (6) would give it by subtraction, so it is
    # hidden as well
    assert modules[world.module]["questions"] is None and modules[world.module]["title"] == "Circuits"
    _assert_no_hidden_cell_derivable(stats)
    assert len(stats["weeks"]) == 8 and stats["weeks"][-1] == {
        "week_start": stats["weeks"][-1]["week_start"], "questions": 7, "students": 6}
    assert all(w["questions"] == 0 and w["students"] == 0 for w in stats["weeks"][:-1])  # nobody: 0
    body = json.dumps(stats)
    for name in ("alice", "cara", "dan", "eve", "fay", "gus"):  # no student is named or identified
        assert world.students[name].student_id not in body and name.title() not in body


def test_a_hidden_row_cannot_be_derived_by_subtraction(world):
    """With the total shown, never exactly one row of a breakdown is hidden (two or none)."""
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    _ask(world, "gus")
    stats = _stats(world)
    assert stats["questions_total"] == 6
    _assert_no_hidden_cell_derivable(stats)
    for rows in (stats["modules"], stats["weeks"]):
        assert sum(r["questions"] is None for r in rows) != 1
    _ask(world, "hal")  # a second student in the small row: still hidden, still not alone
    stats = _stats(world)
    assert next(m for m in stats["modules"] if m["module_id"] is None)["questions"] is None
    assert sum(m["questions"] is None for m in stats["modules"]) != 1


def test_everything_is_hidden_below_the_minimum_group(world):
    for name in ("alice", "cara", "dan", "eve"):  # 4 students: the setting says 3, the floor 5
        _ask(world, name, world.module)
    stats = _stats(world)
    assert stats["active_students"] is None and stats["active_students_7d"] is None
    assert stats["questions_total"] is None and stats["questions_7d"] is None and stats["local_share"] is None
    assert next(m for m in stats["modules"] if m["module_id"] == world.module)["questions"] is None
    assert stats["weeks"][-1]["questions"] is None and stats["weeks"][-1]["students"] is None


def test_nothing_asked_shows_zeros(world):
    stats = _stats(world)
    assert stats["active_students"] == 0 and stats["questions_total"] == 0 and stats["questions_7d"] == 0
    assert all(m["questions"] == 0 for m in stats["modules"])
    assert all(w["questions"] == 0 and w["students"] == 0 for w in stats["weeks"])


def test_removing_a_member_changes_no_count(world):
    """An instructor who removes a student and reads the statistics again must not learn that student's
    activity by subtraction: the counts stay the same, only the students enrolled change."""
    for name in ("alice", "cara", "dan", "eve", "fay", "gus"):
        _ask(world, name, world.module)
    _ask(world, "cara", world.module)
    before = _stats(world)
    with Session(world.services.engine) as db:  # cara leaves the course
        db.delete(db.exec(select(CourseMember).where(CourseMember.account_id == world.students["cara"].id,
                                                     CourseMember.course_id == world.course)).one())
        db.commit()
    after = _stats(world)
    assert after["students_enrolled"] == before["students_enrolled"] - 1
    unchanged = [k for k in before if k != "students_enrolled"]
    assert {k: after[k] for k in unchanged} == {k: before[k] for k in unchanged}
    assert after["questions_total"] == 7 and after["active_students"] == 6


def _published_quiz(world) -> int:
    quiz = world.prof.post(f"{world.url}/quizzes", json={
        "title": "Week 1", "module_id": world.module,
        "questions": [{"kind": "true_false", "kc": None, "stem": "A resistor stores charge.", "answer": 1,
                       "explanation": "A capacitor does."}]}).json()
    world.prof.patch(f"{world.url}/quizzes/{quiz['id']}", json={"status": "published"})
    return quiz["id"]


def test_quiz_attempts_and_averages_need_the_minimum_group_and_are_coarse(world):
    quiz = _published_quiz(world)
    right = {"cara", "dan"}  # 2 of 7 are right: 0.2857
    for i, name in enumerate(("alice", *NAMES)):
        _login(world.app, name).post(f"{world.url}/quizzes/{quiz}/attempt",
                                     json={"answers": [1 if name in right else 0]})
        row = next(q for q in _stats(world)["quizzes"] if q["quiz_id"] == quiz)
        assert row["attempts"] == (i + 1 if i + 1 >= MIN else None)
        if i + 1 < MIN:
            assert row["mean_score"] is None
    assert row == {"quiz_id": quiz, "title": "Week 1", "attempts": 7, "mean_score": 0.3}  # not 0.286


def test_a_quiz_nobody_took_shows_zero_attempts(world):
    quiz = _published_quiz(world)
    row = next(q for q in _stats(world)["quizzes"] if q["quiz_id"] == quiz)
    assert row["attempts"] == 0 and row["mean_score"] is None


def test_the_admin_sees_the_counts_of_every_course(world):
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    world.services.accounts.create_admin("root", PASSWORD, must_change=False)
    stats = _login(world.app, "root").get(f"{V2}/admin/statistics").json()
    row = next(c for c in stats["courses"] if c["course_id"] == world.course)
    assert row == {"course_id": world.course, "code": "ELG 5902", "title": "Fictional course",
                   "status": "active", "students_enrolled": 7, "active_students_7d": 5, "questions_total": 5,
                   "questions_7d": 5}
    assert stats["min_group"] == MIN and stats["students_enrolled"] >= 7 and stats["questions_total"] == 5
    assert stats["active_students_7d"] == 5
    demo = next(c for c in stats["courses"] if c["course_id"] == world.demo)
    assert demo["questions_total"] == 0 and demo["active_students_7d"] == 0  # nobody asked there: 0


def test_a_hidden_course_is_not_derived_from_the_system_total(world):
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    world.services.accounts.create_admin("root", PASSWORD, must_change=False)
    root = _login(world.app, "root")
    other = root.post(f"{V2}/courses", json={"code": "ELG 5000", "title": "Fictional", "course_type": "ece"}
                      ).json()["id"]
    with Session(world.services.engine) as db:
        db.add(CourseMember(course_id=other, account_id=world.students["gus"].id, role="student",
                            status="active"))
        db.commit()
    _log(world, "gus", other, "local")
    _log(world, "gus", other, "local")
    stats = root.get(f"{V2}/admin/statistics").json()
    rows = {c["course_id"]: c for c in stats["courses"]}
    assert stats["questions_total"] == 7  # 6 different students
    assert rows[other]["questions_total"] is None and rows[other]["active_students_7d"] is None
    assert rows[world.course]["questions_total"] is None  # the smallest shown row goes with it
    assert rows[world.demo]["questions_total"] == 0
    assert rows[world.course]["active_students_7d"] == 5
    _assert_admin_sums(stats)


def _assert_admin_sums(stats: dict, *, older=(0, False)) -> None:
    """The system total is the sum of the course totals; the 7-day column likewise; per course and in total
    the total is the 7-day count plus the older ones. No sum has exactly one unknown cell, unless that is
    a remainder that is not small."""
    courses = stats["courses"]
    sums = [[stats["questions_total"], *(c["questions_total"] for c in courses)],
            [stats["questions_7d"], *(c["questions_7d"] for c in courses)]]
    for cells in sums:
        assert sum(c is None for c in cells) != 1, cells
    # total = 7 days + older: the older ones (here all in one course) are a cell that is not on screen
    for total, recent in [(stats["questions_total"], stats["questions_7d"]),
                          *((c["questions_total"], c["questions_7d"]) for c in courses)]:
        gaps = (total is None) + (recent is None) + (older[0] > 0 and total != 0)
        assert gaps != 1 or not older[1] or total == 0, (total, recent)


def test_questions_older_than_a_week_are_not_derived_from_the_total(world):
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    stats = _stats(world)
    assert stats["questions_total"] == 5 and stats["questions_7d"] == 5  # nothing older: both shown
    old = datetime.now(UTC) - timedelta(days=30)
    _log(world, "gus", world.course, "local", created_at=old, topic="circuits")
    stats = _stats(world)  # one student asked 30 days ago: total minus the last 7 days would show it
    _assert_no_hidden_cell_derivable(stats, older=(1, True))
    assert stats["questions_total"] is None or stats["questions_7d"] is None


def _assert_no_hidden_cell_derivable(stats: dict, *, older=(0, False), before=(0, False), other=(0, False)):
    """Every sum of the released course counts (total = last 7 days + older, = weeks + before the window,
    = modules + other topics) has no or at least two unknown cells, unless the only unknown one is a
    remainder that is not on screen and not small. Each remainder is (questions, small group)."""
    unknown_rest = {"older": older, "before": before, "other": other}
    sums = {"older": [stats["questions_7d"]], "before": [w["questions"] for w in stats["weeks"]],
            "other": [m["questions"] for m in stats["modules"]]}
    for name, cells in sums.items():
        gaps = [c is None for c in cells] + [unknown_rest[name][0] > 0]
        gaps.append(stats["questions_total"] is None)
        if sum(gaps) == 1:
            assert unknown_rest[name][0] > 0 and not unknown_rest[name][1], name


def test_a_small_older_group_is_not_derived_from_total_weeks_or_modules(world):
    """Five students asked in the last 7 days, a sixth 30 days ago, all about one module: hiding the total
    alone would let the weeks or modules give the sixth student's question by subtraction."""
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    _log(world, "gus", world.course, "local", created_at=datetime.now(UTC) - timedelta(days=30),
         topic="circuits")
    stats = _stats(world)
    _assert_no_hidden_cell_derivable(stats, older=(1, True))
    assert not (stats["questions_total"] == 6 and stats["questions_7d"] == 5)
    module = next(m for m in stats["modules"] if m["module_id"] == world.module)
    assert not (stats["questions_7d"] == 5 and module["questions"] == 6)


def _log(world, name: str, course_id: int, target: str, warnings: list[str] | None = None, *,
         created_at: datetime | None = None, topic: str = "M1") -> None:
    with Session(world.services.engine) as db:
        row = RequestLog(request_id="r", session_id="s", student_id=world.students[name].student_id,
                         course_id=course_id, topic=topic, sanitized_question="[question]", target=target,
                         warnings=warnings or [])
        if created_at:
            row.created_at = created_at
        db.add(row)
        db.commit()


def test_a_cloud_question_answered_locally_counts_as_local(world):
    """A question routed to the cloud that fell back to the local model was answered locally."""
    _log(world, "alice", world.course, "cloud", ["no cloud connection", LOCAL_CAPABILITY_NOTE])
    _log(world, "cara", world.course, "cloud", [LOCAL_CAPABILITY_NOTE])
    _log(world, "dan", world.course, "cloud")
    _log(world, "eve", world.course, "local")
    _log(world, "fay", world.course, "local")
    assert _stats(world)["local_share"] == 0.8


def test_system_totals_need_the_minimum_group_of_different_students(world):
    """One student asking in several courses is one contributor: the system totals stay hidden."""
    world.services.accounts.create_admin("root", PASSWORD, must_change=False)
    root = _login(world.app, "root")
    for i in range(MIN):
        course = root.post(f"{V2}/courses", json={"code": f"ELG {5000 + i}", "title": "Fictional",
                                                   "course_type": "ece"})
        assert course.status_code == 201, course.text
        with Session(world.services.engine) as db:
            db.add(CourseMember(course_id=course.json()["id"], account_id=world.students["alice"].id,
                                role="student", status="active"))
            db.commit()
        _log(world, "alice", course.json()["id"], "local")
    stats = root.get(f"{V2}/admin/statistics").json()
    assert stats["active_students_7d"] is None  # one student, however many courses
    assert stats["questions_total"] is None and stats["questions_7d"] is None
    assert all(c["active_students_7d"] is None for c in stats["courses"] if c["questions_total"] is None)


def test_who_may_read_the_statistics(world):
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    other = _login(world.app, "other")
    assert other.get(f"{world.url}/statistics").status_code == 404  # another course's instructor
    assert _login(world.app, "alice").get(f"{world.url}/statistics").status_code in (403, 404)  # a student
    assert _login(world.app, "bob").get(f"{world.url}/statistics").status_code in (403, 404)  # not enrolled
    anonymous = TestClient(world.app)
    assert anonymous.get(f"{world.url}/statistics").status_code == 401
    assert other.get(f"{V2}/admin/statistics").status_code == 403  # instructors are not admins
    assert _login(world.app, "alice").get(f"{V2}/admin/statistics").status_code == 403
    assert anonymous.get(f"{V2}/admin/statistics").status_code == 401


def test_a_small_older_group_in_a_course_is_not_derived_in_the_admin_view(world):
    """The same scenario for the admin: the course total, the system total and the 7-day columns."""
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    _log(world, "gus", world.course, "local", created_at=datetime.now(UTC) - timedelta(days=30),
         topic="circuits")
    world.services.accounts.create_admin("root", PASSWORD, must_change=False)
    stats = _login(world.app, "root").get(f"{V2}/admin/statistics").json()
    _assert_admin_sums(stats, older=(1, True))
    row = next(c for c in stats["courses"] if c["course_id"] == world.course)
    assert not (stats["questions_total"] == 6 and stats["questions_7d"] == 5)
    assert not (row["questions_total"] == 6 and row["questions_7d"] == 5)
