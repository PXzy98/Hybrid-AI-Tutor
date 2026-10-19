"""MVP RAG audit: labelled retrieval, uploaded provenance and verification guards."""

import importlib.util
import json
from pathlib import Path

import pytest

from app.core.schemas import AskRequest, Chunk, RequestContext
from app.rag.evidence import evidence_from_chunks
from app.rag.medical_hybrid import MedicalHybridRetriever
from app.verify.checkers.grounding import GroundingChecker

ROOT = Path(__file__).resolve().parents[2]
BENCH_FILE = ROOT / "eval" / "mvp_rag_validation.py"
DATA_FILE = ROOT / "eval" / "fixtures" / "mvp_course_retrieval.json"


@pytest.fixture(scope="module")
def benchmark():
    spec = importlib.util.spec_from_file_location("mvp_rag_validation", BENCH_FILE)
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_labelling_and_metrics_math(benchmark):
    good = Chunk(
        topic="asthma",
        text="The listed source states marker alpha.",
        source="course/asthma/alpha.txt",
        score=0.8,
    )
    distractor = Chunk(topic="asthma", text="Other text", source="course/asthma/beta.txt", score=0.7)

    class FakeRetriever:
        def retrieve(self, query, topic, k=4):
            return [good, distractor] if query == "hit" else [distractor]

    cases = [
        {
            "id": "A",
            "topic": "asthma",
            "query": "hit",
            "relevant_source": good.source,
            "relevant_anchor": "marker alpha",
        },
        {
            "id": "B",
            "topic": "asthma",
            "query": "miss",
            "relevant_source": good.source,
            "relevant_anchor": "marker alpha",
        },
    ]
    score = benchmark.evaluate_cases(FakeRetriever(), cases, k=4)
    assert score["recall_at_1"] == 0.5
    assert score["recall_at_k"] == 0.5
    assert score["mrr_at_k"] == 0.5
    assert score["precision_at_1"] == 0.5
    assert score["precision_at_k"] == 0.125
    assert score["source_traceability"] == 1
    assert score["rows"][1]["first_relevant_rank"] is None
    with pytest.raises(ValueError):
        benchmark.evaluate_cases(FakeRetriever(), [], k=4)
    with pytest.raises(ValueError):
        benchmark.evaluate_cases(FakeRetriever(), cases, k=0)


def test_upload_fixture_runs_offline_and_does_not_touch_real_materials(benchmark, tmp_path):
    data = json.loads(DATA_FILE.read_text(encoding="utf-8"))
    assert len(data["cases"]) == 10
    assert len({x["topic"] for x in data["cases"]}) == 5
    assert len({x["relevant_source"] for x in data["cases"]}) == 10
    result = benchmark.run_fixture(data)
    assert result["fixture_documents"] == 10
    assert result["indexed_uploaded_passages"] >= 10
    assert result["metrics"]["cases"] == 10
    assert result["metrics"]["source_traceability"] == 1
    assert all(row["first_relevant_rank"] for row in result["metrics"]["rows"])
    assert len(result["unrelated_queries"]) == 2
    assert not (tmp_path / "asthma").exists()  # no course uploads leaked into test workdir


def test_uploaded_sources_have_meaningful_but_unapproved_provenance():
    chunk = Chunk(
        topic="asthma",
        text="Lecture says example values: 120 mmHg.",
        source="course/asthma/airway_workshop.docx",
        score=0.8,
    )
    first, second = (evidence_from_chunks([chunk])[0] for _ in range(2))
    assert first.evidence_id == second.evidence_id
    assert first.source_title == "airway workshop"
    assert first.source_url == chunk.source
    assert "review status unverified" in first.source_publisher
    assert first.source_last_modified is None
    assert first.corpus_fetched_at is None


def _context(text, passages):
    ctx = RequestContext(
        request_id="mvp-grounding",
        request=AskRequest(
            student_id="test-student", topic="high_blood_pressure", question="What does the chart show?"
        ),
        answer=text,
    )
    ctx.passages = [
        Chunk(topic="high_blood_pressure", text=p, source="course/high_blood_pressure/chart.txt", score=0.9)
        for p in passages
    ]
    return ctx


def test_no_evidence_never_counts_as_grounded():
    status = GroundingChecker(None).check(_context("This explanation is unverified.", []))
    assert (status.status, status.detail) == ("warn", "no material")


def test_numeric_claim_mismatch_warns_even_with_high_lexical_overlap():
    source = "The teaching chart records 120 mmHg for the sample measurement."
    misleading = "The teaching chart records 180 mmHg for the sample measurement."
    status = GroundingChecker(None).check(_context(misleading, [source]))
    assert status.status == "warn"
    assert "numeric claims absent" in status.detail


def test_matching_numeric_tokens_only_pass_a_lexical_check():
    source = "The teaching chart records 120 mmHg for the sample measurement."
    status = GroundingChecker(None).check(_context(source, [source]))
    assert status.status == "pass"
    assert "100% of 1 sentences supported" in status.detail


def test_valid_upload_is_searchable_but_stays_within_its_topic(tmp_path):
    doc = tmp_path / "asthma" / "class_notes.txt"
    doc.parent.mkdir(parents=True)
    doc.write_text(
        "In the BirchNexus practice exercise, students compare two fictional respiratory diary entries.",
        encoding="utf-8",
    )
    rag = MedicalHybridRetriever(tmp_path)
    hits = rag.retrieve("BirchNexus respiratory diary exercise", "asthma", k=4)
    assert any(p.source == "course/asthma/class_notes.txt" for p in hits)
    assert not any(
        "BirchNexus" in p.text for p in rag.retrieve("BirchNexus respiratory diary exercise", "migraine", k=4)
    )
    doc.unlink()
    rag.retrieve("BirchNexus", "asthma")
    assert not any(p.source == "course/asthma/class_notes.txt" for p in rag.indices["asthma"].passages)


def test_live_pipeline_warns_when_generation_has_no_retrieved_evidence(make_client):
    """Exercise real FastAPI pipeline/retriever + fake local generation, without a provider API."""
    from app.llm.fake import FakeLLMClient
    from tests.conftest import Api

    with make_client(
        {"rag": {"impl": "medical_hybrid"}, "routing": {"impl": "stub", "stub_score": 0.0}}
    ) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        api.services.local_llm = FakeLLMClient("This response is an unverified teaching claim.")
        response = client.post(
            "/api/v1/ask",
            json={
                "topic": "asthma",
                "question": "zxxqytrv blornxx qbbvzz",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["route_target"] == "local"
        assert data["sources"] == []
        assert next(c for c in data["checks"] if c["name"] == "grounding")["status"] == "warn"
        assert "Parts of this answer may go beyond the course material." in data["warnings"]


def test_live_pipeline_warns_when_generated_number_is_unsupported(make_client):
    """A shared vocabulary must not hide a nonexistent numeric value."""
    from app.llm.fake import FakeLLMClient
    from tests.conftest import Api

    with make_client(
        {"rag": {"impl": "medical_hybrid"}, "routing": {"impl": "stub", "stub_score": 0.0}}
    ) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        api.services.local_llm = FakeLLMClient(
            "Blood pressure is the force of blood against artery walls. The teaching chart reads 999 mmHg."
        )
        response = client.post(
            "/api/v1/ask",
            json={
                "topic": "high_blood_pressure",
                "question": "What does blood pressure mean?",
            },
        )
        assert response.status_code == 200, response.text
        data = response.json()
        assert data["sources"]
        detail = next(c for c in data["checks"] if c["name"] == "grounding")
        assert detail["status"] == "warn"
        assert "numeric claims absent" in detail["detail"]
        assert "Parts of this answer may go beyond the course material." in data["warnings"]


def test_char_score_normalization_does_not_invent_relevance():
    rag = MedicalHybridRetriever()
    for topic in rag.indices:
        assert rag.retrieve("zxxqytrv blornxx qbbvzz", topic) == []
        assert rag.retrieve("unrelated code compilation quantum entanglement", topic) == []


def test_genuine_near_spelling_match_is_not_lost():
    rag = MedicalHybridRetriever()
    hits = rag.retrieve("astma simptoms", "asthma")
    assert hits and any("symptoms of asthma" in p.text.lower() for p in hits)
