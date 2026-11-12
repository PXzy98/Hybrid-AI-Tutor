"""Task Z10: CSRF on API v2, failed-login limits per client address, logout everywhere, usage counters."""
from datetime import timedelta

import pytest
from fastapi.testclient import TestClient
from sqlmodel import Session, select

from app.auth import csrf
from app.core.schemas import CourseRef
from app.platform import usage
from app.platform.usage import DbUsageMeter, UsageLimitExceeded
from app.storage.models import Course, UsageCounter
from tests.conftest import PASSWORD, csrf_client

V2 = "/api/v2"
LOGIN = {"username": "prof", "password": PASSWORD}


def test_v2_writes_need_the_csrf_token_and_v1_does_not(make_client):
    with make_client() as app_client:
        app_client.app.state.services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        browser = TestClient(app_client.app)  # a plain client: sends only what we add
        r = browser.post(f"{V2}/auth/login", json=LOGIN)
        assert r.status_code == 403 and r.json()["code"] == "csrf_failed"
        anon = browser.get(f"{V2}/auth/csrf").json()["csrf_token"]
        assert browser.cookies.get(csrf.ANON_COOKIE) == anon
        evil = TestClient(app_client.app)  # another site: can send a header, not our cookie
        assert evil.post(f"{V2}/auth/login", json=LOGIN, headers={csrf.HEADER: anon}).status_code == 403
        r = browser.post(f"{V2}/auth/login", json=LOGIN, headers={csrf.HEADER: anon})
        assert r.status_code == 200
        token = r.headers[csrf.HEADER]
        assert token != anon and browser.get(f"{V2}/auth/csrf").json()["csrf_token"] == token
        body = {"code": "ELG 5902", "title": "F", "course_type": "ece"}
        assert browser.post(f"{V2}/courses", json=body, headers={csrf.HEADER: anon}).status_code == 403
        assert browser.post(f"{V2}/courses", json=body).status_code == 403
        assert browser.post(f"{V2}/courses", json=body, headers={csrf.HEADER: token}).status_code == 201
        assert browser.get(f"{V2}/courses").status_code == 200  # reads need no token
        assert browser.post("/api/v1/auth/logout").status_code == 204  # API v1 is unchanged
        relogin = browser.post("/api/v1/auth/login", json=LOGIN)
        assert relogin.status_code == 200
        assert browser.post(f"{V2}/courses", json={**body, "code": "X"},
                            headers={csrf.HEADER: token}).status_code == 403  # new session, new token


def test_failed_logins_are_limited_per_client_address(make_client):
    with make_client({"limits": {"accounts": {"login_failures_per_hour": 3}}}) as client:
        client.app.state.services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        wrong = {"username": "prof", "password": "wrong-password"}
        assert client.post("/api/v1/auth/login", json=wrong).status_code == 401
        assert client.post(f"{V2}/auth/login", json=wrong).status_code == 401
        assert client.post(f"{V2}/auth/login", json={**wrong, "username": "nobody"}).status_code == 401
        r = client.post(f"{V2}/auth/login", json=LOGIN)  # even the right password, for the hour
        assert r.status_code == 429 and r.json()["code"] == "usage_limit"
        assert r.json()["retry_after_seconds"] > 0
        assert client.post("/api/v1/auth/login", json=LOGIN).status_code == 429


def test_successful_logins_are_not_counted(make_client):
    with make_client({"limits": {"accounts": {"login_failures_per_hour": 2}}}) as client:
        client.app.state.services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        for _ in range(4):
            assert client.post(f"{V2}/auth/login", json=LOGIN).status_code == 200


def test_logout_all_ends_every_session_and_password_change_the_others(make_client):
    with make_client() as client:
        client.app.state.services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        devices = [csrf_client(client.app) for _ in range(3)]
        for d in devices:
            assert d.post(f"{V2}/auth/login", json=LOGIN).status_code == 200
        r = devices[0].post(f"{V2}/auth/change-password",
                            json={"current_password": PASSWORD, "new_password": "another-good-password"})
        assert r.status_code == 200
        assert devices[0].get(f"{V2}/auth/me").status_code == 200
        assert [d.get(f"{V2}/auth/me").status_code for d in devices[1:]] == [401, 401]
        devices[1].cookies.clear()
        assert devices[1].post(f"{V2}/auth/login", json={**LOGIN, "password": "another-good-password"}) \
            .status_code == 200
        assert devices[0].post(f"{V2}/auth/logout-all").status_code == 204
        assert [d.get(f"{V2}/auth/me").status_code for d in devices[:2]] == [401, 401]


@pytest.fixture
def meter(use_config):
    from app.core.services import build_services

    services = build_services(use_config())
    with Session(services.engine) as db:
        other = Course(code="ELG 5902", title="F")
        db.add(other)
        db.commit()
        other_id = other.id
    limits = services.settings.limits.usage.model_copy(update={"questions_per_minute": 2,
                                                               "questions_per_day": 3,
                                                               "cloud_calls_per_day": 1})
    return services, DbUsageMeter(services.engine, limits), services.content.course_id, other_id


def test_usage_is_counted_per_student_course_and_period(meter):
    services, m, demo, other = meter
    for _ in range(2):
        m.check_usage("sid-a", demo, "question")
        m.record_usage("sid-a", demo, "question", tokens=10)
    with pytest.raises(UsageLimitExceeded) as e:
        m.check_usage("sid-a", demo, "question")  # 2 per minute
    assert e.value.kind == "question" and 1 <= e.value.retry_after_seconds <= 61
    m.check_usage("sid-b", demo, "question")  # another student
    m.check_usage("sid-a", other, "question")  # another course
    m.check_usage("sid-a", demo, "cloud_call")
    m.record_usage("sid-a", demo, "cloud_call")
    with pytest.raises(UsageLimitExceeded) as e:
        m.check_usage("sid-a", demo, "cloud_call")  # 1 per day
    assert e.value.retry_after_seconds <= 24 * 3600 + 1
    with Session(services.engine) as db:  # the day limit holds after the minute is over
        for row in db.exec(select(UsageCounter).where(UsageCounter.period == "minute")).all():
            row.period_start -= timedelta(minutes=5)
            db.add(row)
        db.commit()
    m.record_usage("sid-a", demo, "question")  # 3rd today; the old minute rows are removed
    with pytest.raises(UsageLimitExceeded):
        m.check_usage("sid-a", demo, "question")  # 3 per day
    with Session(services.engine) as db:
        rows = db.exec(select(UsageCounter).where(UsageCounter.student_id == "sid-a",
                                                  UsageCounter.course_id == demo)).all()
    day = {r.kind: r for r in rows if r.period == "day"}
    assert (day["question"].count, day["question"].tokens, day["cloud_call"].count) == (3, 20, 1)
    assert all(r.period_start.minute == 0 or r.period == "minute" for r in rows)


def test_a_course_setting_can_only_lower_the_limit(meter):
    services, _, demo, _ = meter

    class Effective:
        usage_questions_per_minute = 1
        usage_questions_per_day = 10_000  # above the cap: the cap wins
        usage_cloud_calls_per_day = None

    m = DbUsageMeter(services.engine, services.settings.limits.usage.model_copy(
        update={"questions_per_minute": 5, "questions_per_day": 2}), effective=lambda course_id: Effective)
    m.record_usage("sid-c", demo, "question")
    with pytest.raises(UsageLimitExceeded):
        m.check_usage("sid-c", demo, "question")  # the course's 1 per minute
    assert m._limit(demo, "questions_per_day", 2) == 2


def test_the_app_installs_the_database_meter(make_client):
    with make_client() as client:
        services = client.app.state.services
        assert isinstance(services.usage, DbUsageMeter)
        course = CourseRef(id=services.content.course_id, code="MED 0000", title="Demo")
        usage.record_usage("sid-d", course.id, "question")
        with Session(services.engine) as db:
            assert db.exec(select(UsageCounter).where(UsageCounter.student_id == "sid-d")).first() is not None
    usage.configure(None)  # back to NoLimits for tests without the app


def test_parallel_attempts_cannot_pass_the_limit_together():
    import threading

    from app.auth.ratelimit import AttemptWindow

    window = AttemptWindow(per_hour=5)
    start = threading.Barrier(40)
    allowed = []

    def attempt():
        start.wait()
        if window.allow("client") == 0:
            allowed.append(1)

    threads = [threading.Thread(target=attempt) for _ in range(40)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert len(allowed) == 5 and window.wait("client") > 0


def test_reservations_are_atomic_and_can_be_given_back(meter):
    from concurrent.futures import ThreadPoolExecutor

    services, m, demo, _ = meter

    def take(_):
        try:
            m.reserve_usage("sid-r", demo, "question")
            return True
        except UsageLimitExceeded:
            return False

    with ThreadPoolExecutor(max_workers=8) as pool:  # concurrent requests: only the allowed two get in
        assert sum(pool.map(take, range(8))) == 2
    m.release_usage("sid-r", demo, "question")  # no answer was produced
    m.add_tokens("sid-r", demo, "question", 7)
    assert take(0) and not take(0)
    with Session(services.engine) as db:
        day = db.exec(select(UsageCounter).where(UsageCounter.student_id == "sid-r",
                                                 UsageCounter.period == "day")).one()
    assert (day.count, day.tokens) == (2, 7)
