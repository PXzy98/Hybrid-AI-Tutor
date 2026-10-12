import sqlite3

import pytest
from sqlalchemy import Column, Integer, String, Table
from sqlmodel import SQLModel

from app.core.config import get_settings
from tests.conftest import PASSWORD

STUDENTS = "/api/v1/admin/students"


def rows(table: str, where: str = "") -> list:
    path = get_settings().database_url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        return con.execute(f"SELECT * FROM {table} {where}").fetchall()  # noqa: S608


def test_instructor_creates_a_student_who_must_change_password(instructor_client, api):
    r = instructor_client.post(STUDENTS, json={"username": "Student.One", "display_name": "S One"})
    assert r.status_code == 201
    assert r.headers["cache-control"] == "no-store"
    created = r.json()
    assert created["account"]["username"] == "student.one" and created["account"]["must_change_password"]
    assert set(created["account"]) == {"id", "username", "display_name", "active", "must_change_password",
                                       "created_at", "last_login_at"}  # account data only
    temp = created["temporary_password"]
    assert len(temp) >= 12
    me = api.login("student.one", temp).json()
    assert me["role"] == "student" and me["must_change_password"] is True


def test_duplicate_and_invalid_usernames(instructor_client):
    assert instructor_client.post(STUDENTS, json={"username": "bob"}).status_code == 201
    assert instructor_client.post(STUDENTS, json={"username": "BOB"}).status_code == 409
    assert instructor_client.post(STUDENTS, json={"username": "bad name"}).status_code == 422


def test_list_shows_students_only(instructor_client):
    instructor_client.post(STUDENTS, json={"username": "zed"})
    instructor_client.post(STUDENTS, json={"username": "amy"})
    names = [s["username"] for s in instructor_client.get(STUDENTS).json()]
    assert names == ["amy", "zed"]  # sorted; the instructor itself is not listed


def test_students_and_anonymous_callers_cannot_manage_accounts(api):
    assert api.client.get(STUDENTS).status_code == 401
    api.make_student()
    api.login("alice")
    assert api.client.get(STUDENTS).status_code == 403
    assert api.client.post(STUDENTS, json={"username": "mallory"}).status_code == 403


def test_instructor_cannot_use_student_endpoints(instructor_client):
    r = instructor_client.post("/api/v1/ask", json={"topic": "asthma", "question": "q"})
    assert r.status_code == 403


def test_endpoints_act_only_on_student_accounts(api):
    prof = api.make_instructor()
    api.login("prof")
    c = api.client
    assert c.delete(f"{STUDENTS}/{prof.id}").status_code == 404  # cannot delete itself
    assert c.post(f"{STUDENTS}/{prof.id}/reset-password").status_code == 404
    assert c.patch(f"{STUDENTS}/{prof.id}", json={"active": False}).status_code == 404
    assert c.delete(f"{STUDENTS}/999").status_code == 404


def test_reset_password_ends_sessions_and_forces_change(api):
    from fastapi.testclient import TestClient

    alice = api.make_student()
    student = TestClient(api.client.app)
    student.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    api.make_instructor()
    api.login("prof")
    r = api.client.post(f"{STUDENTS}/{alice.id}/reset-password")
    assert r.status_code == 200 and r.headers["cache-control"] == "no-store"
    assert student.get("/api/v1/auth/me").status_code == 401  # logged out at once
    me = api.login("alice", r.json()["temporary_password"]).json()
    assert me["must_change_password"] is True


def test_deactivate_ends_sessions_and_reactivate_restores_login(api):
    from fastapi.testclient import TestClient

    alice = api.make_student()
    student = TestClient(api.client.app)
    student.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    api.make_instructor()
    api.login("prof")
    r = api.client.patch(f"{STUDENTS}/{alice.id}", json={"active": False, "display_name": "A. T."})
    assert r.json()["active"] is False and r.json()["display_name"] == "A. T."
    assert student.get("/api/v1/auth/me").status_code == 401
    api.client.patch(f"{STUDENTS}/{alice.id}", json={"active": True})
    assert student.post("/api/v1/auth/login",
                        json={"username": "alice", "password": PASSWORD}).status_code == 200


@pytest.fixture
def extra_student_table():
    """A throw-away table with a student_id column, standing in for tables added in later steps."""
    table = Table("future_learner_table", SQLModel.metadata, Column("id", Integer, primary_key=True),
                  Column("student_id", String, index=True), extend_existing=True)
    yield table
    SQLModel.metadata.remove(table)


def test_delete_purges_everything_and_anonymizes_logs(api, extra_student_table):
    from fastapi.testclient import TestClient

    alice = api.make_student()
    bob = api.make_student("bob", "Bob Ng")
    extra_student_table.create(api.accounts.engine)
    with api.accounts.engine.begin() as con:
        con.execute(extra_student_table.insert(), [{"student_id": alice.student_id},
                                                  {"student_id": bob.student_id}])
    student = TestClient(api.client.app)
    student.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
    r = student.post("/api/v1/ask", json={"topic": "asthma", "question": "What is asthma?"})
    sid = r.json()["session_id"]

    api.make_instructor()
    api.login("prof")
    assert api.client.delete(f"{STUDENTS}/{alice.id}").status_code == 204

    sid_alice = alice.student_id
    assert student.get("/api/v1/auth/me").status_code == 401  # cookie no longer works
    assert rows("account", "WHERE username = 'alice'") == []
    assert rows("session_turn", f"WHERE session_id = '{sid}'") == []
    assert rows("future_learner_table", f"WHERE student_id = '{sid_alice}'") == []
    # other students are untouched
    assert len(rows("future_learner_table", f"WHERE student_id = '{bob.student_id}'")) == 1
    logs = rows("request_log", f"WHERE session_id = '{sid}'")
    assert len(logs) == 1 and "deleted" in logs[0] and sid_alice not in logs[0]  # kept, anonymized
    api.login("alice", expect=401)
    api.login("prof")
    assert [s["username"] for s in api.client.get(STUDENTS).json()] == ["bob"]


def test_usernames_and_display_names_stay_in_the_account_table(api):
    api.make_student("alice", "Alice Tremblay")
    api.login("alice")
    api.client.post("/api/v1/ask", json={"topic": "asthma", "question": "What is asthma?"})
    for table in ("request_log", "session_turn", "auth_session"):
        dump = str(rows(table))
        assert "alice" not in dump.lower() and "Tremblay" not in dump
