"""v5 V8: topics the class finds hard, from quiz answers, for the instructor's extra material. Shown only with
at least the minimum group of students per topic (never below 5, whatever the setting); never a student.
Fictional data."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.storage.models import CourseMember
from tests.test_ask_v2 import PASSWORD, World, _login

MIN = 5  # the floor: the setting below asks for 1
OTHERS = ("cara", "dan", "eve", "finn")
HARD = {"kind": "true_false", "kc": "C.1", "stem": "A resistor stores charge.", "answer": 1,
        "explanation": "A capacitor stores charge."}


@pytest.fixture
def world(make_client):
    with make_client({"learner": {"class_summary_min_group": 1}}) as client:
        w = World(client)
        for name in OTHERS:
            account, _ = w.services.accounts.create_student(name, name.title())
            w.students[name] = w.services.accounts.set_password(account.id, PASSWORD, must_change=False)
            with Session(w.services.engine) as db:
                db.add(CourseMember(course_id=w.course, account_id=account.id, role="student",
                                    status="active"))
                db.commit()
        quiz = w.prof.post(f"{w.url}/quizzes", json={"title": "Week 1", "module_id": w.module,
                                                      "questions": [HARD]}).json()
        w.prof.patch(f"{w.url}/quizzes/{quiz['id']}", json={"status": "published"})
        w.quiz = quiz["id"]
        yield w


def _answer(world, name: str, choice: int) -> None:
    r = _login(world.app, name).post(f"{world.url}/quizzes/{world.quiz}/attempt", json={"answers": [choice]})
    assert r.status_code == 201, r.text


def test_a_topic_is_listed_once_enough_students_found_it_hard(world):
    url = f"{world.url}/weak-topics"
    for name in ("alice", "cara", "dan", "eve"):
        _answer(world, name, 0)
    body = world.prof.get(url).json()
    # four students: nothing is shown, although the setting asks for only one
    assert body["min_group"] == MIN and body["topics"] == []
    _answer(world, "finn", 1)
    body = world.prof.get(url).json()
    # 1 of 5 correct; the share is rounded to tens of percent
    assert body["topics"] == [{"kc_code": "C.1", "name": "Ohm's law", "module_id": world.module,
                               "students": 5, "correct_rate": 0.2}]
    for name in ("alice", "cara", "dan", "eve", "finn"):
        assert world.students[name].student_id not in json.dumps(body)


def test_a_topic_the_class_knows_is_not_listed(world):
    for name in ("alice", "cara", "dan", "eve", "finn"):
        _answer(world, name, 1)
    assert world.prof.get(f"{world.url}/weak-topics").json()["topics"] == []


def test_who_may_read_the_weak_topics(world):
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    url = f"{world.url}/weak-topics"
    assert _login(world.app, "other").get(url).status_code == 404
    assert _login(world.app, "alice").get(url).status_code in (403, 404)
    assert _login(world.app, "bob").get(url).status_code in (403, 404)
    assert TestClient(world.app).get(url).status_code == 401
