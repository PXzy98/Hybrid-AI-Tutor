"""Task Z10: access tests for every endpoint, enumerated from the OpenAPI document, so a new endpoint is
covered without editing this file:
- logged out: 401 everywhere except the public endpoints listed here;
- another course's instructor: 404 on every /api/v2/courses/{course_id}/... endpoint of a course he is
  not in (course IDs do not leak);
- a student: 403 on every admin endpoint (v1 and v2) and 404 on course endpoints of a course he is not in;
- an instructor: 403 on every v2 admin endpoint (they are for the system role admin).
"""
import re

import pytest
from fastapi.testclient import TestClient

from app.main import create_app
from tests.conftest import PASSWORD, csrf_client

PUBLIC = {
    ("post", "/api/v1/auth/login"), ("post", "/api/v1/auth/logout"), ("get", "/api/v1/health"),
    ("get", "/api/v2/auth/csrf"), ("post", "/api/v2/auth/login"), ("post", "/api/v2/auth/logout"),
    ("post", "/api/v2/auth/join"),
}


def _endpoints() -> list[tuple[str, str]]:
    paths = create_app().openapi()["paths"]
    return sorted((method, path) for path, ops in paths.items() for method in ops)


def _fill(path: str, course_id: int) -> str:
    path = path.replace("{course_id}", str(course_id))
    return re.sub(r"\{[a-z_]+\}", "1", path)


def _call(client: TestClient, method: str, path: str):
    kwargs = {"json": {}} if method in ("post", "put", "patch") else {}
    return getattr(client, method)(path, **kwargs)


@pytest.fixture(scope="module")
def endpoints():
    return _endpoints()


def test_the_public_list_names_real_endpoints(endpoints):
    assert PUBLIC <= set(endpoints)


def test_logged_out_callers_get_401_everywhere_but_the_public_endpoints(make_client, endpoints):
    with make_client() as client:
        anon = csrf_client(client.app)  # with a valid CSRF token, so the 401 comes from the access check
        for method, path in endpoints:
            if (method, path) in PUBLIC:
                continue
            r = _call(anon, method, _fill(path, 1))
            assert r.status_code == 401, (method, path, r.status_code, r.text[:200])


def _login(app, username: str) -> TestClient:
    c = csrf_client(app)
    assert c.post("/api/v2/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


def test_outsiders_cannot_reach_a_course_or_the_admin_pages(make_client, endpoints):
    with make_client() as client:
        services = client.app.state.services
        services.accounts.create_instructor("owner", PASSWORD, must_change=False)
        services.accounts.create_instructor("other", PASSWORD, must_change=False)
        alice, _ = services.accounts.create_student("alice", "Alice")
        services.accounts.set_password(alice.id, PASSWORD, must_change=False)
        owner = _login(client.app, "owner")
        course = owner.post("/api/v2/courses", json={"code": "ELG 5902", "title": "F",
                                                     "course_type": "ece"}).json()["id"]
        other, student = _login(client.app, "other"), _login(client.app, "alice")
        for method, path in endpoints:
            url = _fill(path, course)
            if path.startswith("/api/v2/courses/{course_id}"):
                for who, c in (("other instructor", other), ("student", student)):
                    r = _call(c, method, url)
                    assert r.status_code == 404, (who, method, path, r.status_code, r.text[:200])
            elif "/admin/" in path:
                v2 = path.startswith("/api/v2/")
                callers = [("student", student)] + ([("instructor", other)] if v2 else [])
                for who, c in callers:
                    r = _call(c, method, url)
                    assert r.status_code == 403, (who, method, path, r.status_code, r.text[:200])
