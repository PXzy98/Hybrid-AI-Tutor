"""Medical hybrid retriever: offline evidence, KC preference, and API integration."""
import pytest

from app.core.schemas import Chunk
from app.rag.medical_hybrid import MedicalHybridRetriever, _chunk_section, _segments
from app.rag.medical_tfidf import TOPIC_FILES


@pytest.fixture(scope="module")
def hybrid():
    return MedicalHybridRetriever()


@pytest.mark.parametrize("topic", list(TOPIC_FILES))
def test_returns_topic_only_source_chunks(hybrid, topic):
    result = hybrid.retrieve("What are symptoms and causes?", topic, k=4)
    assert 1 <= len(result) <= 4
    assert all(isinstance(p, Chunk) and p.topic == topic for p in result)
    assert all(p.source.startswith("https://medlineplus.gov/") for p in result)
    assert all(0 < p.score <= 1 for p in result)
    assert all(p.kc_ids and p.level for p in result)


def test_short_list_items_and_heading_are_not_lost():
    body = "What are the symptoms of asthma?\nWheezing\nChest tightness\nCoughing\n"
    parts = _segments(body)
    assert parts[0][0] == "What are the symptoms of asthma?"
    text = " ".join(_chunk_section(*parts[0]))
    assert "Wheezing" in text
    assert "Chest tightness" in text
    assert "What are the symptoms" in text


def test_real_short_medical_list_is_retrievable(hybrid):
    results = hybrid.retrieve("Which symptoms include wheezing in asthma?", "asthma")
    assert any("Wheezing" in p.text for p in results)
    assert any("What are the symptoms of asthma?" in p.text for p in results)


def test_preference_respects_kc_and_falls_back(hybrid):
    entries = hybrid.indices["high_blood_pressure"].passages
    p = entries[0]
    preferred = hybrid.retrieve("What is blood pressure?", "high_blood_pressure",
                                kc_ids=p.kc_ids, level=p.level)
    assert preferred
    assert preferred[0].kc_ids == p.kc_ids
    assert preferred[0].level == p.level
    fallback = hybrid.retrieve("What is blood pressure?", "high_blood_pressure",
                               kc_ids=["UNKNOWN.999"], level="advanced")
    assert fallback
    assert all(p.topic == "high_blood_pressure" for p in fallback)


def test_odd_input_and_abstention(hybrid):
    assert hybrid.retrieve("Wheezing", "not_a_topic") == []
    assert hybrid.retrieve("", "asthma") == []
    assert hybrid.retrieve("Wheezing", "asthma", k=0) == []
    assert hybrid.retrieve("zzzzxxqqvvxx", "asthma") == []


def test_retrieval_is_deterministic(hybrid):
    args = ("Which infections can cause pneumonia?", "pneumonia")
    assert hybrid.retrieve(*args) == hybrid.retrieve(*args)


def test_api_uses_hybrid_retriever(make_client):
    from tests.conftest import Api

    with make_client({"rag": {"impl": "medical_hybrid"}}) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        response = client.post("/api/v1/ask", json={
            "topic": "asthma", "question": "What are common symptoms of asthma?",
        })
        assert response.status_code == 200, response.text
        payload = response.json()
        assert payload["model_used"] == "fake-local"
        assert payload["sources"]
        assert payload["sources"][0]["source"].startswith("https://medlineplus.gov/asthma")
        assert payload["timings_ms"]["retrieve"] >= 0


def test_only_explicitly_approved_tag_overrides_are_applied(hybrid, tmp_path, monkeypatch):
    import csv

    from app.rag import medical_hybrid

    topic = "high_blood_pressure"
    original = hybrid.indices[topic].passages[0]
    key = medical_hybrid._chunk_id(topic, original.source, original.text)
    path = tmp_path / "reviewed_tags.csv"
    row = {
        "chunk_id": key, "topic": topic, "source_url": original.source,
        "review_status": "approved", "reviewed_kc_ids": "HBP.6",
        "reviewed_level": "advanced", "reviewer": "test-reviewer",
    }
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)
    monkeypatch.setattr(medical_hybrid, "REVIEWED_TAGS_PATH", path)
    revised = MedicalHybridRetriever()
    tagged = next(p for p in revised.indices[topic].passages if p.text == original.text)
    assert tagged.kc_ids == ["HBP.6"]
    assert tagged.level == "advanced"
    assert original.kc_ids != tagged.kc_ids or original.level != tagged.level
    row["review_status"] = "pending"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=row)
        writer.writeheader()
        writer.writerow(row)
    pending = MedicalHybridRetriever()
    unreviewed = next(p for p in pending.indices[topic].passages if p.text == original.text)
    assert unreviewed.kc_ids == original.kc_ids and unreviewed.level == original.level


def test_invalid_approved_override_fails_closed(hybrid, tmp_path, monkeypatch):
    import csv

    from app.rag import medical_hybrid

    topic = "high_blood_pressure"
    passage = hybrid.indices[topic].passages[0]
    record = {
        "chunk_id": medical_hybrid._chunk_id(topic, passage.source, passage.text),
        "topic": topic, "review_status": "approved", "reviewed_kc_ids": "BAD.KC",
        "reviewed_level": "advanced", "reviewer": "test-reviewer",
    }
    path = tmp_path / "reviewed_tags.csv"
    with path.open("w", encoding="utf-8", newline="") as stream:
        writer = csv.DictWriter(stream, fieldnames=record)
        writer.writeheader()
        writer.writerow(record)
    monkeypatch.setattr(medical_hybrid, "REVIEWED_TAGS_PATH", path)
    with pytest.raises(ValueError, match="invalid approved RAG tag override"):
        MedicalHybridRetriever()
