"""Offline checks for the integrated medical RAG baseline."""
import pytest

from app.core.schemas import Chunk
from app.rag.medical_tfidf import TOPIC_FILES, MedicalTfidfRetriever


@pytest.fixture(scope="module")
def rag():
    return MedicalTfidfRetriever()


@pytest.mark.parametrize("topic", list(TOPIC_FILES))
def test_every_demo_topic_has_retrievable_medlineplus_evidence(rag, topic):
    chunks = rag.retrieve("What causes this condition and what can help?", topic, k=3)
    assert chunks
    assert len(chunks) <= 3
    assert all(isinstance(c, Chunk) and c.topic == topic for c in chunks)
    assert all(c.source.startswith("https://medlineplus.gov/") for c in chunks)
    assert all(c.kc_ids and c.level in {"basic", "intermediate", "advanced"} for c in chunks)


def test_retrieval_is_deterministic_and_topic_isolated(rag):
    question = "What are common symptoms of asthma?"
    first = rag.retrieve(question, "asthma", k=4)
    assert first == rag.retrieve(question, "asthma", k=4)
    assert all(chunk.topic == "asthma" for chunk in first)


def test_kc_and_level_preference_with_fallback(rag):
    topic = "high_blood_pressure"
    passages = rag.passages[topic]
    p = passages[0]
    matched = rag.retrieve("What is high blood pressure?", topic, k=4,
                           kc_ids=list(p.kc_ids), level=p.level)
    assert matched
    assert matched[0].kc_ids == list(p.kc_ids)
    assert matched[0].level == p.level
    fallback = rag.retrieve("What is high blood pressure?", topic, k=4,
                            kc_ids=["UNKNOWN.99"], level="advanced")
    assert fallback
    assert len(fallback) == min(4, len(passages))


def test_odd_inputs_do_not_raise(rag):
    assert rag.retrieve("test", "unknown_topic") == []
    assert rag.retrieve("", "asthma") == []
    assert rag.retrieve("test", "asthma", k=0) == []


def test_ask_pipeline_uses_integrated_retriever(make_client):
    """Real retrieval through /ask; FakeLLM avoids external model calls."""
    from tests.conftest import Api

    with make_client({"rag": {"impl": "medical_tfidf"}}) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        response = client.post(
            "/api/v1/ask",
            json={"topic": "high_blood_pressure",
                  "question": "What do systolic and diastolic numbers mean?"},
        )
        assert response.status_code == 200, response.text
        result = response.json()
        assert result["model_used"] == "fake-local"
        assert result["sources"]
        assert all(source["source"].startswith("https://medlineplus.gov/")
                   for source in result["sources"])
        assert result["timings_ms"]["retrieve"] >= 0
