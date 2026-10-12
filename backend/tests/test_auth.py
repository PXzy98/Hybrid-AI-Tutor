from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.auth.service import AccountService, InvalidUsername, PasswordPolicyError, normalize_username
from app.core.services import build_services
from app.storage.models import Account, AuthSession, utcnow
from tests.conftest import PASSWORD

LOGIN = "/api/v1/auth/login"


def test_login_me_logout(api):
    api.make_student()
    r = api.login("Alice")  # usernames are case-insensitive
    me = r.json()
    assert me == {"username": "alice", "display_name": "Alice Tremblay", "role": "student",
                  "must_change_password": False}
    cookie = r.headers["set-cookie"].lower()
    assert "httponly" in cookie and "samesite=lax" in cookie
    assert api.client.get("/api/v1/auth/me").json()["username"] == "alice"
    assert api.client.post("/api/v1/auth/logout").status_code == 204
    assert api.client.get("/api/v1/auth/me").status_code == 401


def test_session_token_is_stored_only_as_hash(api):
    api.make_student()
    token = api.login("alice").cookies.get("tutor_session")
    with Session(api.accounts.engine) as db:
        stored = db.exec(select(AuthSession.token_hash)).all()
    assert token and token not in stored and len(stored[0]) == 64


@pytest.mark.parametrize(("username", "password"), [("alice", "wrong-password"), ("nobody", PASSWORD),
                                                     ("!!", PASSWORD)])
def test_login_errors_are_generic(api, username, password):
    api.make_student()
    r = api.login(username, password, expect=401)
    assert r.json()["detail"] == "invalid username or password"


def test_lockout_after_repeated_failures(api, monkeypatch):
    api.make_student()
    for _ in range(api.accounts.cfg.max_failed_logins):
        api.login("alice", "wrong-password", expect=401)
    api.login("alice", PASSWORD, expect=429)  # even the right password is refused while locked
    with Session(api.accounts.engine) as db:  # time passes: unlock
        a = db.exec(select(Account).where(Account.username == "alice")).one()
        a.locked_until = utcnow() - timedelta(seconds=1)
        db.add(a)
        db.commit()
    api.login("alice", PASSWORD)


def test_deactivated_account_cannot_log_in(api):
    alice = api.make_student()
    api.accounts.update_student(alice.id, active=False)
    api.login("alice", expect=401)


def test_temporary_password_forces_a_change(api):
    api.make_student(must_change=True)
    temp = api.last_temp_password
    me = api.login("alice", temp).json()
    assert me["must_change_password"] is True
    c = api.client
    assert c.get("/api/v1/auth/me").status_code == 200  # allowed, so the client can react
    assert c.post("/api/v1/ask", json={"topic": "asthma", "question": "q"}).json()["detail"] == \
        "password change required"
    assert c.get("/api/v1/topics").status_code == 403
    r = c.post("/api/v1/auth/change-password", json={"current_password": temp, "new_password": "short"})
    assert r.status_code == 422
    r = c.post("/api/v1/auth/change-password", json={"current_password": "nope", "new_password": PASSWORD})
    assert r.status_code == 400
    r = c.post("/api/v1/auth/change-password", json={"current_password": temp, "new_password": PASSWORD})
    assert r.status_code == 200 and r.json()["must_change_password"] is False
    assert c.get("/api/v1/topics").status_code == 200  # same session keeps working


def test_change_password_ends_other_sessions(api):
    from fastapi.testclient import TestClient

    api.make_student()
    other = TestClient(api.client.app)  # a second device
    other.post(LOGIN, json={"username": "alice", "password": PASSWORD})
    api.login("alice")
    assert other.get("/api/v1/auth/me").status_code == 200
    api.client.post("/api/v1/auth/change-password",
                    json={"current_password": PASSWORD, "new_password": "another-good-password"})
    assert other.get("/api/v1/auth/me").status_code == 401
    assert api.client.get("/api/v1/auth/me").status_code == 200


def test_expired_session_is_rejected(api):
    api.make_student()
    api.login("alice")
    with Session(api.accounts.engine) as db:
        for row in db.exec(select(AuthSession)).all():
            row.expires_at = utcnow() - timedelta(minutes=1)
            db.add(row)
        db.commit()
    assert api.client.get("/api/v1/auth/me").status_code == 401


@pytest.mark.parametrize("bad", ["ab", "x" * 33, "has space", "Ünïcode", "a/b"])
def test_username_rules(bad):
    with pytest.raises(InvalidUsername):
        normalize_username(bad)
    assert normalize_username("  Student.One_2-x ") == "student.one_2-x"


def test_password_policy(use_config):
    accounts: AccountService = build_services(use_config()).accounts
    with pytest.raises(PasswordPolicyError):
        accounts.create_instructor("prof", "short")
    with pytest.raises(PasswordPolicyError):
        accounts.create_instructor("profprofprof", "ProfProfProf")  # same as the username


def test_instructor_bootstrap_from_env(make_client, monkeypatch):
    monkeypatch.setenv("INSTRUCTOR_USERNAME", "dr.abbas")
    monkeypatch.setenv("INSTRUCTOR_INITIAL_PASSWORD", "initial-password-1")
    with make_client() as client:
        r = client.post(LOGIN, json={"username": "dr.abbas", "password": "initial-password-1"})
        assert r.json() == {"username": "dr.abbas", "display_name": "dr.abbas", "role": "instructor",
                            "must_change_password": True}
    with make_client() as client:  # second start: no duplicate
        with Session(client.app.state.services.engine) as db:
            assert len(db.exec(select(Account).where(Account.role == "instructor")).all()) == 1


def test_cli_set_password_recovers_a_locked_instructor(use_config, monkeypatch):
    from app.auth import cli

    accounts = build_services(use_config()).accounts
    prof = accounts.create_instructor("prof", PASSWORD, must_change=False)
    with Session(accounts.engine) as db:
        a = db.get(Account, prof.id)
        a.locked_until = utcnow() + timedelta(hours=1)
        db.add(a)
        db.commit()
    monkeypatch.setattr(cli.getpass, "getpass", lambda prompt="": "brand-new-password")
    cli.main(["set-password", "prof"])
    account, _ = accounts.login("prof", "brand-new-password")
    assert account.username == "prof"
