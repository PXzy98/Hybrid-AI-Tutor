"""API v2 ask (api-v2.md 3.5; guide 4.5): the pipeline runs in the request's course (content, learner data,
conversations), behind the course role check and the usage limits. Fictional data; the models are fakes."""
import json

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.core.config import get_settings
from app.llm.fake import FakeLLMClient
from app.storage.models import CourseMember
from app.storage.testing import table_rows
from tests.conftest import PASSWORD, UNDERSTOOD_NOTHING, csrf_client

V2 = "/api/v2"
OPTIONS = {"A": {"text": "Several times"}, "B": {"text": "Once"}, "C": {"text": "Never"},
           "D": {"text": "Only when ill"}}


def _login(app, username: str) -> TestClient:
    c = csrf_client(app)
    assert c.post(f"{V2}/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


def rows(table: str) -> list[dict]:
    return table_rows(get_settings().database_url, table)


class World:
    def __init__(self, client) -> None:
        self.app, self.services = client.app, client.app.state.services
        self.services.local_llm = FakeLLMClient("Fake local answer.", model="fake-local")
        self.services.understand_llm = FakeLLMClient(UNDERSTOOD_NOTHING, model="fake-understand")
        accounts = self.services.accounts
        accounts.create_instructor("prof", PASSWORD, must_change=False)
        self.students = {}
        for name in ("alice", "bob"):
            account, _ = accounts.create_student(name, name.title())
            self.students[name] = accounts.set_password(account.id, PASSWORD, must_change=False)
        self.prof = _login(self.app, "prof")
        self.demo = self.services.content.course_id
        self.course = self.prof.post(f"{V2}/courses", json={
            "code": "ELG 5902", "title": "Fictional course", "course_type": "ece"}).json()["id"]
        self.url = f"{V2}/courses/{self.course}"
        self.module = self.prof.post(f"{self.url}/modules", json={
            "code": "circuits", "title": "Circuits"}).json()["id"]
        kc = self.prof.post(f"{self.url}/kcs", json={"module_id": self.module, "code": "C.1",
                                                     "name": "Ohm's law", "difficulty": "basic"}).json()
        self.prof.post(f"{self.url}/check-items", json={
            "kc_id": kc["id"], "code": "C.1-q1", "level": "basic", "stem": "How often?", "options": OPTIONS,
            "answer": "A", "status": "active"})
        self.enrol("alice")

    def enrol(self, name: str) -> None:
        with Session(self.services.engine) as db:
            db.add(CourseMember(course_id=self.course, account_id=self.students[name].id, role="student",
                                status="active"))
            db.commit()

    def consent(self, name: str) -> None:
        self.services.learner.set_consent(self.students[name].student_id, True)


@pytest.fixture
def world(make_client):
    with make_client() as client:
        yield World(client)


def test_a_student_asks_in_the_course_and_the_conversation_stays_there(world):
    alice = _login(world.app, "alice")
    r = alice.post(f"{world.url}/ask", json={"question": "What is Ohm's law?", "module_id": world.module})
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["answer"] == "Fake local answer." and body["route_target"] == "local"
    assert body["conversation_id"] == body["session_id"]
    assert body["check_item"]["id"] == "C.1-q1"  # the course's own item, not one of the demo course
    conversation = body["conversation_id"]

    r = alice.post(f"{world.url}/ask", json={"question": "And resistance?", "conversation_id": conversation})
    assert r.status_code == 200 and r.json()["conversation_id"] == conversation
    assert r.json()["check_item"] is None  # a question about the whole course has no module to check

    assert {t["course_id"] for t in rows("session_turn")} == {world.course}
    assert {(t["course_id"], t["topic"]) for t in rows("request_log")} == {
        (world.course, "circuits"), (world.course, "general")}
    listed = alice.get(f"{world.url}/conversations").json()
    assert [(c["conversation_id"], c["turns"]) for c in listed] == [(conversation, 4)]
    detail = alice.get(f"{world.url}/conversations/{conversation}").json()
    assert [t["role"] for t in detail["turns"]] == ["student", "tutor", "student", "tutor"]

    # the same ID in another course is not this conversation
    demo = f"{V2}/courses/{world.demo}"
    assert alice.get(f"{demo}/conversations").json() == []
    assert alice.get(f"{demo}/conversations/{conversation}").status_code == 404
    again = {"question": "Hi", "conversation_id": conversation}
    assert alice.post(f"{demo}/ask", json=again).status_code == 404


def test_only_students_of_the_course_can_ask_or_read_conversations(world):
    alice, bob, anon = _login(world.app, "alice"), _login(world.app, "bob"), csrf_client(world.app)
    conversation = alice.post(f"{world.url}/ask", json={"question": "What is a volt?"}).json()[
        "conversation_id"]
    question = {"question": "What is a volt?"}
    assert bob.post(f"{world.url}/ask", json=question).status_code == 404  # not in the course
    assert bob.post(f"{world.url}/ask/stream", json=question).status_code == 404
    assert bob.get(f"{world.url}/conversations").status_code == 404
    assert anon.post(f"{world.url}/ask", json=question).status_code == 401
    assert world.prof.post(f"{world.url}/ask", json=question).status_code == 404  # students only
    world.enrol("bob")  # a classmate cannot read or continue someone else's conversation
    assert bob.get(f"{world.url}/conversations").json() == []
    assert bob.get(f"{world.url}/conversations/{conversation}").status_code == 404
    assert bob.post(f"{world.url}/ask", json={**question, "conversation_id": conversation}).status_code == 404
    assert alice.post(f"{world.url}/ask", json={"question": "x", "module_id": 999999}).status_code == 404


def test_learner_data_is_written_to_the_course_that_was_asked(make_client):
    with make_client({"learner": {"weak_evidence": True}}) as client:
        _learner_data_goes_to_the_course(World(client))


def _learner_data_goes_to_the_course(world):
    world.consent("alice")
    sid = world.students["alice"].student_id
    world.services.understand_llm = FakeLLMClient('{"k": ["C.1"], "t": "concept", "c": true, "m": []}',
                                                  model="fake-understand")
    alice = _login(world.app, "alice")
    r = alice.post(f"{world.url}/ask", json={"question": "I am confused by Ohm's law",
                                             "module_id": world.module})
    assert r.status_code == 200 and r.json()["kc_level"] is not None  # personalized in this course
    evidence = [e for e in rows("evidence_log") if e["student_id"] == sid]
    assert evidence and {e["course_id"] for e in evidence} == {world.course}
    assert {e["kc_id"] for e in evidence} == {"C.1"}


def test_the_stream_ends_with_the_result_and_the_conversation_id(world):
    alice = _login(world.app, "alice")
    r = alice.post(f"{world.url}/ask/stream", json={"question": "What is a volt?"})
    assert r.status_code == 200 and r.headers["content-type"].startswith("text/event-stream")
    text = r.text
    events = [block.split("\n", 1) for block in text.strip().split("\n\n") if block.startswith("event:")]
    names = [e[0].removeprefix("event: ") for e in events]
    assert names[0] == "meta" and names[-2:] == ["result", "done"]
    meta = json.loads(events[0][1].removeprefix("data: "))
    result = json.loads(events[-2][1].removeprefix("data: "))
    assert result["conversation_id"] == meta["conversation_id"] and result["answer"] == "Fake local answer."
    assert {t["course_id"] for t in rows("session_turn")} == {world.course}


def test_question_limits_apply_per_course(make_client):
    with make_client({"limits": {"usage": {"questions_per_minute": 2}}}) as client:
        world = World(client)
        alice = _login(world.app, "alice")
        question = {"question": "What is a volt?"}
        assert alice.post(f"{world.url}/ask", json=question).status_code == 200
        assert alice.post(f"{world.url}/ask", json=question).status_code == 200
        r = alice.post(f"{world.url}/ask", json=question)
        assert r.status_code == 429 and r.json()["code"] == "usage_limit"
        assert r.json()["retry_after_seconds"] >= 1
        assert alice.post(f"{world.url}/ask/stream", json=question).status_code == 429
        # the limit is per course: the demo course still answers
        assert alice.post(f"{V2}/courses/{world.demo}/ask", json=question).status_code == 200
        counters = [c for c in rows("usage_counter") if c["kind"] == "question" and c["period"] == "day"]
        assert {(c["course_id"], c["count"]) for c in counters} == {(world.course, 2), (world.demo, 1)}


def test_the_cloud_limit_keeps_the_answer_local(make_client):
    with make_client({"limits": {"usage": {"cloud_calls_per_day": 0}}}) as client:
        world = World(client)
        alice = _login(world.app, "alice")
        body = alice.post(f"{world.url}/ask", json={"question": "What is a volt?"}).json()
        assert body["route_target"] == "local"
        assert any("limit of cloud answers" in w for w in body["warnings"])


def test_api_v1_logs_show_only_the_demo_course(world):
    alice = _login(world.app, "alice")
    assert alice.post(f"{world.url}/ask", json={"question": "What is a volt?"}).status_code == 200
    page = world.prof.get("/api/v1/admin/logs").json()
    assert page["total"] == 0 and page["entries"] == []  # the other course's request is not shown


def test_ending_a_course_removes_its_conversations_and_logs(world):
    alice = _login(world.app, "alice")
    assert alice.post(f"{world.url}/ask", json={"question": "What is a volt?"}).status_code == 200
    demo = f"{V2}/courses/{world.demo}"
    assert alice.post(f"{demo}/ask", json={"question": "What is asthma?"}).status_code == 200
    with Session(world.services.engine) as db:
        from app.storage.models import Course

        db.delete(db.get(Course, world.course))
        db.commit()
    assert {t["course_id"] for t in rows("session_turn")} == {world.demo}
    assert {t["course_id"] for t in rows("request_log")} == {world.demo}
