"""v5 V2: class statistics for the instructor and usage counts for the admin. Counts only; a count that fewer
than the minimum group contributed is null. Fictional data; the models are fakes."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.pipeline.steps.generate import LOCAL_CAPABILITY_NOTE
from app.storage.models import CourseMember, RequestLog
from tests.test_ask_v2 import PASSWORD, V2, World, _login

MIN = 3


@pytest.fixture
def world(make_client):
    with make_client({"learner": {"class_summary_min_group": MIN}}) as client:
        w = World(client)  # alice is enrolled
        for name in ("cara", "dan", "eve"):
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


def test_course_statistics_count_questions_and_hide_small_groups(world):
    for name in ("alice", "cara", "dan"):
        _ask(world, name, world.module)
    _ask(world, "alice", world.module)
    _ask(world, "eve")  # one student about the whole course: hidden
    stats = world.prof.get(f"{world.url}/statistics").json()
    assert stats["min_group"] == MIN and stats["students_enrolled"] == 4
    assert stats["active_students"] == 4 and stats["active_students_7d"] == 4
    assert stats["questions_total"] == 5 and stats["questions_7d"] == 5
    assert stats["local_share"] == 1.0
    modules = {m["module_id"]: m for m in stats["modules"]}
    assert modules[world.module]["questions"] == 4 and modules[world.module]["title"] == "Circuits"
    assert modules[None]["questions"] is None
    assert len(stats["weeks"]) == 8 and stats["weeks"][-1] == {
        "week_start": stats["weeks"][-1]["week_start"], "questions": 5, "students": 4}
    assert all(w["questions"] is None for w in stats["weeks"][:-1])
    body = json.dumps(stats)
    for name in ("alice", "cara", "dan", "eve"):  # no student is named or identified
        assert world.students[name].student_id not in body and name.title() not in body


def test_everything_is_hidden_below_the_minimum_group(world):
    _ask(world, "alice", world.module)
    _ask(world, "cara", world.module)
    stats = world.prof.get(f"{world.url}/statistics").json()
    assert stats["active_students"] == 2
    assert stats["questions_total"] is None and stats["questions_7d"] is None and stats["local_share"] is None
    assert all(m["questions"] is None for m in stats["modules"])
    assert all(w["questions"] is None and w["students"] is None for w in stats["weeks"])


def test_quiz_averages_need_the_minimum_group(world):
    quiz = world.prof.post(f"{world.url}/quizzes", json={
        "title": "Week 1", "module_id": world.module,
        "questions": [{"kind": "true_false", "kc": None, "stem": "A resistor stores charge.", "answer": 1,
                       "explanation": "A capacitor does."}]}).json()
    world.prof.patch(f"{world.url}/quizzes/{quiz['id']}", json={"status": "published"})
    for i, name in enumerate(("alice", "cara", "dan")):
        _login(world.app, name).post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [i % 2]})
        stats = world.prof.get(f"{world.url}/statistics").json()
        row = next(q for q in stats["quizzes"] if q["quiz_id"] == quiz["id"])
        assert row["attempts"] == i + 1
        assert row["mean_score"] == (round(1 / 3, 3) if i + 1 >= MIN else None)  # only cara is right


def test_the_admin_sees_the_counts_of_every_course(world):
    for name in ("alice", "cara", "dan"):
        _ask(world, name, world.module)
    world.services.accounts.create_admin("root", PASSWORD, must_change=False)
    stats = _login(world.app, "root").get(f"{V2}/admin/statistics").json()
    row = next(c for c in stats["courses"] if c["course_id"] == world.course)
    assert row == {"course_id": world.course, "code": "ELG 5902", "title": "Fictional course",
                   "status": "active", "students_enrolled": 4, "active_students_7d": 3, "questions_total": 3,
                   "questions_7d": 3}
    assert stats["students_enrolled"] >= 4 and stats["questions_total"] == 3
    demo = next(c for c in stats["courses"] if c["course_id"] == world.demo)
    assert demo["questions_total"] is None  # nobody asked there


def _log(world, name: str, course_id: int, target: str, warnings: list[str] | None = None) -> None:
    with Session(world.services.engine) as db:
        db.add(RequestLog(request_id="r", session_id="s", student_id=world.students[name].student_id,
                          course_id=course_id, topic="M1", sanitized_question="[question]", target=target,
                          warnings=warnings or []))
        db.commit()


def test_a_cloud_question_answered_locally_counts_as_local(world):
    """A question routed to the cloud that fell back to the local model was answered locally."""
    _log(world, "alice", world.course, "cloud", ["no cloud connection", LOCAL_CAPABILITY_NOTE])
    _log(world, "cara", world.course, "cloud", [LOCAL_CAPABILITY_NOTE])
    _log(world, "dan", world.course, "cloud")
    _log(world, "eve", world.course, "local")
    stats = world.prof.get(f"{world.url}/statistics").json()
    assert stats["local_share"] == 0.75


def test_system_totals_need_the_minimum_group_of_different_students(world):
    """One student asking in several courses is one contributor: the system totals stay hidden."""
    world.services.accounts.create_admin("root", PASSWORD, must_change=False)
    root = _login(world.app, "root")
    for i in range(MIN):
        course = root.post(f"{V2}/courses", json={"code": f"ELG {5000 + i}", "title": "Fictional",
                                                   "course_type": "ece"})
        assert course.status_code == 201, course.text
        _log(world, "alice", course.json()["id"], "local")
    stats = root.get(f"{V2}/admin/statistics").json()
    assert stats["active_students_7d"] == MIN  # per course
    assert stats["questions_total"] is None and stats["questions_7d"] is None


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
