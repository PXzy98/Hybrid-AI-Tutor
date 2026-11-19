"""v5 V8: topics the class finds hard, from quiz answers, for the instructor's extra material. Shown only with
at least the minimum group of students per topic; never a student. Fictional data."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.storage.models import CourseMember
from tests.test_ask_v2 import PASSWORD, World, _login

MIN = 3
HARD = {"kind": "true_false", "kc": "C.1", "stem": "A resistor stores charge.", "answer": 1,
        "explanation": "A capacitor stores charge."}


@pytest.fixture
def world(make_client):
    with make_client({"learner": {"class_summary_min_group": MIN}}) as client:
        w = World(client)
        for name in ("cara", "dan"):
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
    _answer(world, "alice", 0)
    _answer(world, "cara", 0)
    body = world.prof.get(url).json()
    assert body["min_group"] == MIN and body["topics"] == []  # two students: nothing is shown
    _answer(world, "dan", 1)
    body = world.prof.get(url).json()
    assert body["topics"] == [{"kc_code": "C.1", "name": "Ohm's law", "module_id": world.module,
                               "students": 3, "correct_rate": round(1 / 3, 3)}]
    for name in ("alice", "cara", "dan"):
        assert world.students[name].student_id not in json.dumps(body)


def test_a_topic_the_class_knows_is_not_listed(world):
    for name in ("alice", "cara", "dan"):
        _answer(world, name, 1)
    assert world.prof.get(f"{world.url}/weak-topics").json()["topics"] == []


def test_who_may_read_the_weak_topics(world):
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    url = f"{world.url}/weak-topics"
    assert _login(world.app, "other").get(url).status_code == 404
    assert _login(world.app, "alice").get(url).status_code in (403, 404)
    assert _login(world.app, "bob").get(url).status_code in (403, 404)
    assert TestClient(world.app).get(url).status_code == 401
