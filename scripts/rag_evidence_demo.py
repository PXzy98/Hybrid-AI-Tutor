"""Reproducible RAG evidence demonstration (no LLM or student data required).

Run: python scripts/rag_evidence_demo.py [--web]
--web explicitly searches fixed public PubMed topic terms, never student text.
"""
import argparse
import json
import sys
import xml.etree.ElementTree as ET
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.evidence import check_numeric_claim, evidence_from_chunks  # noqa: E402
from app.rag.medical_hybrid import MedicalHybridRetriever  # noqa: E402
from app.rag.pubmed import PubMedEvidenceSearch  # noqa: E402


def main():
    parser = argparse.ArgumentParser(description="ELG5902 RAG evidence demonstration")
    parser.add_argument(
        "--web", action="store_true",
        help="Opt in to PubMed search with preset topic terms, never a student question",
    )
    args = parser.parse_args()
    topic = "asthma"
    question = "What are the symptoms of asthma?"
    chunks = MedicalHybridRetriever().retrieve(question, topic, k=3)
    evidence = evidence_from_chunks(chunks)
    numeric = check_numeric_claim("Asthma treatment reduces risk by 20% to 40%.", evidence)
    result = {
        "demo": "ELG5902 course-specific RAG evidence",
        "question": question,
        "retriever": "medical_hybrid",
        "retrieved": [
            {
                "evidence_id": r.evidence_id,
                "source_title": r.source_title,
                "source_url": r.source_url,
                "source_last_modified": r.source_last_modified,
                "corpus_fetched_at": r.corpus_fetched_at,
                "score": r.relevance_score,
                "kc_ids": list(r.suggested_kc_ids),
                "level": r.suggested_level,
                "text_excerpt": r.text[:230],
            }
            for r in evidence
        ],
        "hypothetical_numeric_claim_check": numeric.to_dict(),
        "pubmed": {
            "status": "not_requested",
            "note": "Not connected to automatic student/pipeline requests.",
            "public_candidates": [],
        },
    }
    if args.web:
        try:
            publications = PubMedEvidenceSearch().search_topic(
                topic, focus="overview", limit=2, network_enabled=True,
            )
            result["pubmed"] = {
                "status": "returned_candidates" if publications else "no_candidates",
                "note": "Metadata/abstract records are not evidence that a specific claim is correct.",
                "public_candidates": [p.to_dict() for p in publications],
            }
        except (httpx.HTTPError, ValueError, KeyError, ET.ParseError) as exc:
            result["pubmed"] = {
                "status": "unavailable",
                "note": f"PubMed external request failed: {type(exc).__name__}",
                "public_candidates": [],
            }
    print(json.dumps(result, indent=2, ensure_ascii=False))


if __name__ == "__main__":
    main()
