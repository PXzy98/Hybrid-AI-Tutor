"""Task Z6: /api/v2 model connection endpoints: who may use them, and no API key in any response."""
import pytest
from cryptography.fernet import Fernet

from app.auth.deps import CurrentUser, require_any
from app.core.schemas import CourseRef
from app.llm import endpoints
from app.platform.access import CourseAccess, FakeCourseDirectory

BODY = {"name": "Course GPT", "kind": "openai_compat", "base_url": "https://93.184.216.34/v1",
        "model": "gpt-x", "trust": "external", "api_key": "sk-secret-value-1234"}


def _user(role: str, account_id: int = 1) -> CurrentUser:
    return CurrentUser(account_id, f"user{account_id}", "User", role, None, False, "token")


@pytest.fixture
def client(make_client, monkeypatch):
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())

    async def passes(row, key):
        return None

    monkeypatch.setattr(endpoints, "default_tester", passes)
    monkeypatch.setattr(endpoints.create_endpoint, "__kwdefaults__",
                        {**endpoints.create_endpoint.__kwdefaults__, "tester": passes})
    monkeypatch.setattr(endpoints.update_endpoint, "__kwdefaults__",
                        {**endpoints.update_endpoint.__kwdefaults__, "tester": passes})
    monkeypatch.setattr(endpoints.test_endpoint, "__kwdefaults__",
                        {**endpoints.test_endpoint.__kwdefaults__, "tester": passes})
    with make_client() as c:
        yield c


def _as(client, user: CurrentUser):
    client.app.dependency_overrides[require_any] = lambda: user
    return client


def test_system_connections_are_admin_only_and_never_return_the_key(client):
    assert _as(client, _user("instructor")).get("/api/v2/admin/model-endpoints").status_code == 403
    admin = _as(client, _user("admin"))
    r = admin.post("/api/v2/admin/model-endpoints", json=BODY)
    assert r.status_code == 201, r.text
    created = r.json()
    assert created["api_key_last4"] == "1234" and "sk-secret" not in r.text
    listed = admin.get("/api/v2/admin/model-endpoints")
    assert [e["id"] for e in listed.json()] == [created["id"]] and "sk-secret" not in listed.text
    r = admin.patch(f"/api/v2/admin/model-endpoints/{created['id']}", json={"model": "gpt-y"})
    assert r.json()["model"] == "gpt-y"
    bad = admin.post("/api/v2/admin/model-endpoints", json={**BODY, "base_url": "http://169.254.169.254/"})
    assert bad.status_code == 422
    assert admin.delete(f"/api/v2/admin/model-endpoints/{created['id']}").status_code == 204
    assert admin.get("/api/v2/admin/model-endpoints").json() == []


def test_course_connections_belong_to_the_course_instructors(client):
    course = CourseRef(id=client.app.state.services.content.course_id, code="MED 0000", title="Demo",
                       course_type="medical_science")
    directory = FakeCourseDirectory()
    directory.add(CourseAccess(course=course, account_id=2, role="instructor", student_id=None))
    directory.add(CourseAccess(course=course, account_id=3, role="student", student_id="sid-3"))
    client.app.state.course_directory = directory
    url = f"/api/v2/courses/{course.id}/model-endpoints"
    instructor = _as(client, _user("instructor", 2))
    r = instructor.post(url, json=BODY)
    assert r.status_code == 201 and r.json()["course_id"] == course.id and "sk-secret" not in r.text
    trusted = instructor.post(url, json={**BODY, "trust": "trusted_local", "kind": "ollama",
                                         "base_url": "http://10.0.0.5:11434", "api_key": None})
    assert trusted.status_code == 422 and "control" in trusted.text  # needs confirm_controlled
    assert _as(client, _user("student", 3)).get(url).status_code == 404
    assert _as(client, _user("instructor", 9)).get(url).status_code == 404  # not a member
    other = _as(client, _user("admin")).get("/api/v2/admin/model-endpoints").json()
    assert other == []  # course connections are not system connections


def test_a_stored_connection_can_be_tested_again(client, monkeypatch):
    admin = _as(client, _user("admin"))
    created = admin.post("/api/v2/admin/model-endpoints", json=BODY).json()
    r = admin.post(f"/api/v2/admin/model-endpoints/{created['id']}/test")
    assert r.status_code == 200 and r.json()["last_test_ok_at"] >= created["last_test_ok_at"]
    assert "sk-secret" not in r.text
    assert admin.post("/api/v2/admin/model-endpoints/999999/test").status_code == 404

    async def fails(row, key):
        raise endpoints.EndpointError("the connection test failed (LLMUnavailable)")

    monkeypatch.setattr(endpoints.test_endpoint, "__kwdefaults__",
                        {**endpoints.test_endpoint.__kwdefaults__, "tester": fails})
    r = admin.post(f"/api/v2/admin/model-endpoints/{created['id']}/test")
    assert r.status_code == 422 and "LLMUnavailable" in r.text
    assert _as(client, _user("instructor")).post(
        f"/api/v2/admin/model-endpoints/{created['id']}/test").status_code == 403


def test_testing_a_connection_whose_address_is_now_refused_gives_422(client, monkeypatch):
    admin = _as(client, _user("admin"))
    created = admin.post("/api/v2/admin/model-endpoints", json=BODY).json()

    async def unsafe(row, key):
        raise ValueError("the address resolves to a private network")  # what PinnedTransport raises

    monkeypatch.setattr(endpoints.test_endpoint, "__kwdefaults__",
                        {**endpoints.test_endpoint.__kwdefaults__, "tester": unsafe})
    r = admin.post(f"/api/v2/admin/model-endpoints/{created['id']}/test")
    assert r.status_code == 422 and "private network" in r.text
