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
    assert body["model_used"] == "fake-local"
    assert body["answer"] == "Fake local answer."
    assert set(body["timings_ms"]) == set(get_settings().pipeline)


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


def test_only_sanitized_text_reaches_the_database(student_client):
    assert ask(student_client).status_code == 200
    logs = table_dump("request_log") + table_dump("session_turn")
    for secret in ("Alice", "Tremblay", "alice", "300418277"):
        assert secret not in logs
    assert "<PERSON_1>" in logs and "<STUDENT_ID_1>" in logs and "salt" in logs  # the sanitized question
    assert "300418277" not in db_dump()  # nowhere in the DB; the display name lives only in `account`


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

    with make_client({"routing": {"stub_score": 1.0}, "rag": {"impl": "fixture"},
                      "privacy": {"health_detail_policy": "local_only"}}) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        body = ask(client).json()  # name + student number only: cloud_safe, routed to the cloud
        health = ask(client, question="I have high blood pressure. Is salt bad for me?").json()
    # no cloud model configured in tests: the local model answered, and the response says so
    assert body["route_score"] == 1.0 and body["route_target"] == "local"
    assert "No cloud model is connected, so the local model answered this question." in body["warnings"]
    assert body["sources"]  # fixture chunks for the topic
    # a personal health detail is never cloud_safe: kept local without even trying the cloud
    assert health["route_target"] == "local" and health["warnings"] == []


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


def test_local_model_down_is_503_without_question(api):
    from app.llm.base import LLMUnavailable
    from app.llm.fake import FakeLLMClient

    api.services.local_llm = FakeLLMClient(LLMUnavailable("ollama unreachable"))
    api.make_student()
    api.login("alice")
    r = ask(api.client)
    assert r.status_code == 503 and r.json()["step"] == "generate"
    assert r.json()["detail"] == "The tutor could not answer right now. Please try again."
    assert "Alice" not in r.text


def test_answer_repeating_pii_is_not_stored(api):
    """The local model sees the raw question and may repeat the name; storage must not."""
    api.local_llm.replies = [lambda msgs: "Hello Alice Tremblay (300418277)! Salt makes you retain water."]
    api.make_student()
    api.login("alice")
    r = ask(api.client)
    assert "Alice Tremblay" in r.json()["answer"]  # the student sees their own answer
    logs = table_dump("request_log") + table_dump("session_turn")
    assert "Alice" not in logs and "300418277" not in logs  # replaced before storage...
    assert "Hello <PERSON_1> (<STUDENT_ID_1>)! Salt makes you retain water." in logs  # ...the rest is kept
