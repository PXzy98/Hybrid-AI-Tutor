"""Task Z9c: /api/v2 course content (modules, KCs, check items, misconceptions, YAML import/export), with
access tests: another course's instructor, a student, logged out."""
import io
import zipfile

import pytest
import yaml
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.catalog import course_topics, load_course_content
from app.storage.models import CourseMember
from tests.conftest import PASSWORD

V2 = "/api/v2"
OPTIONS = {"A": {"text": "Right"}, "B": {"text": "Wrong one", "misconception": "BP.MC1"},
           "C": {"text": "Wrong two"}, "D": {"text": "Wrong three"}}


def _login(app, username: str) -> TestClient:
    c = TestClient(app)
    assert c.post(f"{V2}/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


@pytest.fixture
def world(make_client):
    with make_client() as client:
        services = client.app.state.services
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        services.accounts.create_instructor("other", PASSWORD, must_change=False)
        alice, _ = services.accounts.create_student("alice", "Alice")
        services.accounts.set_password(alice.id, PASSWORD, must_change=False)
        prof = _login(client.app, "prof")
        r = prof.post(f"{V2}/courses", json={"code": "ELG 5902", "title": "Fictional", "course_type": "ece"})
        course_id = r.json()["id"]
        with Session(services.engine) as db:
            db.add(CourseMember(course_id=course_id, account_id=alice.id, role="student", status="active"))
            db.commit()
        yield {"app": client.app, "services": services, "prof": prof, "course": course_id,
               "url": f"{V2}/courses/{course_id}"}


def _build(prof: TestClient, url: str) -> dict:
    module = prof.post(f"{url}/modules", json={"code": "blood_pressure", "title": "Blood pressure",
                                               "guideline": "Speak plainly."}).json()
    a = prof.post(f"{url}/kcs", json={"module_id": module["id"], "code": "BP.1", "name": "What it is",
                                      "difficulty": "basic"}).json()
    b = prof.post(f"{url}/kcs", json={"module_id": module["id"], "code": "BP.2", "name": "Measuring",
                                      "difficulty": "intermediate", "prerequisite_ids": [a["id"]]}).json()
    mc = prof.post(f"{url}/misconceptions", json={"kc_id": b["id"], "code": "BP.MC1",
                                                  "statement": "One reading is enough.",
                                                  "correction": "Measure several times."}).json()
    item = prof.post(f"{url}/check-items", json={"kc_id": b["id"], "code": "BP.2-q1", "level": "basic",
                                                 "stem": "How often?", "options": OPTIONS, "answer": "A",
                                                 "status": "draft"}).json()
    return {"module": module, "a": a, "b": b, "mc": mc, "item": item}


def test_content_endpoints_belong_to_the_course_instructors(world):
    built = _build(world["prof"], world["url"])
    url, app = world["url"], world["app"]
    other, alice, anon = _login(app, "other"), _login(app, "alice"), TestClient(app)
    paths = ["kcs", f"kcs/{built['a']['id']}", "check-items", "misconceptions", "content/export"]
    for path in paths:
        assert other.get(f"{url}/{path}").status_code == 404, path
        assert alice.get(f"{url}/{path}").status_code == 404, path
        assert anon.get(f"{url}/{path}").status_code == 401, path
    for client in (other, alice):
        assert client.post(f"{url}/modules", json={"code": "x", "title": "X"}).status_code == 404
        assert client.patch(f"{url}/kcs/{built['a']['id']}", json={"status": "retired"}).status_code == 404
        assert client.patch(f"{url}/check-items/{built['item']['id']}",
                            json={"status": "active"}).status_code == 404
    assert other.get(f"{url}/modules").status_code == 404
    student_view = alice.get(f"{url}/modules").json()  # students see the modules, not the guideline
    assert [(m["code"], m["guideline"]) for m in student_view] == [("blood_pressure", None)]
    assert world["prof"].get(f"{url}/modules").json()[0]["guideline"] == "Speak plainly."


def test_edits_are_checked_like_the_seed_and_drafts_are_published_by_status(world):
    prof, url = world["prof"], world["url"]
    built = _build(prof, url)
    a, b, item = built["a"], built["b"], built["item"]
    r = prof.patch(f"{url}/kcs/{a['id']}", json={"prerequisite_ids": [b["id"]]})
    assert r.status_code == 422 and "cycle" in r.json()["detail"]
    dup = prof.post(f"{url}/kcs", json={"module_id": built["module"]["id"], "code": "BP.1", "name": "Again",
                                        "difficulty": "basic"})
    assert dup.status_code == 409
    bad_tag = {**OPTIONS, "C": {"text": "Wrong two", "misconception": "NOPE.MC"}}
    r = prof.post(f"{url}/check-items", json={"kc_id": b["id"], "code": "BP.2-q2", "level": "basic",
                                              "stem": "S?", "options": bad_tag, "answer": "A"})
    assert r.status_code == 422 and "NOPE.MC" in r.json()["detail"]
    r = prof.patch(f"{url}/check-items/{item['id']}", json={"answer": "B"})  # tags the answer
    assert r.status_code == 422 and "correct answer" in r.json()["detail"]
    three = {k: v for k, v in OPTIONS.items() if k != "D"}
    assert prof.patch(f"{url}/check-items/{item['id']}", json={"options": three}).status_code == 422
    store = load_course_content(world["services"].engine, world["course"])
    assert store.items("BP.2") == []  # the draft is not served
    r = prof.patch(f"{url}/check-items/{item['id']}", json={"status": "active"})
    assert r.status_code == 200 and r.json()["status"] == "active"
    store = load_course_content(world["services"].engine, world["course"])
    assert [i.id for i in store.items("BP.2")] == ["BP.2-q1"]
    r = prof.patch(f"{url}/kcs/{a['id']}", json={"status": "retired"})
    assert r.status_code == 200 and r.json()["status"] == "retired"
    store = load_course_content(world["services"].engine, world["course"])
    assert store.kc("BP.1") is None and store.prerequisites("BP.2") == []
    assert prof.get(f"{url}/check-items", params={"kc_id": b["id"]}).json()[0]["code"] == "BP.2-q1"
    renamed = prof.patch(f"{url}/kcs/{b['id']}", json={"code": "BP.9", "name": "Measuring BP"}).json()
    assert (renamed["code"], renamed["name"]) == ("BP.2", "Measuring BP")  # codes never change
    other = prof.post(f"{V2}/courses", json={"code": "ELG 1", "title": "Other", "course_type": "ece"}).json()
    r = prof.post(f"{V2}/courses/{other['id']}/misconceptions",
                  json={"kc_id": b["id"], "code": "X.MC", "statement": "s", "correction": "c"})
    assert r.status_code == 404  # a KC of another course


def test_modules_are_ordered_and_only_empty_ones_deleted(world):
    prof, url = world["prof"], world["url"]
    built = _build(prof, url)
    empty = prof.post(f"{url}/modules", json={"code": "later", "title": "Later"}).json()
    assert load_course_content(world["services"].engine, world["course"]).topics() == ["blood_pressure"]
    order = prof.post(f"{url}/modules/reorder", json={"module_ids": [empty["id"], built["module"]["id"]]})
    assert [m["code"] for m in order.json()] == ["later", "blood_pressure"]
    assert prof.post(f"{url}/modules/reorder", json={"module_ids": [empty["id"]]}).status_code == 422
    assert prof.delete(f"{url}/modules/{built['module']['id']}").status_code == 409
    assert prof.delete(f"{url}/modules/{empty['id']}").status_code == 204
    r = prof.patch(f"{url}/modules/{built['module']['id']}", json={"title": "BP"})
    assert r.json()["title"] == "BP" and r.json()["code"] == "blood_pressure"


def test_export_and_import_round_trip_the_demo_course(world):
    services, prof = world["services"], world["prof"]
    demo = services.content.course_id
    with Session(services.engine) as db:  # prof is an instructor of the demo course (API v1 accounts)
        demo_topics = course_topics(db, demo)
    r = prof.get(f"{V2}/courses/{demo}/content/export")
    assert r.status_code == 200 and r.headers["content-type"] == "application/zip"
    names = zipfile.ZipFile(io.BytesIO(r.content)).namelist()
    assert {n.split("/")[0] for n in names} == {t.topic for t in demo_topics}
    up = prof.post(f"{world['url']}/content/import", files={"file": ("c.zip", r.content, "application/zip")})
    assert up.status_code == 200, up.text
    assert up.json()["kcs"] == sum(len(t.kcs) for t in demo_topics)
    with Session(services.engine) as db:
        copied = course_topics(db, world["course"])
    by_topic = {t.topic: t for t in demo_topics}
    assert sorted(t.topic for t in copied) == sorted(by_topic)
    for t in copied:
        assert t.model_dump() == by_topic[t.topic].model_dump()  # statuses (drafts) included
    zip_file = {"file": ("c.zip", r.content, "application/zip")}
    again = prof.post(f"{world['url']}/content/import", files=zip_file)
    assert again.status_code == 409


def _zip(entries: dict[str, str]) -> bytes:
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w") as zf:
        for name, text in entries.items():
            zf.writestr(name, text)
    return buffer.getvalue()


def test_import_reads_only_the_seed_files_and_rejects_bad_content(world):
    prof, url = world["prof"], world["url"]
    kcs = yaml.safe_dump({"topic": "t1", "name": "T1", "kcs": [{"id": "T.1", "name": "One",
                                                                 "difficulty": "basic"}]})
    items = yaml.safe_dump([{"id": "T.1-q1", "kc": "T.1", "level": "basic", "stem": "Q?",
                             "options": {"A": "a", "B": "b", "C": "c", "D": "d"}, "answer": "A",
                             "reviewed_by": "someone"}])

    def upload(data: bytes):
        return prof.post(f"{url}/content/import", files={"file": ("c.zip", data, "application/zip")})

    assert upload(b"not a zip").status_code == 422
    cyclic = yaml.safe_dump({"kcs": [
        {"id": "X.1", "name": "x", "difficulty": "basic", "prerequisites": ["X.2"]},
        {"id": "X.2", "name": "y", "difficulty": "basic", "prerequisites": ["X.1"]}]})
    r = upload(_zip({"x/kcs.yaml": cyclic}))
    assert r.status_code == 422 and "cycle" in r.json()["detail"]
    r = upload(_zip({"t1/kcs.yaml": kcs, "t1/items.yaml": items, "../evil/kcs.yaml": kcs,
                     "t1/notes.txt": "x"}))
    assert r.status_code == 200, r.text
    assert r.json() == {"modules": 1, "kcs": 1, "items": 1, "misconceptions": 0}
    item = prof.get(f"{url}/check-items").json()[0]
    assert item["status"] == "active"  # the instructor's own file is published (decision E)


def test_every_content_endpoint_refuses_other_instructors_students_and_anonymous_callers(world):
    built = _build(world["prof"], world["url"])
    url, app = world["url"], world["app"]
    m, kc, item, mc = built["module"]["id"], built["a"]["id"], built["item"]["id"], built["mc"]["id"]
    zip_file = {"file": ("c.zip", b"PK", "application/zip")}
    calls = [
        ("post", "modules", {"json": {"code": "x", "title": "X"}}),
        ("patch", f"modules/{m}", {"json": {"title": "X"}}),
        ("delete", f"modules/{m}", {}),
        ("post", "modules/reorder", {"json": {"module_ids": [m]}}),
        ("get", "kcs", {}), ("get", f"kcs/{kc}", {}),
        ("post", "kcs", {"json": {"module_id": m, "code": "Z.1", "name": "Z", "difficulty": "basic"}}),
        ("patch", f"kcs/{kc}", {"json": {"status": "retired"}}),
        ("get", "check-items", {}), ("get", f"check-items/{item}", {}),
        ("post", "check-items", {"json": {"kc_id": kc, "code": "Z.1-q", "level": "basic", "stem": "S?",
                                          "options": OPTIONS, "answer": "A"}}),
        ("patch", f"check-items/{item}", {"json": {"status": "active"}}),
        ("get", "misconceptions", {}), ("get", f"misconceptions/{mc}", {}),
        ("post", "misconceptions", {"json": {"kc_id": kc, "code": "Z.MC", "statement": "s",
                                             "correction": "c"}}),
        ("patch", f"misconceptions/{mc}", {"json": {"statement": "changed"}}),
        ("post", "content/import", {"files": zip_file}),
        ("get", "content/export", {}),
    ]
    clients = {"other instructor": (_login(app, "other"), 404), "student": (_login(app, "alice"), 404),
               "logged out": (TestClient(app), 401)}
    for who, (client, expected) in clients.items():
        for method, path, kwargs in calls:
            r = getattr(client, method)(f"{url}/{path}", **kwargs)
            assert r.status_code == expected, (who, method, path, r.status_code)
    assert TestClient(app).get(f"{url}/modules").status_code == 401
    assert world["prof"].get(f"{url}/check-items/{item}").json()["status"] == "draft"  # nothing changed


def test_duplicate_codes_are_conflicts_not_server_errors(world):
    prof, url = world["prof"], world["url"]
    built = _build(prof, url)
    assert prof.post(f"{url}/modules", json={"code": "blood_pressure", "title": "Again"}).status_code == 409
    item = {"kc_id": built["b"]["id"], "code": "BP.2-q1", "level": "basic", "stem": "S?", "options": OPTIONS,
            "answer": "A"}
    assert prof.post(f"{url}/check-items", json=item).status_code == 409
    mc = {"kc_id": built["b"]["id"], "code": "BP.MC1", "statement": "s", "correction": "c"}
    assert prof.post(f"{url}/misconceptions", json=mc).status_code == 409


def test_an_export_with_an_empty_module_imports_in_the_same_order(world):
    prof, url = world["prof"], world["url"]
    _build(prof, url)
    first = prof.post(f"{url}/modules", json={"code": "intro", "title": "Intro"}).json()
    modules = [m["id"] for m in prof.get(f"{url}/modules").json()]
    order = [first["id"]] + [i for i in modules if i != first["id"]]
    prof.post(f"{url}/modules/reorder", json={"module_ids": order})
    exported = prof.get(f"{url}/content/export").content
    body = {"code": "ELG 2", "title": "Copy", "course_type": "ece"}
    copy = prof.post(f"{V2}/courses", json=body).json()["id"]
    zip_file = {"file": ("c.zip", exported, "application/zip")}
    r = prof.post(f"{V2}/courses/{copy}/content/import", files=zip_file)
    assert r.status_code == 200, r.text
    assert r.json()["modules"] == 2
    assert [m["code"] for m in prof.get(f"{V2}/courses/{copy}/modules").json()] == ["intro", "blood_pressure"]


def test_edits_of_the_served_course_reach_the_running_tutor(make_client):
    with make_client({"content": {"seed_status": "active"}}) as client:
        services = client.app.state.services
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)  # demo course instructor
        prof = _login(client.app, "prof")
        demo = services.content.course_id
        items = prof.get(f"{V2}/courses/{demo}/check-items").json()
        target = next(i for i in items if i["status"] == "active")
        assert services.content.item(target["code"]).active
        r = prof.patch(f"{V2}/courses/{demo}/check-items/{target['id']}", json={"status": "retired"})
        assert r.status_code == 200
        assert not services.content.item(target["code"]).active  # this process: at once
        assert services.learner.content is services.content  # the learner model uses the new content
        assert services.components.runner is not None
        with Session(services.engine) as db:  # another process's edit: picked up by the next sync
            from app.storage.models import CheckItem, Course

            row = db.get(CheckItem, target["id"])
            row.status = "active"
            db.add(row)
            course = db.get(Course, demo)
            course.content_version += 1
            db.add(course)
            db.commit()
        services.component_manager.sync()
        assert services.content.item(target["code"]).active
