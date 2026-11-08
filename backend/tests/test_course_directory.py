"""Task Z9a: system roles, login identities and the database course directory behind require_course_role."""
from alembic import command
from sqlalchemy import text
from sqlmodel import Session, select

from app.catalog import create_course
from app.core.services import build_services
from app.platform.access import DbCourseDirectory
from app.storage.db import alembic_config, make_engine
from app.storage.models import Account, Course, CourseMember, LoginIdentity
from app.storage.testing import temporary_database
from tests.conftest import PASSWORD


def _member(db, course_id, account_id, role, status="active"):
    db.add(CourseMember(course_id=course_id, account_id=account_id, role=role, status=status))


def test_memberships_decide_course_access(use_config):
    services = build_services(use_config())
    directory = DbCourseDirectory(services.engine)
    accounts = services.accounts
    alice, _ = accounts.create_student("alice", "Alice")  # API v1: a member of the demo course
    bob, _ = accounts.create_student("bob", "Bob")
    prof = accounts.create_instructor("prof", PASSWORD, must_change=False)
    admin = accounts.create_admin("root", PASSWORD, must_change=False)
    demo = services.content.course_id
    with Session(services.engine) as db:
        other = create_course(db, code="ELG 5902", title="Fictional course", course_type="ece")
        _member(db, other.id, alice.id, "student", status="pending")
        db.commit()
        other_id = other.id
    assert directory.membership(alice.id, demo).role == "student"
    assert directory.membership(alice.id, demo).student_id == alice.student_id
    assert directory.membership(prof.id, demo).role == "instructor"
    assert directory.membership(alice.id, other_id) is None  # pending
    assert directory.membership(prof.id, other_id) is None  # not a member
    assert directory.membership(admin.id, other_id).role == "instructor"  # admin manages every course
    assert directory.membership(alice.id, 9999) is None
    _deactivate(services, bob.id)
    assert directory.membership(bob.id, demo) is None
    with Session(services.engine) as db:
        course = db.get(Course, demo)
        course.status = "archived"
        db.add(course)
        db.commit()
    assert directory.membership(alice.id, demo) is None  # students leave an archived course
    assert directory.membership(prof.id, demo).role == "instructor"


def _deactivate(services, account_id):
    with Session(services.engine) as db:
        account = db.get(Account, account_id)
        account.active = False
        db.add(account)
        db.commit()


def test_new_accounts_have_an_email_a_password_identity_and_the_demo_membership(use_config):
    services = build_services(use_config())
    alice, _ = services.accounts.create_student("alice", "Alice")
    with Session(services.engine) as db:
        assert db.get(Account, alice.id).email == "alice@demo.invalid"
        identity = db.exec(select(LoginIdentity).where(LoginIdentity.account_id == alice.id)).one()
        assert (identity.provider, identity.subject) == ("password", f"account:{alice.id}")  # no username
        member = db.exec(select(CourseMember).where(CourseMember.account_id == alice.id)).one()
        demo = services.content.course_id
        assert (member.course_id, member.role, member.status) == (demo, "student", "active")
        assert member.email is None  # identity data only in `account` (privacy invariant 6)


def test_an_admin_uses_the_instructor_pages_of_api_v1(make_client):
    with make_client() as client:
        client.app.state.services.accounts.create_admin("root", PASSWORD, must_change=False)
        me = client.post("/api/v1/auth/login", json={"username": "root", "password": PASSWORD}).json()
        assert me["role"] == "instructor"
        assert client.get("/api/v1/admin/students").status_code == 200


def test_migration_0005_fills_in_accounts_from_before():
    with temporary_database() as url:
        engine = make_engine(url, pooled=False)
        cfg = alembic_config(engine)
        command.downgrade(cfg, "0004")
        with engine.begin() as conn:
            conn.execute(text("INSERT INTO course (code, title, term_label, course_type, visibility_mode, "
                              "status, created_at) VALUES ('MED 0000', 'General Medical Knowledge', '', "
                              "'medical_science', 'A', 'active', now())"))
            for name, role in (("prof", "instructor"), ("alice", "student")):
                conn.execute(text("INSERT INTO account (username, display_name, role, password_hash, "
                                  "active, must_change_password, failed_logins, created_at) "
                                  "VALUES (:u, :u, :r, 'x', true, false, 0, now())"), {"u": name, "r": role})
        command.upgrade(cfg, "head")
        with Session(engine) as db:
            rows = {a.username: a for a in db.exec(select(Account)).all()}
            assert rows["alice"].email == "alice@demo.invalid" and rows["prof"].role == "admin"
            assert len(db.exec(select(LoginIdentity)).all()) == 2
            members = db.exec(select(CourseMember)).all()
            assert {(m.account_id, m.role) for m in members} == {(rows["alice"].id, "student"),
                                                                 (rows["prof"].id, "instructor")}
        engine.dispose()
