"""Real bundled retrieval through the semantic pipeline; deterministic scoring, no model downloads."""

import numpy as np

from app.core.schemas import SemanticAnalysis
from app.llm.cloud_guard import CloudClient
from app.llm.fake import FakeLLMClient
from app.rag.medical_hybrid import MedicalHybridRetriever
from app.routing.semantic import SemanticRouter
from tests.conftest import Api

PIPELINE = [
    "privacy_filter", "understand", "learner_context", "analyze_route", "retrieve", "route",
    "generate", "restore", "verify", "attach_check", "record",
]


def configure_classifier(monkeypatch, *, cloud_probability=0.1):
    monkeypatch.setattr(SemanticRouter, "embed", lambda self, text: np.zeros(3))
    monkeypatch.setattr(
        SemanticRouter, "classify",
        lambda self, vector, method: SemanticAnalysis(
            method=method, reliable=True, cloud_probability=cloud_probability,
            requires_evidence=True, nearest_similarity=0.9,
        ),
    )


def config():
    return {"routing": {"impl": "semantic"}, "rag": {"impl": "medical_hybrid"}, "pipeline": PIPELINE}


def test_actual_hybrid_chunks_reach_local_prompt_and_sources(make_client, monkeypatch):
    configure_classifier(monkeypatch)
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores", lambda name, pairs, cfg: np.full(len(pairs), 0.99)
    )
    with make_client(config()) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        assert isinstance(api.services.retriever, MedicalHybridRetriever)
        reply = client.post("/api/v1/ask", json={
            "topic": "high_blood_pressure", "question": "What is systolic blood pressure?",
            "routing_method": "svm",
        })
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["route_target"] == "local"
        assert body["routing_details"]["evidence"]["status"] == "sufficient"
        assert body["sources"]
        assert all(s["source"].startswith("https://medlineplus.gov/") for s in body["sources"])
        assert "systolic" in api.local_llm.sent_text().lower()
        events = body["routing_progress"]
        assert any(e["stage"] == "retrieval" and "Retrieved 4" in e["detail"] for e in events)


def test_no_matching_real_evidence_routes_to_cloud(make_client, monkeypatch):
    configure_classifier(monkeypatch)
    with make_client(config()) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        transport = FakeLLMClient("Cloud answer.", model="fake-cloud", backend="cloud")
        api.services.cloud_llm = CloudClient(transport)
        reply = client.post("/api/v1/ask", json={"topic": "asthma", "question": "zzzzxxqqvvxx"})
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["route_target"] == "cloud" and body["sources"] == []
        assert body["routing_details"]["evidence"]["status"] == "empty"
        assert not api.local_llm.calls and transport.calls


def test_complex_query_skips_retrieval_on_connected_rag(make_client, monkeypatch):
    configure_classifier(monkeypatch, cloud_probability=0.99)
    with make_client(config()) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        transport = FakeLLMClient("Cloud answer.", model="fake-cloud", backend="cloud")
        api.services.cloud_llm = CloudClient(transport)

        def unexpected(*args, **kwargs):
            raise AssertionError("RAG must be skipped after capability rejection")

        monkeypatch.setattr(api.services.retriever, "retrieve", unexpected)
        reply = client.post("/api/v1/ask", json={"topic": "asthma", "question": "A complex case."})
        assert reply.status_code == 200, reply.text
        body = reply.json()
        assert body["route_target"] == "cloud"
        assert any(e["stage"] == "retrieval" and e["status"] == "skipped" for e in body["routing_progress"])
        assert transport.calls and not api.local_llm.calls


def test_teacher_display_choice_survives_application_restart(make_client, monkeypatch):
    configure_classifier(monkeypatch)
    with make_client(config()) as client:
        api = Api(client)
        api.make_instructor()
        api.make_student()
        api.login("prof")
        values = client.get("/api/v1/admin/config").json()["values"]
        values["show_routing_progress"] = False
        assert client.put("/api/v1/admin/config", json=values).status_code == 200
    # Same database, fresh FastAPI instance and lifespan: restore is automatic.
    with make_client(config()) as client:
        api = Api(client)
        api.login("alice")
        assert client.get("/api/v1/routing/options").json()["show_progress"] is False
        assert client.put("/api/v1/admin/config", json=values).status_code == 403


def test_complete_dashboard_and_upload_coexist_with_semantic_rag(make_client, monkeypatch, tmp_path):
    configure_classifier(monkeypatch)
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores", lambda name, pairs, cfg: np.full(len(pairs), 0.99)
    )
    settings = config()
    settings["rag"]["materials_dir"] = str(tmp_path / "uploads")
    with make_client(settings) as client:
        api = Api(client)
        api.make_student()
        api.make_instructor()
        api.login("alice")
        result = client.post("/api/v1/ask", json={
            "topic": "high_blood_pressure", "question": "What is systolic blood pressure?",
        })
        assert result.status_code == 200, result.text
        assert result.json()["sources"]
        api.login("prof")
        assert client.get("/api/v1/admin/students").status_code == 200
        assert client.get("/api/v1/admin/class-summary?topic=high_blood_pressure").status_code == 200
        logs = client.get("/api/v1/admin/logs")
        assert logs.status_code == 200 and logs.json()["total"] == 1
        assert client.get("/api/v1/admin/config").status_code == 200
        assert client.get("/api/v1/admin/content").status_code == 200
        upload = client.post("/api/v1/admin/topics/high_blood_pressure/materials", files={
            "file": ("notes.txt", b"Teacher course notes.", "text/plain"),
        })
        assert upload.status_code == 201, upload.text
        assert upload.json()["ingested"] is True
        assert (tmp_path / "uploads/high_blood_pressure/notes.txt").is_file()
        api.login("alice")
        assert client.get("/api/v1/admin/content").status_code == 403
