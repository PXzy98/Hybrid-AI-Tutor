"""End of term (course-structure.md 3.5; task Z9): the export holds only what the instructor may see, then
the course's student data is deleted and everything else stays."""
import io
import json
import os
import time
import zipfile

import pytest
from sqlmodel import Session

from app.platform import end_of_term
from app.storage.models import RequestLog, SessionTurn
from tests.conftest import csrf_client
from tests.test_ask_v2 import V2, World, _login, rows
from tests.test_learner_v2 import Q1, set_mode


@pytest.fixture
def world(make_client, tmp_path):
    with make_client({"data_dir": str(tmp_path), "learner": {"class_summary_min_group": 1}}) as client:
        w = World(client)
        w.data = tmp_path
        w.enrol("bob")
        for name in ("alice", "bob"):
            w.consent(name)
        yield w


def _export(world, export_id: str) -> dict[str, object]:
    r = world.prof.get(f"{world.url}/exports/{export_id}")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    with zipfile.ZipFile(io.BytesIO(r.content)) as archive:
        return {name: json.loads(archive.read(name)) for name in archive.namelist()}


def test_ending_the_term_exports_then_deletes_the_course_student_data(world):
    alice, bob = _login(world.app, "alice"), _login(world.app, "bob")
    demo = f"{V2}/courses/{world.demo}"
    set_mode(world, "B")
    alice.post(f"{world.url}/me/visibility", json={"action": "acknowledge"})  # bob does not acknowledge
    for client in (alice, bob):
        client.post(f"{world.url}/check", json=Q1)
        client.post(f"{world.url}/ask", json={"question": "What is a volt?"})
    alice.post(f"{demo}/ask", json={"question": "What is asthma?"})
    sid = world.students["alice"].student_id
    world.prof.put(f"{world.url}/students/{sid}/plan", json={"focus_kcs": ["C.1"], "goal": "basic"})

    assert world.prof.post(f"{world.url}/end-term", json={}).status_code == 422  # needs the confirmation
    r = world.prof.post(f"{world.url}/end-term", json={"confirm": True})
    assert r.status_code == 200, r.text
    done = r.json()
    assert done["students_removed"] == 2 and done["students_exported"] == 1
    assert done["deleted"]["evidence_log"] == 2 and done["deleted"]["session_turn"] == 4

    files = _export(world, done["export_id"])
    assert set(files) == {"export.json", "class_summary.json", "students.json", "quizzes.json", "survey.json"}
    assert files["export.json"]["students"] == 2 and files["class_summary.json"][0]["students"] == 2
    assert [s["student_id"] for s in files["students.json"]] == [sid]  # only the student who acknowledged
    assert [k["kc_code"] for k in files["students.json"][0]["kcs"]] == ["C.1"]  # mastery since visible
    text = json.dumps(files)
    assert "volt" not in text and "alice" not in text.lower()  # no question text, no names

    # this course: student data and memberships are gone; the course, its content and instructor stay
    for table in ("evidence_log", "learner_kc_state", "learning_plan"):
        assert rows(table) == [], table
    assert {t["course_id"] for t in rows("session_turn")} == {world.demo}
    assert {t["course_id"] for t in rows("request_log")} == {world.demo}
    assert all(c["course_id"] != world.course for c in rows("usage_counter"))
    members = world.prof.get(f"{world.url}/members").json()
    assert [m["role"] for m in members] == ["instructor"]
    assert world.prof.get(f"{world.url}/kcs").json()[0]["code"] == "C.1"
    assert alice.get(f"{world.url}/me/profile").status_code == 404  # no longer a member
    assert alice.get(f"{demo}/conversations").json() != []  # other courses and the account are untouched
    assert alice.get(f"{V2}/me/consent").json()["given"] is True
    assert world.prof.post(f"{world.url}/archive").status_code == 200  # possible once the term is ended
    audit = [a for a in rows("audit_log") if a["action"] == "course.end_term"]
    assert audit[0]["details"]["export_id"] == done["export_id"]


def test_mode_a_exports_no_individual_data(world):
    _login(world.app, "alice").post(f"{world.url}/check", json=Q1)
    done = world.prof.post(f"{world.url}/end-term", json={"confirm": True}).json()
    assert done["students_exported"] == 0
    files = set(_export(world, done["export_id"]))
    assert files == {"export.json", "class_summary.json", "quizzes.json", "survey.json"}


def test_exports_belong_to_the_course_instructors_and_expire(world):
    world.services.accounts.create_instructor("other", "correct-horse-battery", must_change=False)
    other, alice = _login(world.app, "other"), _login(world.app, "alice")
    for outsider in (other, alice):
        assert outsider.post(f"{world.url}/end-term", json={"confirm": True}).status_code == 404
    export_id = world.prof.post(f"{world.url}/end-term", json={"confirm": True}).json()["export_id"]
    url = f"{world.url}/exports/{export_id}"
    assert other.get(url).status_code == 404 and alice.get(url).status_code == 404
    assert world.prof.get(f"{world.url}/exports/..%2F..%2Fsecret").status_code == 404
    assert world.prof.get(f"{world.url}/exports/20260101T000000Z-000000000000").status_code == 404
    # the same export ID under another course is not found
    assert world.prof.get(f"{V2}/courses/{world.demo}/exports/{export_id}").status_code == 404
    path = world.data / "courses" / str(world.course) / "exports" / f"{export_id}.zip"
    old = time.time() - 73 * 3600
    os.utime(path, (old, old))
    assert world.prof.get(url).status_code == 404 and not path.exists()  # expired: deleted


def test_logged_out_callers_can_neither_end_the_term_nor_download(world):
    _login(world.app, "alice").post(f"{world.url}/check", json=Q1)
    export_id = world.prof.post(f"{world.url}/end-term", json={"confirm": True}).json()["export_id"]
    world.enrol("alice")
    _login(world.app, "alice").post(f"{world.url}/check", json=Q1)
    anonymous = csrf_client(world.app)
    assert anonymous.post(f"{world.url}/end-term", json={"confirm": True}).status_code == 401
    assert len(rows("evidence_log")) == 1  # nothing was deleted
    r = anonymous.get(f"{world.url}/exports/{export_id}")
    assert r.status_code == 401 and r.headers["content-type"] != "application/zip"


def test_maintenance_removes_late_writes_and_expired_exports(world):
    alice = _login(world.app, "alice")
    alice.post(f"{world.url}/check", json=Q1)
    export_id = world.prof.post(f"{world.url}/end-term", json={"confirm": True}).json()["export_id"]
    late = world.students["alice"].student_id  # a request that was still running writes afterwards
    world.enrol("bob")  # next term's student keeps their data
    current = world.students["bob"].student_id
    with Session(world.services.engine) as db:
        for sid in (late, current):
            db.add(RequestLog(request_id=f"r-{sid}", session_id="s", student_id=sid, course_id=world.course,
                              topic="circuits", sanitized_question="[test]"))
            db.add(SessionTurn(session_id="s", student_id=sid, course_id=world.course, role="student",
                               text="[test]"))
        db.commit()
    path = world.data / "courses" / str(world.course) / "exports" / f"{export_id}.zip"
    old = time.time() - 73 * 3600
    os.utime(path, (old, old))
    end_of_term.maintenance(world.services.engine, world.data, 72)
    assert {r["student_id"] for r in rows("request_log")} == {current}
    assert {r["student_id"] for r in rows("session_turn")} == {current}
    assert not path.exists()  # deleted although nobody opened the course again


def test_an_export_can_be_taken_before_the_term_ends_without_deleting(world):
    alice = _login(world.app, "alice")
    alice.post(f"{world.url}/check", json=Q1)
    r = world.prof.post(f"{world.url}/exports")
    assert r.status_code == 201, r.text
    early = r.json()
    files = _export(world, early["export_id"])
    assert {"export.json", "class_summary.json", "quizzes.json", "survey.json"} <= set(files)
    assert len(rows("evidence_log")) == 1  # nothing deleted, the student is still a member
    assert alice.get(f"{world.url}/me/profile").status_code == 200
    audit = [a for a in rows("audit_log") if a["action"] == "course.export"]
    assert audit[0]["details"]["export_id"] == early["export_id"]
    done = world.prof.post(f"{world.url}/end-term", json={"confirm": True}).json()
    assert done["export_id"] != early["export_id"]  # the end of term takes its own, final export
    _export(world, early["export_id"])  # the early one stays downloadable until it expires


def test_only_the_course_instructors_take_an_export(world):
    world.services.accounts.create_instructor("other", "correct-horse-battery", must_change=False)
    for client, code in ((_login(world.app, "other"), 404), (_login(world.app, "alice"), 404),
                         (csrf_client(world.app), 401)):
        assert client.post(f"{world.url}/exports").status_code == code
    assert [a for a in rows("audit_log") if a["action"] == "course.export"] == []
