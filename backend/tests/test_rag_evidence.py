"""Evidence traceability, cautious numeric checks, and mocked PubMed tests."""

import httpx
import pytest

from app.core.schemas import Chunk
from app.rag.evidence import check_numeric_claim, evidence_from_chunks
from app.rag.pubmed import PubMedEvidenceSearch


def test_local_evidence_has_reproducible_source_metadata():
    passage = Chunk(
        topic="asthma", text="What are the symptoms of asthma? Wheezing.",
        source="https://medlineplus.gov/asthma.html", score=0.8,
        kc_ids=["AST.1"], level="basic",
    )
    first = evidence_from_chunks([passage])
    second = evidence_from_chunks([passage])
    assert first == second
    assert first[0].evidence_id
    assert first[0].source_title == "Asthma"
    assert first[0].source_last_modified
    assert first[0].corpus_fetched_at
    assert first[0].to_dict()["suggested_kc_ids"] == ("AST.1",)


def test_numeric_precheck_never_claims_verification():
    def ev(text: str):
        chunk = Chunk(topic="asthma", text=text, score=0.7,
                      source="https://medlineplus.gov/asthma.html")
        return evidence_from_chunks([chunk])

    claim = "The intervention reduces risk by 20% to 40%."
    missing = check_numeric_claim(claim, ev("A reduction by 20% was seen."))
    assert missing.status == "numeric_evidence_missing"
    assert not missing.candidate_evidence_ids
    candidate = check_numeric_claim(claim, ev("Range from 20% to 40% in one report."))
    assert candidate.status == "numbers_present_context_unverified"
    assert candidate.candidate_evidence_ids
    assert "relative" in candidate.note
    assert check_numeric_claim("Does this work?", ev("Some evidence.")).status == "not_a_numeric_claim"


def test_pubmed_off_by_default_and_rejects_unapproved_topics():
    called = []

    def handler(request):
        called.append(request)
        return httpx.Response(500)

    client = httpx.Client(transport=httpx.MockTransport(handler))
    try:
        search = PubMedEvidenceSearch(client)
        assert search.search_topic("asthma") == []
        assert search.search_topic("patient private diagnosis", network_enabled=True) == []
        assert search.search_topic("asthma", focus="unknown", network_enabled=True) == []
        assert called == []
    finally:
        client.close()


def test_pubmed_live_contract_with_mocked_ncbi():
    requests = []
    fixture_xml = b'''<PubmedArticleSet>
      <PubmedArticle><MedlineCitation><PMID>123456</PMID>
      <Article><ArticleTitle>Review of asthma treatment</ArticleTitle>
      <Journal><Title>Medical Journal</Title>
      <JournalIssue><PubDate><Year>2025</Year></PubDate></JournalIssue></Journal>
      <Abstract><AbstractText Label="OBJECTIVE">A public abstract.</AbstractText></Abstract>
      </Article></MedlineCitation></PubmedArticle>
    </PubmedArticleSet>'''

    def handler(req):
        requests.append(req)
        assert req.url.host == "eutils.ncbi.nlm.nih.gov"
        if req.url.path.endswith("esearch.fcgi"):
            params = dict(req.url.params)
            assert "patient" not in params["term"]
            assert "asthma" in params["term"]
            assert params["db"] == "pubmed"
            return httpx.Response(200, json={"esearchresult": {"idlist": ["123456"]}})
        return httpx.Response(200, content=fixture_xml)

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        publications = PubMedEvidenceSearch(client).search_topic(
            "asthma", focus="treatment", limit=2, network_enabled=True,
        )
    assert len(requests) == 2
    assert len(publications) == 1
    record = publications[0]
    assert record.pmid == "123456"
    assert record.source_url == "https://pubmed.ncbi.nlm.nih.gov/123456/"
    assert record.year == "2025"
    assert record.verification_status == "unreviewed_candidate"
    assert "OBJECTIVE" in record.abstract_excerpt


@pytest.mark.parametrize("bad_limit", [-2, 0, 200])
def test_pubmed_caps_result_count(bad_limit):
    queries = []

    def handler(req):
        queries.append(dict(req.url.params))
        return httpx.Response(200, json={"esearchresult": {"idlist": []}})

    with httpx.Client(transport=httpx.MockTransport(handler)) as client:
        assert PubMedEvidenceSearch(client).search_topic(
            "pneumonia", network_enabled=True, limit=bad_limit,
        ) == []
    assert 1 <= int(queries[0]["retmax"]) <= 5
