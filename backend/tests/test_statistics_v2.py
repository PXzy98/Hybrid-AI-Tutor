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


def test_questions_older_than_a_week_are_not_derived_from_the_total(world):
    for name in ("alice", "cara", "dan", "eve", "fay"):
        _ask(world, name, world.module)
    stats = _stats(world)
    assert stats["questions_total"] == 5 and stats["questions_7d"] == 5  # nothing older: both shown
    old = datetime.now(UTC) - timedelta(days=30)
    _log(world, "gus", world.course, "local", created_at=old)
    stats = _stats(world)  # one student asked 30 days ago: total minus the last 7 days would show it
    assert stats["questions_7d"] == 5 and stats["questions_total"] is None


def _log(world, name: str, course_id: int, target: str, warnings: list[str] | None = None, *,
         created_at: datetime | None = None) -> None:
    with Session(world.services.engine) as db:
        row = RequestLog(request_id="r", session_id="s", student_id=world.students[name].student_id,
                         course_id=course_id, topic="M1", sanitized_question="[question]", target=target,
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
