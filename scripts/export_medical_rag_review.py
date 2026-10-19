"""Export machine-proposed RAG KC tags for human review (never auto-approve)."""
import csv
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.medical_hybrid import MedicalHybridRetriever, _chunk_id  # noqa: E402

OUT = ROOT / "docs" / "review" / "medical_rag_kc_review.csv"


def main():
    retriever = MedicalHybridRetriever()
    rows = []
    for topic, index in retriever.indices.items():
        for passage in index.passages:
            fingerprint = _chunk_id(topic, passage.source, passage.text)
            rows.append({
                "chunk_id": fingerprint,
                "topic": topic,
                "source_url": passage.source,
                "suggested_kc_ids": ";".join(passage.kc_ids),
                "suggested_level": passage.level or "",
                "excerpt": passage.text[:240].replace("\n", " "),
                "review_status": "pending",
                "reviewed_kc_ids": "",
                "reviewed_level": "",
                "reviewer": "",
                "review_notes": "",
            })
    OUT.parent.mkdir(parents=True, exist_ok=True)
    with OUT.open("w", encoding="utf-8-sig", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=rows[0])
        writer.writeheader()
        writer.writerows(rows)
    print(f"Exported {len(rows)} unreviewed RAG chunks to {OUT}")


if __name__ == "__main__":
    main()
