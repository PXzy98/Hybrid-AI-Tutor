"""Opt-in PubMed evidence discovery. Not part of automatic student requests.

Only a fixed public topic/focus vocabulary reaches NCBI; there is deliberately
NO student-question argument to avoid leaking PII or medical conversations.
Articles are candidates, not verified clinical evidence.
"""
import os
import re
import xml.etree.ElementTree as ET
from dataclasses import asdict, dataclass

import httpx

_BASE = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
_TOPIC_TERMS = {
    "high_blood_pressure": "hypertension",
    "type2_diabetes": "type 2 diabetes",
    "asthma": "asthma",
    "migraine": "migraine",
    "pneumonia": "pneumonia",
}
_FOCUS_TERMS = {
    "overview": "(review[Publication Type] OR systematic review[Title])",
    "treatment": "(therapy[Title/Abstract] AND review[Publication Type])",
    "risks": "(risk factors[Title/Abstract] AND review[Publication Type])",
}


@dataclass(frozen=True)
class PubMedCandidate:
    pmid: str
    title: str
    journal: str
    year: str | None
    source_url: str
    abstract_excerpt: str
    verification_status: str = "unreviewed_candidate"

    def to_dict(self) -> dict:
        return asdict(self)


def _text(element: ET.Element | None) -> str:
    return " ".join("".join(element.itertext()).split()) if element is not None else ""


def _parse_articles(xml: bytes, allowed_pmids: set[str]) -> list[PubMedCandidate]:
    root = ET.fromstring(xml)
    result = []
    for node in root.findall(".//PubmedArticle"):
        pmid = _text(node.find("./MedlineCitation/PMID"))
        if not re.fullmatch(r"\d{1,12}", pmid) or pmid not in allowed_pmids:
            continue
        article = node.find("./MedlineCitation/Article")
        if article is None:
            continue
        title = _text(article.find("ArticleTitle"))
        if not title:
            continue
        abstract = " ".join(
            f"{n.get('Label', '')}: {_text(n)}".strip(": ")
            for n in article.findall("./Abstract/AbstractText")
        )
        year = (
            _text(article.find("./Journal/JournalIssue/PubDate/Year"))
            or _text(article.find("./ArticleDate/Year"))
            or None
        )
        result.append(PubMedCandidate(
            pmid=pmid,
            title=title,
            journal=_text(article.find("./Journal/Title")),
            year=year,
            source_url=f"https://pubmed.ncbi.nlm.nih.gov/{pmid}/",
            abstract_excerpt=abstract[:1600],
        ))
    return result


class PubMedEvidenceSearch:
    """Two bounded E-utilities calls; only controlled public topic terms."""

    def __init__(self, client: httpx.Client | None = None):
        self.client = client  # caller owns injected client when provided

    def search_topic(
        self, topic: str, *, focus: str = "overview", limit: int = 3,
        network_enabled: bool = False,
    ) -> list[PubMedCandidate]:
        if not network_enabled:
            return []
        if topic not in _TOPIC_TERMS or focus not in _FOCUS_TERMS:
            return []
        limit = min(5, max(1, limit))
        search_term = f'({_TOPIC_TERMS[topic]}[Title]) AND {_FOCUS_TERMS[focus]}'
        params = {
            "db": "pubmed", "term": search_term, "retmax": limit,
            "retmode": "json", "sort": "relevance", "tool": "ELG5902HybridTutor",
        }
        email = os.environ.get("NCBI_CONTACT_EMAIL", "").strip()
        if email:
            params["email"] = email
        owned_client = self.client is None
        client = self.client or httpx.Client(timeout=8, follow_redirects=False)
        try:
            response = client.get(_BASE + "esearch.fcgi", params=params)
            response.raise_for_status()
            if len(response.content) > 200_000:
                raise ValueError("oversized PubMed ESearch response")
            payload = response.json()["esearchresult"]
            pmids = [str(p) for p in payload.get("idlist", [])]
            pmids = [p for p in pmids if re.fullmatch(r"\d{1,12}", p)][:limit]
            if not pmids:
                return []
            fetch_params = {
                "db": "pubmed", "id": ",".join(pmids), "retmode": "xml",
                "tool": "ELG5902HybridTutor",
            }
            if email:
                fetch_params["email"] = email
            fetched = client.get(_BASE + "efetch.fcgi", params=fetch_params)
            fetched.raise_for_status()
            if len(fetched.content) > 2_000_000:
                raise ValueError("oversized PubMed EFetch response")
            by_id = {
                record.pmid: record
                for record in _parse_articles(fetched.content, set(pmids))
            }
            return [
                by_id[p] for p in pmids
                if p in by_id and _TOPIC_TERMS[topic].casefold() in by_id[p].title.casefold()
            ]
        finally:
            if owned_client:
                client.close()
