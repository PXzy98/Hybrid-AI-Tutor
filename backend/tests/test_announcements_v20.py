"""Course announcements (V20; api-v2.md 3.11). Fictional data; no model is called."""
import json

import pytest
from sqlmodel import Session

from app.storage.models import Course
from tests.conftest import PASSWORD, csrf_client
from tests.test_ask_v2 import World, _login, rows

WELCOME = {"title": "Welcome to the course", "body": "Office hours are on Tuesdays at 14:00 in room 101."}


@pytest.fixture
def world(make_client):
    with make_client() as client:
        yield World(client)


def _post(world, **body) -> dict:
    r = world.prof.post(f"{world.url}/announcements", json={**WELCOME, **body})
    assert r.status_code == 201, r.text
    return r.json()


def test_students_of_the_course_read_pinned_first_then_newest_first(world):
    first = _post(world, title="Problem set 1 is out")
    assert first["created_at"] == first["updated_at"]
    pinned = _post(world, title="Final exam information", pinned=True)
    last = _post(world, title="Midterm review session")
    alice = _login(world.app, "alice")
    r = alice.get(f"{world.url}/announcements")
    assert r.status_code == 200
    assert [a["id"] for a in r.json()] == [pinned["id"], last["id"], first["id"]]
    assert r.json()[0]["body"] == WELCOME["body"] and r.json()[0]["pinned"] is True
    assert world.prof.get(f"{world.url}/announcements").json() == r.json()

    # unpinning puts it back among the others by date
    r = world.prof.patch(f"{world.url}/announcements/{pinned['id']}", json={"pinned": False})
    assert r.status_code == 200 and r.json()["pinned"] is False
    assert r.json()["updated_at"] == pinned["updated_at"]  # only a text change counts as an edit
    assert [a["id"] for a in alice.get(f"{world.url}/announcements").json()] == [
        last["id"], pinned["id"], first["id"]]


def test_an_instructor_edits_and_deletes_and_the_audit_log_has_no_text(world):
    row = _post(world)
    url = f"{world.url}/announcements/{row['id']}"
    r = world.prof.patch(url, json={"title": "  Office hours moved  ", "body": "Now on Wednesdays."})
    assert r.status_code == 200, r.text
    assert (r.json()["title"], r.json()["body"]) == ("Office hours moved", "Now on Wednesdays.")
    assert r.json()["created_at"] == row["created_at"] and r.json()["updated_at"] >= row["updated_at"]
    assert world.prof.delete(url).status_code == 204
    assert world.prof.delete(url).status_code == 404
    assert world.prof.get(f"{world.url}/announcements").json() == []

    audit = [a for a in rows("audit_log") if a["action"].startswith("announcement.")]
    assert [(a["action"], a["target"]) for a in audit] == [
        ("announcement.create", f"course:{world.course}"), ("announcement.update", f"course:{world.course}"),
        ("announcement.delete", f"course:{world.course}")]
    assert audit[1]["details"] == {"announcement_id": row["id"], "fields": ["body", "title"]}
    logged = json.dumps([a["details"] for a in audit])
    for text in ("Welcome", "Office", "Wednesdays", "Tuesdays"):
        assert text not in logged


def test_validation_blank_title_and_lengths(world):
    url = f"{world.url}/announcements"
    for body in ({"title": ""}, {"title": "   "}, {"title": "x" * 201}, {"title": "Ok", "body": "x" * 4001},
                 {"body": "no title"}):
        r = world.prof.post(url, json=body)
        assert r.status_code == 422, (body, r.text)
    row = _post(world)
    assert world.prof.patch(f"{url}/{row['id']}", json={"title": "  "}).status_code == 422
    assert world.prof.post(url, json={"title": "x" * 200, "body": "y" * 4000}).status_code == 201
    assert world.prof.patch(f"{url}/999999", json={"pinned": True}).status_code == 404
    assert len(rows("announcement")) == 2


def test_student_data_is_refused_before_anything_is_stored(world):
    url = f"{world.url}/announcements"
    leak = "Student 300123456 (jane.doe@uottawa.ca) got 45% on the midterm."
    for body in ({"title": "Midterm results", "body": leak}, {"title": leak}):
        r = world.prof.post(url, json=body)
        assert r.status_code == 422 and "privacy scan" in r.json()["detail"], r.text
        assert "300123456" not in r.text
    row = _post(world)
    r = world.prof.patch(f"{url}/{row['id']}", json={"body": leak})
    assert r.status_code == 422 and "300123456" not in r.text
    stored = rows("announcement")
    assert [a["body"] for a in stored] == [WELCOME["body"]]
    assert "300123456" not in json.dumps(rows("audit_log"), default=str)


def test_an_archived_course_takes_no_new_announcements(world):
    row = _post(world)
    with Session(world.services.engine) as db:
        course = db.get(Course, world.course)
        course.status = "archived"
        db.add(course)
        db.commit()
    url = f"{world.url}/announcements"
    assert world.prof.post(url, json=WELCOME).status_code == 422
    assert world.prof.patch(f"{url}/{row['id']}", json={"pinned": True}).status_code == 422
    assert [a["id"] for a in world.prof.get(url).json()] == [row["id"]]  # instructors still read them


def test_other_people_cannot_use_the_announcement_endpoints(world):
    row = _post(world)
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    carol, _ = world.services.accounts.create_student("carol", "Carol")
    world.services.accounts.set_password(carol.id, PASSWORD, must_change=False)
    other, outsider = _login(world.app, "other"), _login(world.app, "carol")
    anonymous = csrf_client(world.app)
    url = f"{world.url}/announcements"
    one = f"{url}/{row['id']}"
    for client, code in ((other, 404), (outsider, 404), (anonymous, 401)):
        assert client.get(url).status_code == code
        assert client.post(url, json=WELCOME).status_code == code
        assert client.patch(one, json={"title": "x"}).status_code == code
        assert client.delete(one).status_code == code
    # a student of the course reads them but cannot write
    alice = _login(world.app, "alice")
    assert alice.get(url).status_code == 200
    assert alice.post(url, json=WELCOME).status_code == 404
    assert alice.patch(one, json={"title": "x"}).status_code == 404
    assert alice.delete(one).status_code == 404
    # another course's announcement is not found through this course
    other_course = world.prof.post("/api/v2/courses", json={"code": "ELG 9999", "title": "Other",
                                                             "course_type": "ece"}).json()["id"]
    elsewhere = world.prof.post(f"/api/v2/courses/{other_course}/announcements", json=WELCOME).json()
    assert world.prof.patch(f"{url}/{elsewhere['id']}", json={"title": "x"}).status_code == 404
    assert world.prof.delete(f"{url}/{elsewhere['id']}").status_code == 404
    assert [(a["id"], a["title"]) for a in rows("announcement")] == [
        (row["id"], WELCOME["title"]), (elsewhere["id"], WELCOME["title"])]


def test_a_logistics_question_reads_the_matching_announcements(world):
    """Announcements that share words with a logistics question reach the tutor as course-level passages,
    pinned first among equals; nothing for a concept question; never another course's."""
    from app.platform import course_scope

    _post(world, title="Problem set 4 due date", body="Problem set 4 is due with Lecture 22 this time.")
    _post(world, title="Office hours moved", body="Office hours are on Thursday this week.", pinned=True)
    retriever = course_scope.CourseModuleRetriever(world.services, world.course, {})
    found = retriever.announcements("When is problem set 4 due?")
    assert [c.source for c in found] == ["Announcement: Problem set 4 due date"]
    assert found[0].metadata == {"course_id": world.course, "module_id": None, "origin": "announcement"}
    assert found[0].topic == f"course:{world.course}" and "Lecture 22" in found[0].text
    with course_scope.question_kind("logistics"):
        first = retriever.retrieve("When is problem set 4 due?", "general")[0]
    assert first.source.startswith("Announcement")
    assert retriever.retrieve("When is problem set 4 due?", "general") == []  # concept: files only
    assert course_scope.CourseModuleRetriever(world.services, world.demo, {}).announcements(
        "When is problem set 4 due?") == []
