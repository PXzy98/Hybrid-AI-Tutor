"""Task Z9d: /api/v2 settings (system and course), admin instructor accounts, and the student's preferences
and consent, with access tests: another course's instructor, a student, logged out."""
import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session

from app.storage.models import CourseMember, SystemSettings
from tests.conftest import PASSWORD

V2 = "/api/v2"


def _login(app, username: str, password: str = PASSWORD) -> TestClient:
    c = TestClient(app)
    r = c.post(f"{V2}/auth/login", json={"username": username, "password": password})
    assert r.status_code == 200, r.text
    return c


@pytest.fixture
def world(make_client):
    with make_client() as client:
        services = client.app.state.services
        accounts = services.accounts
        accounts.create_admin("root", PASSWORD, must_change=False)
        accounts.create_instructor("prof", PASSWORD, must_change=False)
        accounts.create_instructor("other", PASSWORD, must_change=False)
        alice, _ = accounts.create_student("alice", "Alice")
        accounts.set_password(alice.id, PASSWORD, must_change=False)
        app = client.app
        people = {name: _login(app, name) for name in ("root", "prof", "other", "alice")}
        course = people["prof"].post(f"{V2}/courses", json={"code": "ELG 5902", "title": "Fictional",
                                                            "course_type": "ece"}).json()["id"]
        with Session(services.engine) as db:
            db.add(CourseMember(course_id=course, account_id=alice.id, role="student", status="active"))
            db.commit()
        yield {"app": app, "services": services, "course": course, "anon": TestClient(app), **people}


def test_system_settings_are_admin_only_versioned_and_restorable(world):
    root = world["root"]
    for who in ("prof", "alice"):
        assert world[who].get(f"{V2}/admin/settings").status_code == 403
        assert world[who].get(f"{V2}/admin/settings/apply-status").status_code == 403
    assert world["anon"].get(f"{V2}/admin/settings").status_code == 401
    current = root.get(f"{V2}/admin/settings").json()
    r = root.put(f"{V2}/admin/settings", json={"values": {"enabled_course_types": ["ece"]},
                                               "version": current["version"]})
    assert r.status_code == 200 and r.json()["values"]["enabled_course_types"] == ["ece"]
    stale = root.put(f"{V2}/admin/settings", json={"values": {}, "version": current["version"]})
    assert stale.status_code == 409 and stale.json()["code"] == "conflict"
    bad = root.put(f"{V2}/admin/settings", json={"values": {"checkers": []}, "version": r.json()["version"]})
    assert bad.status_code == 422 and "cannot be switched off" in bad.json()["detail"]
    history = root.get(f"{V2}/admin/settings/history").json()
    assert history[0]["changed"] == ["enabled_course_types"]
    first = r.json()["version"]
    root.put(f"{V2}/admin/settings", json={"values": {"enabled_course_types": ["ece", "general"]},
                                           "version": first})
    restored = root.post(f"{V2}/admin/settings/restore/{history[0]['id']}")
    assert restored.status_code == 200 and restored.json()["values"]["enabled_course_types"] == ["ece"]
    status = root.get(f"{V2}/admin/settings/apply-status").json()
    assert status["apply_state"] == "applied" and status["version"] == restored.json()["version"]
    assert all(p["kind"] in ("api", "worker") for p in status["processes"])


def test_a_system_change_being_applied_locks_the_settings(world):
    root = world["root"]
    version = root.get(f"{V2}/admin/settings").json()["version"]
    with Session(world["services"].engine) as db:
        row = db.get(SystemSettings, 1) or SystemSettings(id=1, version=version)
        row.apply_state, row.apply_target_version = "applying", row.version
        db.add(row)
        db.commit()
    r = root.put(f"{V2}/admin/settings", json={"values": {}, "version": version})
    assert r.status_code == 423 and r.json()["code"] == "settings_applying"
    assert root.get(f"{V2}/admin/settings/apply-status").json()["apply_state"] == "applying"


def test_course_settings_belong_to_the_course_instructors(world):
    url = f"{V2}/courses/{world['course']}/settings"
    prof = world["prof"]
    for who in ("other", "alice"):
        assert world[who].get(url).status_code == 404
        assert world[who].put(url, json={"values": {}, "version": 0}).status_code == 404
        assert world[who].get(f"{url}/history").status_code == 404
    assert world["anon"].get(url).status_code == 401
    current = prof.get(url).json()
    assert current == {"values": {k: None for k in current["values"]}, "version": 0}
    r = prof.put(url, json={"values": {"local_only": True, "routing_threshold": 0.7}, "version": 0})
    assert r.status_code == 200 and r.json()["values"]["local_only"] is True
    assert prof.put(url, json={"values": {}, "version": 0}).status_code == 409
    assert world["services"].effective(world["course"]).local_only is True
    entry = prof.get(f"{url}/history").json()[0]
    assert sorted(entry["changed"]) == ["local_only", "routing_threshold"]
    # an entry of another course, or of the system, is not restorable here
    other_course = world["other"].post(f"{V2}/courses", json={"code": "ELG 1", "title": "O",
                                                              "course_type": "ece"}).json()["id"]
    other_url = f"{V2}/courses/{other_course}/settings"
    world["other"].put(other_url, json={"values": {"local_only": False}, "version": 0})
    foreign = world["other"].get(f"{other_url}/history").json()[0]["id"]
    assert prof.post(f"{url}/restore/{foreign}").status_code == 404
    assert world["other"].post(f"{other_url}/restore/{entry['id']}").status_code == 404
    root = world["root"]
    v = root.get(f"{V2}/admin/settings").json()["version"]
    root.put(f"{V2}/admin/settings", json={"values": {"weak_evidence": False}, "version": v})
    system_entry = root.get(f"{V2}/admin/settings/history").json()[0]["id"]
    assert prof.post(f"{url}/restore/{system_entry}").status_code == 404
    assert root.post(f"{V2}/admin/settings/restore/{entry['id']}").status_code == 404
    prof.put(url, json={"values": {}, "version": 1})
    assert prof.post(f"{url}/restore/{entry['id']}").json()["values"]["local_only"] is True


def test_admin_manages_instructor_accounts(world):
    root, app = world["root"], world["app"]
    assert world["prof"].get(f"{V2}/admin/instructors").status_code == 403
    assert world["anon"].get(f"{V2}/admin/instructors").status_code == 401
    r = root.post(f"{V2}/admin/instructors", json={"email": "New.Prof@uottawa.ca", "display_name": "Dr. New"})
    assert r.status_code == 201, r.text
    new = r.json()
    assert (new["username"], new["email"], new["role"]) == ("new.prof", "new.prof@uottawa.ca", "instructor")
    assert root.post(f"{V2}/admin/instructors", json={"email": "new.prof@uottawa.ca",
                                                      "display_name": "Again"}).status_code == 409
    me = _login(app, "new.prof@uottawa.ca", new["temporary_password"]).get(f"{V2}/auth/me").json()
    assert me["must_change_password"] is True and me["memberships"] == []  # no demo membership
    listed = {a["username"] for a in root.get(f"{V2}/admin/instructors").json()}
    assert {"root", "prof", "other", "new.prof"} <= listed and "alice" not in listed
    aid = new["account_id"]
    assert root.patch(f"{V2}/admin/instructors/{aid}", json={"active": False}).json()["active"] is False
    bad = TestClient(app).post(f"{V2}/auth/login", json={"username": "new.prof",
                                                         "password": new["temporary_password"]})
    assert bad.status_code == 401
    promoted = root.patch(f"{V2}/admin/instructors/{aid}", json={"active": True, "role": "admin"})
    assert promoted.json()["role"] == "admin"
    temp = root.post(f"{V2}/admin/instructors/{aid}/reset-password").json()["temporary_password"]
    assert _login(app, "new.prof", temp).get(f"{V2}/admin/instructors").status_code == 403  # change first
    root_id = root.get(f"{V2}/auth/me").json()["account_id"]
    assert root.patch(f"{V2}/admin/instructors/{root_id}", json={"active": False}).status_code == 422
    assert root.patch(f"{V2}/admin/instructors/{root_id}", json={"role": "instructor"}).status_code == 422
    student_id = world["alice"].get(f"{V2}/auth/me").json()["account_id"]
    assert root.patch(f"{V2}/admin/instructors/{student_id}", json={"active": False}).status_code == 404
    assert root.post(f"{V2}/admin/instructors/{student_id}/reset-password").status_code == 404


def test_students_set_their_own_global_preferences_and_consent(world):
    alice = world["alice"]
    for who in ("prof", "root"):
        assert world[who].get(f"{V2}/me/preferences").status_code == 403
        assert world[who].put(f"{V2}/me/consent", json={"given": True}).status_code == 403
    assert world["anon"].get(f"{V2}/me/consent").status_code == 401
    assert alice.get(f"{V2}/me/consent").json() == {"given": None}
    assert alice.put(f"{V2}/me/preferences", json={"detail": "detailed"}).status_code == 409  # no consent
    assert alice.put(f"{V2}/me/consent", json={"given": True}).json() == {"given": True}
    r = alice.put(f"{V2}/me/preferences", json={"detail": "detailed", "sequencing": "concept_first"})
    assert r.status_code == 200
    assert (r.json()["detail"], r.json()["sequencing"]) == ("detailed", "concept_first")
    assert alice.get(f"{V2}/me/preferences").json()["detail"] == "detailed"
    assert alice.put(f"{V2}/me/preferences", json={"detail": "loud"}).status_code == 422
    assert alice.put(f"{V2}/me/consent", json={"given": False}).json() == {"given": False}
    assert alice.get(f"{V2}/me/preferences").json()["detail"] == "concise"  # withdrawing forgets the profile
