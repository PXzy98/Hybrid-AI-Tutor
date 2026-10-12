import sqlite3

from app.core.config import get_settings
from app.export_openapi import main as export_openapi

PII_QUESTION = "My name is Alice Tremblay, student 300418277. Why is salt bad for blood pressure?"


def ask(client, **kw):
    body = {"student_id": "stu-1", "topic": "high_blood_pressure", "question": PII_QUESTION} | kw
    return client.post("/api/v1/ask", json=body)


def db_dump() -> str:
    path = get_settings().database_url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        return "\n".join(con.iterdump())


def test_ask_runs_every_step(make_client):
    with make_client() as client:
        r = ask(client)
    assert r.status_code == 200, r.text
    body = r.json()
    assert body["session_id"]
    assert body["route_target"] == "local"
    assert body["model_used"] == "placeholder"
    assert set(body["timings_ms"]) == set(get_settings().pipeline)
    assert "Alice" not in body["answer"]  # placeholder privacy filter withholds the question


def test_raw_question_never_reaches_the_database(make_client):
    with make_client() as client:
        assert ask(client).status_code == 200
    dump = db_dump()
    assert "request_log" in dump and "session_turn" in dump
    for secret in ("Alice", "Tremblay", "300418277", "salt"):
        assert secret not in dump


def test_session_round_trip(make_client):
    with make_client() as client:
        sid = ask(client).json()["session_id"]
        assert ask(client, session_id=sid).json()["session_id"] == sid
        turns = client.get(f"/api/v1/sessions/{sid}").json()["turns"]
        assert [t["role"] for t in turns] == ["student", "tutor", "student", "tutor"]
        assert client.get(f"/api/v1/sessions/{sid}", params={"last": 1}).json()["turns"][0]["role"] == "tutor"
        assert client.get("/api/v1/sessions/unknown").json()["turns"] == []


def test_unknown_topic_and_bad_body_are_422(make_client):
    with make_client() as client:
        assert ask(client, topic="astrology").status_code == 422
        assert ask(client, question="").status_code == 422
        assert client.post("/api/v1/ask", json={"topic": "asthma"}).status_code == 422


def test_privacy_filter_failure_is_503_without_question(make_client, monkeypatch):
    from app.pipeline.steps.privacy_filter import PrivacyFilterStep

    async def boom(self, ctx):
        raise RuntimeError(ctx.request.question)

    monkeypatch.setattr(PrivacyFilterStep, "run", boom)
    with make_client() as client:
        r = ask(client)
    assert r.status_code == 503
    assert r.json()["step"] == "privacy_filter"
    assert "Alice" not in r.text and "300418277" not in r.text


def test_cloud_route_with_fixture_rag(make_client, monkeypatch):
    # the placeholder privacy filter is fail-closed (cloud_safe=False), so even a high score stays local
    with make_client({"routing": {"stub_score": 1.0}, "rag": {"impl": "fixture"}}) as client:
        body = ask(client).json()
    assert body["route_target"] == "local" and body["route_score"] == 1.0
    assert body["sources"]  # fixture chunks for the topic


def test_topics_and_health(make_client):
    with make_client() as client:
        topics = client.get("/api/v1/topics").json()
        health = client.get("/api/v1/health").json()
    assert [t["id"] for t in topics][:2] == ["high_blood_pressure", "type2_diabetes"]
    assert topics[0]["name"] == "High Blood Pressure"
    assert health["db"] is True and health["status"] == "ok"
    assert health["ollama"]["reachable"] is False  # closed port in tests; reported, not fatal


def test_cors_allows_vite_dev_server(make_client):
    with make_client() as client:
        r = client.options("/api/v1/ask", headers={"Origin": "http://localhost:5173",
                                                   "Access-Control-Request-Method": "POST"})
    assert r.headers.get("access-control-allow-origin") == "http://localhost:5173"


def test_export_openapi(tmp_path):
    out = export_openapi(tmp_path / "openapi.json")
    text = out.read_text(encoding="utf-8")
    assert '"/api/v1/ask"' in text and '"AskResponse"' in text
