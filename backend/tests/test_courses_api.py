"""Task Z9b: /api/v2 courses, members (CSV import), invitation codes and joining a course (course-structure.md
3.2 and 3.3), with access tests: another course's instructor, a student, logged out."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.storage.models import Account, CourseInvite, CourseMember, LoginIdentity, utcnow
from app.storage.testing import dump_rows
from tests.conftest import PASSWORD

V2 = "/api/v2"
DOMAINS = {"limits": {"accounts": {"allowed_email_domains": ["uottawa.ca", "demo.invalid"]}}}


class World:
    """One app, one TestClient per person (each keeps its own session cookie)."""

    def __init__(self, client: TestClient) -> None:
        self.app = client.app
        self.services = client.app.state.services
        self.accounts = self.services.accounts
        self.anon = TestClient(self.app)

    def client(self, login: str | None = None, password: str = PASSWORD) -> TestClient:
        c = TestClient(self.app)
        if login:
            r = c.post(f"{V2}/auth/login", json={"username": login, "password": password})
            assert r.status_code == 200, r.text
        return c

    def student(self, username: str) -> Account:
        account, _ = self.accounts.create_student(username, username.title())
        return self.accounts.set_password(account.id, PASSWORD, must_change=False)

    def course(self, owner: TestClient, code: str = "ELG 5902") -> int:
        body = {"code": code, "title": "Fictional course", "course_type": "ece"}
        r = owner.post(f"{V2}/courses", json=body)
        assert r.status_code == 201, r.text
        return r.json()["id"]


@pytest.fixture
def world(make_client):
    with make_client(DOMAINS) as client:
        yield World(client)


def _import(client: TestClient, course_id: int, text: str):
    return client.post(f"{V2}/courses/{course_id}/members/import",
                       files={"file": ("roster.csv", text.encode("utf-8"), "text/csv")})


def test_courses_are_created_by_instructors_and_seen_only_by_their_members(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    world.accounts.create_instructor("other", PASSWORD, must_change=False)
    world.student("alice")
    prof, other, alice = world.client("prof"), world.client("other"), world.client("alice@demo.invalid")
    course_id = world.course(prof)
    assert [c["code"] for c in prof.get(f"{V2}/courses").json()] == ["ELG 5902", "MED 0000"]
    assert prof.get(f"{V2}/courses/{course_id}").json()["my_role"] == "instructor"
    new = {"code": "X 1", "title": "X", "course_type": "ece"}
    assert alice.post(f"{V2}/courses", json=new).status_code == 403
    assert prof.post(f"{V2}/courses", json={"code": "ELG 5902", "title": "Again",
                                             "course_type": "ece"}).status_code == 409
    for outsider in (other, alice):  # another instructor, a student of another course
        assert outsider.get(f"{V2}/courses/{course_id}").status_code == 404
        assert outsider.patch(f"{V2}/courses/{course_id}", json={"title": "Taken"}).status_code == 404
        assert "ELG 5902" not in {c["code"] for c in outsider.get(f"{V2}/courses").json()}
    assert world.anon.get(f"{V2}/courses").status_code == 401
    assert world.anon.get(f"{V2}/courses/{course_id}").status_code == 401
    r = prof.patch(f"{V2}/courses/{course_id}", json={"title": "Renamed", "term_label": "Winter 2027"})
    assert (r.json()["title"], r.json()["term_label"]) == ("Renamed", "Winter 2027")
    me = alice.get(f"{V2}/auth/me").json()
    assert me["system_role"] == "student" and [m["code"] for m in me["memberships"]] == ["MED 0000"]


def test_a_course_type_disabled_by_the_admin_cannot_be_created(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    _, version, _ = world.services.settings_service.system_values()
    world.services.settings_service.save_system({"enabled_course_types": ["medical_science"]},
                                                expected_version=version, account_id=None)
    prof = world.client("prof")
    r = prof.post(f"{V2}/courses", json={"code": "E 1", "title": "E", "course_type": "ece"})
    assert r.status_code == 422 and r.json()["code"] == "invalid"
    _, version, _ = world.services.settings_service.system_values()
    world.services.settings_service.save_system({"enabled_course_types": []}, expected_version=version,
                                                account_id=None)
    r = prof.post(f"{V2}/courses", json={"code": "M 1", "title": "M", "course_type": "medical_science"})
    assert r.status_code == 422  # an empty list disables every type


def test_roster_import_report_and_nothing_but_the_email_is_stored(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    world.student("alice")
    prof = world.client("prof")
    course_id = world.course(prof)
    csv_text = ("Email,display_name,Student Number\n"
                "alice@demo.invalid,Alice,S7777771\n"
                "New.One@uottawa.ca,New One,S7777772\n"
                "new.one@uottawa.ca,Duplicate,S7777773\n"
                "someone@gmail.com,Gmail,S7777774\n"
                "not-an-email,Bad,S7777775\n"
                "prof@demo.invalid,Prof,S7777776\n"
                ",,\n")
    r = _import(prof, course_id, csv_text)
    assert r.status_code == 200, r.text
    report = r.json()
    assert report["added"] == ["alice@demo.invalid"] and report["pending"] == ["new.one@uottawa.ca"]
    assert [(x["row"], x["reason"]) for x in report["rejected"]] == [
        (4, "duplicate in the file"), (5, "e-mail domain not allowed"), (6, "not a valid e-mail address"),
        (7, "not a student account")]
    again = _import(prof, course_id, csv_text).json()
    assert again["unchanged"] == ["alice@demo.invalid", "new.one@uottawa.ca"]
    dump = dump_rows(world.services.settings.database_url)
    assert "new.one@uottawa.ca" in dump and "S777777" not in dump  # other columns are not stored
    members = {(m["email"], m["status"]) for m in prof.get(f"{V2}/courses/{course_id}/members").json()}
    assert members == {("prof@demo.invalid", "active"), ("alice@demo.invalid", "active"),
                       ("new.one@uottawa.ca", "pending")}
    assert _import(prof, course_id, "name\nx\n").status_code == 422  # no email column
    alice = world.client("alice")
    assert alice.get(f"{V2}/courses/{course_id}").json()["my_role"] == "student"
    assert alice.get(f"{V2}/courses/{course_id}/members").status_code == 404


def test_a_new_student_activates_with_the_code_and_all_his_pending_memberships_become_active(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    prof = world.client("prof")
    first, second = world.course(prof, "ELG 5902"), world.course(prof, "ELG 5903")
    for course_id in (first, second):
        _import(prof, course_id, "email\nnew.one@uottawa.ca\n")
    code = prof.post(f"{V2}/courses/{first}/invite/rotate").json()["code"]
    body = {"code": code, "email": "New.One@uottawa.ca", "display_name": "New One",
            "password": "a-good-new-password"}
    refused = [{**body, "code": "wrong-code"}, {**body, "email": "stranger@uottawa.ca"},
               {**body, "email": "new.one@gmail.com"}]
    for bad in refused:
        r = world.anon.post(f"{V2}/auth/join", json=bad)
        assert r.status_code == 400 and r.json()["code"] == "invalid", r.text
    assert world.anon.post(f"{V2}/auth/join", json={"code": code}).status_code == 422
    student = TestClient(world.app)
    r = student.post(f"{V2}/auth/join", json=body)
    assert r.status_code == 200, r.text
    me = r.json()["me"]
    assert r.json()["course_id"] == first
    assert (me["username"], me["email"]) == ("new.one", "new.one@uottawa.ca")
    assert {m["course_id"] for m in me["memberships"]} == {first, second}  # both pending ones
    assert student.get(f"{V2}/courses/{second}").status_code == 200  # logged in by the join
    again = world.anon.post(f"{V2}/auth/join", json=body)
    assert again.status_code == 400 and "log in" in again.json()["detail"]  # never a second account
    with Session(world.services.engine) as db:  # identity data only in `account` (privacy invariant 6)
        account = db.exec(select(Account).where(Account.username == "new.one")).one()
        rows = db.exec(select(CourseMember).where(CourseMember.account_id == account.id)).all()
        assert [m.email for m in rows] == [None, None]
        subject = db.exec(select(LoginIdentity.subject).where(LoginIdentity.account_id == account.id)).one()
        assert subject == f"account:{account.id}"
    invite = prof.get(f"{V2}/courses/{first}/invite").json()
    assert invite["uses"] == 1 and "code" not in invite


def test_a_logged_in_student_joins_with_the_code_and_keeps_his_password(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    alice = world.student("alice")
    prof = world.client("prof")
    course_id = world.course(prof)
    with Session(world.services.engine) as db:  # imported before her account existed
        db.add(CourseMember(course_id=course_id, email=alice.email, role="student", status="pending"))
        db.commit()
    code = prof.post(f"{V2}/courses/{course_id}/invite/rotate").json()["code"]
    world.student("bob")
    assert world.client("bob").post(f"{V2}/auth/join", json={"code": code}).status_code == 400  # not listed
    student = world.client("alice")
    assert student.get(f"{V2}/courses/{course_id}").status_code == 404
    r = student.post(f"{V2}/auth/join", json={"code": code.upper()})  # codes ignore case
    assert r.status_code == 200 and r.json()["course_id"] == course_id
    assert student.get(f"{V2}/courses/{course_id}").status_code == 200
    world.client("alice")  # same password
    instructor = world.client("prof")
    assert instructor.post(f"{V2}/auth/join", json={"code": code}).status_code == 400  # students only


def test_an_expired_or_rotated_code_does_not_work(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    prof = world.client("prof")
    course_id = world.course(prof)
    _import(prof, course_id, "email\nnew.one@uottawa.ca\n")
    old = prof.post(f"{V2}/courses/{course_id}/invite/rotate").json()["code"]
    new = prof.post(f"{V2}/courses/{course_id}/invite/rotate").json()["code"]
    body = {"email": "new.one@uottawa.ca", "display_name": "New", "password": "a-good-new-password"}
    assert world.anon.post(f"{V2}/auth/join", json={**body, "code": old}).status_code == 400
    with Session(world.services.engine) as db:
        invite = db.exec(select(CourseInvite).where(CourseInvite.course_id == course_id)).one()
        invite.expires_at = utcnow() - timedelta(minutes=1)
        db.add(invite)
        db.commit()
    assert world.anon.post(f"{V2}/auth/join", json={**body, "code": new}).status_code == 400
    assert prof.get(f"{V2}/courses/{course_id}/invite").json()["expired"] is True


def test_join_is_rate_limited(make_client):
    limits = {"limits": {"accounts": {"join_attempts_per_hour": 2}}}
    with make_client(limits) as client:
        for _ in range(2):
            assert client.post(f"{V2}/auth/join", json={"code": "nope"}).status_code in (400, 422)
        r = client.post(f"{V2}/auth/join", json={"code": "nope"})
        assert r.status_code == 429 and r.json()["code"] == "usage_limit"
        assert r.json()["retry_after_seconds"] > 0


def test_members_co_instructors_removal_and_password_reset(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    world.accounts.create_instructor("coprof", PASSWORD, must_change=False)
    world.accounts.create_instructor("other", PASSWORD, must_change=False)
    world.student("alice")
    prof = world.client("prof")
    course_id = world.course(prof)
    _import(prof, course_id, "email\nalice@demo.invalid\n")
    url = f"{V2}/courses/{course_id}/members"
    assert prof.post(f"{url}/instructors", json={"email": "nobody@demo.invalid"}).status_code == 404
    co = prof.post(f"{url}/instructors", json={"email": "coprof@demo.invalid"})
    assert co.status_code == 201 and co.json()["role"] == "instructor"
    assert prof.post(f"{url}/instructors", json={"email": "coprof@demo.invalid"}).status_code == 409
    coprof = world.client("coprof")
    assert coprof.get(f"{V2}/courses/{course_id}").json()["my_role"] == "instructor"
    members = {m["username"]: m for m in prof.get(url).json()}
    alice_member, prof_member = members["alice"]["id"], members["prof"]["id"]
    other, alice = world.client("other"), world.client("alice")
    for outsider in (other, alice):
        assert outsider.get(url).status_code == 404
        assert outsider.post(f"{url}/{alice_member}/reset-password").status_code == 404
        assert outsider.delete(f"{url}/{alice_member}").status_code == 404
        assert _import(outsider, course_id, "email\nx@uottawa.ca\n").status_code == 404
        assert outsider.post(f"{url}/instructors", json={"email": "other@demo.invalid"}).status_code == 404
    assert world.anon.get(url).status_code == 401
    assert prof.post(f"{url}/{prof_member}/reset-password").status_code == 422  # students only
    temp = prof.post(f"{url}/{alice_member}/reset-password").json()["temporary_password"]
    assert alice.get(f"{V2}/auth/me").status_code == 401  # sessions ended
    me = world.client("alice", temp).get(f"{V2}/auth/me").json()
    assert me["must_change_password"] is True
    assert coprof.delete(f"{url}/{prof_member}").status_code == 204
    only = {m["username"]: m["id"] for m in coprof.get(url).json()}["coprof"]
    assert coprof.delete(f"{url}/{only}").status_code == 409  # the last instructor stays
    assert coprof.delete(f"{url}/{alice_member}").status_code == 204
    assert prof.get(f"{V2}/courses/{course_id}").status_code == 404  # removed


def test_archive_needs_an_ended_term_and_hides_the_course_from_students(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    world.student("alice")
    prof = world.client("prof")
    course_id = world.course(prof)
    _import(prof, course_id, "email\nalice@demo.invalid\n")
    prof.post(f"{V2}/courses/{course_id}/invite/rotate")
    alice = world.client("alice")
    assert alice.post(f"{V2}/courses/{course_id}/archive").status_code == 404
    assert prof.post(f"{V2}/courses/{course_id}/archive").status_code == 409  # still has students
    members = prof.get(f"{V2}/courses/{course_id}/members").json()
    alice_member = {m["username"]: m["id"] for m in members}["alice"]
    prof.delete(f"{V2}/courses/{course_id}/members/{alice_member}")
    r = prof.post(f"{V2}/courses/{course_id}/archive")
    assert r.status_code == 200 and r.json()["status"] == "archived"
    assert prof.get(f"{V2}/courses/{course_id}/invite").json() is None  # the code stops working
    assert _import(prof, course_id, "email\nalice@demo.invalid\n").status_code == 422


def test_login_by_email_and_admin_sees_every_course(world):
    world.accounts.create_instructor("prof", PASSWORD, must_change=False)
    world.accounts.create_admin("root", PASSWORD, must_change=False)
    course_id = world.course(world.client("prof"))
    r = world.anon.post(f"{V2}/auth/login", json={"username": "PROF@demo.invalid", "password": PASSWORD})
    assert r.status_code == 200 and r.json()["system_role"] == "instructor"
    assert world.anon.post(f"{V2}/auth/login", json={"username": "prof@demo.invalid",
                                                     "password": "wrong-password"}).status_code == 401
    root = world.client("root")
    assert root.get(f"{V2}/courses/{course_id}").json()["my_role"] == "instructor"
    assert {c["id"] for c in root.get(f"{V2}/courses").json()} >= {course_id}
    assert root.get(f"{V2}/auth/me").json()["system_role"] == "admin"
    assert root.post(f"{V2}/auth/logout").status_code == 204
    assert root.get(f"{V2}/auth/me").status_code == 401


def test_a_new_profile_file_is_a_course_type_of_the_api(world, tmp_path, monkeypatch):
    """Z7 + Z9: the course types are the privacy profile files; the API takes a new one without a change."""
    from app.privacy import profiles

    for name in ("base", "general", "medical_science", "ece", "life_science"):
        (tmp_path / f"{name}.yaml").write_text((profiles.PROFILE_DIR / f"{name}.yaml").read_text("utf-8"),
                                               encoding="utf-8")
    (tmp_path / "law.yaml").write_text("extends: base\nrecognizers: []\n", encoding="utf-8")
    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path)
    profiles._raw.cache_clear()
    profiles.privacy_profile.cache_clear()
    try:
        world.accounts.create_instructor("prof", PASSWORD, must_change=False)
        prof = world.client("prof")
        r = prof.post(f"{V2}/courses", json={"code": "LAW 1", "title": "Law", "course_type": "law"})
        assert r.status_code == 201 and r.json()["course_type"] == "law"
        assert prof.get(f"{V2}/courses/{r.json()['id']}").json()["course_type"] == "law"
        bad = prof.post(f"{V2}/courses", json={"code": "X 1", "title": "X", "course_type": "astrology"})
        assert bad.status_code == 422
    finally:
        profiles._raw.cache_clear()
        profiles.privacy_profile.cache_clear()
