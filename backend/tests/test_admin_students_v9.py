"""v5 V9: the admin manages student accounts from term to term: list, deactivate and reactivate, reset the
password, delete the account with its data. Admin only. Fictional data."""
import pytest
from fastapi.testclient import TestClient

from tests.test_ask_v2 import PASSWORD, V2, World, _login, rows

URL = f"{V2}/admin/students"


@pytest.fixture
def world(make_client):
    with make_client() as client:
        w = World(client)  # alice is enrolled in the course, bob in none
        w.consent("alice")
        w.services.accounts.create_admin("root", PASSWORD, must_change=False)
        w.admin = _login(w.app, "root")
        yield w


def _row(world, name: str) -> dict:
    return next(s for s in world.admin.get(URL).json() if s["account_id"] == world.students[name].id)


def test_the_admin_lists_students_with_their_courses(world):
    alice, bob = _row(world, "alice"), _row(world, "bob")
    assert alice["courses"] == bob["courses"] + 1  # both are in the demo course, alice also in this one
    assert alice["active"] and alice["display_name"] == "Alice"
    assert {"password_hash", "student_id"}.isdisjoint(alice)  # no secret, no pseudonym


def test_deactivate_ends_the_sessions_and_reactivate_allows_login_again(world):
    alice = _login(world.app, "alice")
    sid = world.students["alice"].id
    r = world.admin.patch(f"{URL}/{sid}", json={"active": False})
    assert r.status_code == 200 and r.json()["active"] is False
    assert alice.get(f"{V2}/auth/me").status_code == 401  # the open session ended
    login = TestClient(world.app).post(f"{V2}/auth/login", json={"username": "alice", "password": PASSWORD})
    assert login.status_code in (401, 403)
    assert world.admin.patch(f"{URL}/{sid}", json={"active": True}).json()["active"] is True
    _login(world.app, "alice")


def test_a_reset_gives_a_temporary_password(world):
    r = world.admin.post(f"{URL}/{world.students['bob'].id}/reset-password")
    assert r.status_code == 200 and len(r.json()["temporary_password"]) >= 10
    assert _row(world, "bob")["must_change_password"] is True


def test_delete_removes_the_account_and_its_learning_data(world):
    alice = _login(world.app, "alice")
    alice.post(f"{world.url}/check", json={"item_id": "C.1-q1", "choice": "A"})
    student_id = world.students["alice"].student_id
    assert any(r["student_id"] == student_id for r in rows("evidence_log"))
    assert world.admin.delete(f"{URL}/{world.students['alice'].id}").status_code == 204
    assert all(r["student_id"] != student_id for r in rows("evidence_log"))
    assert all(r["account_id"] != world.students["alice"].id for r in rows("course_member"))
    assert world.admin.delete(f"{URL}/{world.students['alice'].id}").status_code == 404
    assert any(a["action"] == "admin.student.delete" for a in rows("audit_log"))


def test_delete_leaves_nothing_with_the_students_id(world):
    from sqlmodel import Session

    from app.storage.models import AuditLog, Quiz
    alice, bob = world.students["alice"], world.students["bob"]
    sid = alice.student_id
    with Session(world.services.engine) as db:
        cid = world.course
        db.add(Quiz(course_id=cid, title="Q", assigned_to=[sid, bob.student_id]))
        db.add(AuditLog(account_id=None, action="learner.plan.update", target=f"course:{cid}",
                        details={"student_id": sid, "focus_kcs": ["k"], "goal": "pass"}))
        db.add(AuditLog(account_id=alice.id, action="learner.visibility.ack", target=f"course:{cid}",
                        details={}))
        db.commit()
    assert world.admin.delete(f"{URL}/{alice.id}").status_code == 204
    quizzes, audit = rows("quiz"), rows("audit_log")
    assert [q["assigned_to"] for q in quizzes if q["title"] == "Q"] == [[bob.student_id]]
    assert sid not in str(audit) and "pass" not in str(audit)
    assert all(a["account_id"] != alice.id for a in audit)
    assert any(a["action"] == "learner.plan.update" for a in audit)  # the trail stays
    assert any(a["action"] == "admin.student.delete" for a in audit)


def test_the_course_count_ignores_archived_courses(world):
    from sqlmodel import Session

    from app.storage.models import Course
    before = _row(world, "alice")["courses"]
    with Session(world.services.engine) as db:
        course = db.get(Course, world.course)
        course.status = "archived"
        db.add(course)
        db.commit()
    assert _row(world, "alice")["courses"] == before - 1


def test_staff_accounts_are_not_student_accounts(world):
    staff = world.admin.get(f"{V2}/admin/instructors").json()
    prof_id = next(a["account_id"] for a in staff if a["username"] == "prof")
    assert world.admin.patch(f"{URL}/{prof_id}", json={"active": False}).status_code == 404
    assert world.admin.delete(f"{URL}/{prof_id}").status_code == 404


def test_only_the_admin_manages_student_accounts(world):
    target = f"{URL}/{world.students['bob'].id}"
    for client, code in ((world.prof, 403), (_login(world.app, "alice"), 403)):
        assert client.get(URL).status_code == code
        assert client.patch(target, json={"active": False}).status_code == code
        assert client.post(f"{target}/reset-password").status_code == code
        assert client.delete(target).status_code == code
    anonymous = TestClient(world.app)  # logged out: no session (writes also lack the CSRF token)
    assert anonymous.get(URL).status_code == 401
    assert anonymous.patch(target, json={"active": False}).status_code in (401, 403)
    assert anonymous.delete(target).status_code in (401, 403)
    assert _row(world, "bob")["active"] is True
