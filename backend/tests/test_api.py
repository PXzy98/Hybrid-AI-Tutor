import sqlite3

from app.core.config import get_settings
from app.export_openapi import main as export_openapi

PII_QUESTION = "My name is Alice Tremblay, student 300418277. Why is salt bad for blood pressure?"


def ask(client, **kw):
    body = {"topic": "high_blood_pressure", "question": PII_QUESTION} | kw
    return client.post("/api/v1/ask", json=body)


def db_dump() -> str:
    path = get_settings().database_url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        return "\n".join(con.iterdump())


def table_dump(table: str) -> str:
    path = get_settings().database_url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        return "\n".join(map(str, con.execute(f"SELECT * FROM {table}").fetchall()))  # noqa: S608


def test_ask_runs_every_step(student_client):
    r = ask(student_client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"]
    assert body["route_target"] == "local"
    assert body["model_used"] == "placeholder"
    assert set(body["timings_ms"]) == set(get_settings().pipeline)
    assert "Alice" not in body["answer"]  # placeholder privacy filter withholds the question


def test_ask_requires_login(api):
    assert ask(api.client).status_code == 401


def test_student_id_in_body_is_ignored(api):
    """Identity comes from the session; a forged student_id in the body changes nothing."""
    alice = api.make_student()
    api.login("alice")
    r = ask(api.client, student_id="someone-else")
    assert r.status_code == 200
    assert "someone-else" not in db_dump()
    assert alice.student_id in table_dump("request_log")


def test_raw_question_and_identity_never_reach_learning_tables(student_client):
    assert ask(student_client).status_code == 200
    logs = table_dump("request_log") + table_dump("session_turn")
    for secret in ("Alice", "Tremblay", "alice", "300418277", "salt"):
        assert secret not in logs
    # the question words are nowhere in the DB; the display name exists only in the account table
    assert "salt" not in db_dump() and "300418277" not in db_dump()


def test_session_round_trip(student_client):
    sid = ask(student_client).json()["session_id"]
    assert ask(student_client, session_id=sid).json()["session_id"] == sid
    turns = student_client.get(f"/api/v1/sessions/{sid}").json()["turns"]
    assert [t["role"] for t in turns] == ["student", "tutor", "student", "tutor"]
    last = student_client.get(f"/api/v1/sessions/{sid}", params={"last": 1}).json()["turns"]
    assert [t["role"] for t in last] == ["tutor"]
    assert student_client.get("/api/v1/sessions/unknown").json()["turns"] == []


def test_students_cannot_see_or_continue_each_others_sessions(api):
    api.make_student("alice")
    api.make_student("bob", "Bob Ng")
    api.login("alice")
    sid = ask(api.client).json()["session_id"]
    api.login("bob")
    assert api.client.get(f"/api/v1/sessions/{sid}").status_code == 404
    assert ask(api.client, session_id=sid).status_code == 404
    api.login("alice")
    assert len(api.client.get(f"/api/v1/sessions/{sid}").json()["turns"]) == 2


def test_unknown_topic_and_bad_body_are_422(student_client):
    assert ask(student_client, topic="astrology").status_code == 422
    assert ask(student_client, question="").status_code == 422
    assert student_client.post("/api/v1/ask", json={"topic": "asthma"}).status_code == 422


def test_privacy_filter_failure_is_503_without_question(student_client, monkeypatch):
    from app.pipeline.steps.privacy_filter import PrivacyFilterStep

    async def boom(self, ctx):
        raise RuntimeError(ctx.request.question)

    monkeypatch.setattr(PrivacyFilterStep, "run", boom)
    r = ask(student_client)
    assert r.status_code == 503
    assert r.json()["step"] == "privacy_filter"
    assert "Alice" not in r.text and "300418277" not in r.text


def test_cloud_score_with_fixture_rag(make_client):
    from tests.conftest import Api

    # the placeholder privacy filter is fail-closed (cloud_safe=False), so even a high score stays local
    with make_client({"routing": {"stub_score": 1.0}, "rag": {"impl": "fixture"}}) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        body = ask(client).json()
    assert body["route_target"] == "local" and body["route_score"] == 1.0
    assert body["sources"]  # fixture chunks for the topic


def test_topics_need_login_health_is_public(api):
    assert api.client.get("/api/v1/topics").status_code == 401
    health = api.client.get("/api/v1/health").json()
    assert health["db"] is True and health["status"] == "ok"
    assert health["ollama"]["reachable"] is False  # closed port in tests; reported, not fatal
    api.make_student()
    api.login("alice")
    topics = api.client.get("/api/v1/topics").json()
    assert [t["id"] for t in topics][:2] == ["high_blood_pressure", "type2_diabetes"]
    assert topics[0]["name"] == "High Blood Pressure"


def test_cors_allows_vite_dev_server_with_credentials(api):
    r = api.client.options("/api/v1/ask", headers={"Origin": "http://localhost:5173",
                                                   "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"
    assert r.headers.get("access-control-allow-credentials") == "true"


def test_export_openapi(tmp_path):
    out = export_openapi(tmp_path / "openapi.json")
    text = out.read_text(encoding="utf-8")
    assert '"/api/v1/ask"' in text and '"AskBody"' in text and '"/api/v1/auth/login"' in text
