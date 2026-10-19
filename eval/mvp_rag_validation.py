"""Offline, reproducible MVP retrieval diagnostics using synthetic uploaded lectures.

This is *not* a clinical or professor-approved evaluation set. Each fixture question
has one manually labelled relevant passage, defined by document + exact excerpt.
Use a fresh isolated materials directory; never write instructor upload folders.
Run from repo root: .venv/Scripts/python.exe eval/mvp_rag_validation.py
"""

import json
import statistics
import sys
import tempfile
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.medical_hybrid import MedicalHybridRetriever  # noqa: E402

FIXTURE = ROOT / "eval" / "fixtures" / "mvp_course_retrieval.json"
OUTPUT = ROOT / "eval" / "results"


def relevant(passage, case: dict) -> bool:
    """Passage-level relevance judged by both course source and excerpt."""
    return (
        passage.topic == case["topic"]
        and passage.source == case["relevant_source"]
        and case["relevant_anchor"].casefold() in passage.text.casefold()
    )


def evaluate_cases(retriever, cases: list[dict], k: int = 4) -> dict:
    if not cases or k < 1:
        raise ValueError("At least one labelled case and k >= 1 are required.")
    rows = []
    for case in cases:
        start = perf_counter()
        passages = retriever.retrieve(case["query"], case["topic"], k=k)
        latency_ms = (perf_counter() - start) * 1000
        matched = [relevant(p, case) for p in passages]
        rank = next((i + 1 for i, is_relevant in enumerate(matched) if is_relevant), None)
        rows.append(
            {
                "id": case["id"],
                "topic": case["topic"],
                "query": case["query"],
                "gold_source": case["relevant_source"],
                "first_relevant_rank": rank,
                "retrieved_sources": [p.source for p in passages],
                "retrieved_count": len(passages),
                "precision_at_1": int(rank == 1),
                # P@k uses k as the denominator, even if fewer results are returned.
                "precision_at_k": sum(matched) / k,
                "recall_at_1": int(rank == 1),
                "recall_at_k": int(rank is not None),
                "reciprocal_rank_at_k": 1 / rank if rank else 0.0,
                "source_traceable": all(bool(p.source and p.topic == case["topic"]) for p in passages),
                "latency_ms": round(latency_ms, 3),
            }
        )
    latencies = sorted(row["latency_ms"] for row in rows)
    return {
        "cases": len(rows),
        "k": k,
        "precision_at_1": round(statistics.mean(row["precision_at_1"] for row in rows), 4),
        "precision_at_k": round(statistics.mean(row["precision_at_k"] for row in rows), 4),
        "recall_at_1": round(statistics.mean(row["recall_at_1"] for row in rows), 4),
        "recall_at_k": round(statistics.mean(row["recall_at_k"] for row in rows), 4),
        "mrr_at_k": round(statistics.mean(row["reciprocal_rank_at_k"] for row in rows), 4),
        "source_traceability": round(statistics.mean(row["source_traceable"] for row in rows), 4),
        "mean_latency_ms": round(statistics.mean(latencies), 3),
        "p95_latency_ms": latencies[max(0, int(len(latencies) * 0.95) - 1)],
        "rows": rows,
    }


def run_fixture(data: dict) -> dict:
    with tempfile.TemporaryDirectory(prefix="5902_rag_mvp_") as folder:
        root = Path(folder)
        for doc in data["materials"]:
            path = root / doc["topic"] / doc["filename"]
            path.parent.mkdir(parents=True, exist_ok=True)
            path.write_text(doc["text"], encoding="utf-8")
        rag = MedicalHybridRetriever(root)
        for case in data["cases"]:
            gold_chunks = [p for p in rag.indices[case["topic"]].passages if relevant(p, case)]
            if len(gold_chunks) != 1:
                raise ValueError(
                    f"{case['id']} must label exactly one indexed passage, got {len(gold_chunks)}"
                )
        uploaded_passages = sum(
            row["passage_count"]
            for topic in rag.indices
            for row in rag.material_status(topic)
            if row["origin"] == "uploaded" and row["indexed"]
        )
        scored = evaluate_cases(rag, data["cases"])
        negatives = []
        for case in data["unrelated_queries"]:
            passages = rag.retrieve(case["query"], case["topic"], k=4)
            negatives.append(
                {
                    **case,
                    "returned": len(passages),
                    "abstained": not passages,
                }
            )
        return {
            "dataset_id": data["dataset_id"],
            "disclaimer": data["disclaimer"],
            "fixture_documents": len(data["materials"]),
            "fixture_topics": len({d["topic"] for d in data["materials"]}),
            "indexed_uploaded_passages": uploaded_passages,
            "metrics": scored,
            "unrelated_queries": negatives,
        }


def main() -> None:
    data = json.loads(FIXTURE.read_text(encoding="utf-8"))
    result = run_fixture(data)
    OUTPUT.mkdir(exist_ok=True)
    (OUTPUT / "mvp_rag_validation.json").write_text(
        json.dumps(result, indent=2, ensure_ascii=False) + "\n", encoding="utf-8"
    )
    m = result["metrics"]
    lines = [
        "# MVP RAG: independently isolated upload fixture",
        "",
        "**Synthetic educational texts only.** The 10 manually labelled examples are a",
        "small engineering diagnostic; not blind, clinician-reviewed, real-student or",
        "held-out production data. Each question has exactly one gold passage.",
        "The retriever also contains the five built-in MedlinePlus texts.",
        "",
        (
            f"- Uploaded documents: {result['fixture_documents']}; "
            f"indexed passages: {result['indexed_uploaded_passages']}"
        ),
        f"- Labelled questions: {m['cases']}; unrelated negative queries: {len(result['unrelated_queries'])}",
        f"- Recall@1: {m['recall_at_1']:.1%}; Recall@4: {m['recall_at_k']:.1%}",
        f"- Precision@1: {m['precision_at_1']:.1%}; Precision@4: {m['precision_at_k']:.1%}",
        f"- MRR@4: {m['mrr_at_k']:.3f}",
        f"- Source traceability (returned chunks): {m['source_traceability']:.1%}",
        (
            f"- Mean / p95 retrieval latency: {m['mean_latency_ms']:.2f} / "
            f"{m['p95_latency_ms']:.2f} ms (index construction excluded)"
        ),
        "",
        "Precision@4 is capped at 25% when one gold passage is annotated per query;",
        "other potentially useful chunks are conservatively counted as nonrelevant.",
        "Scores cannot be generalized to actual professor materials.",
        "",
        "| ID | Topic | Rank | Retrieved | P@4 | Milliseconds |",
        "|---|---|---:|---:|---:|---:|",
    ]
    for row in m["rows"]:
        lines.append(
            f"| {row['id']} | {row['topic']} | {row['first_relevant_rank'] or '-'}"
            f" | {row['retrieved_count']} | {row['precision_at_k']:.2f} | {row['latency_ms']:.2f} |"
        )
    lines.extend(["", "## Deliberately unrelated inputs"])
    for neg in result["unrelated_queries"]:
        lines.append(f"- {neg['topic']}: abstained={neg['abstained']}; returned={neg['returned']}")
    lines.extend(
        [
            "",
            "## Interpretation",
            "- The labelled excerpt and matching document must both be returned.",
            "- Passage scores are not probabilities of medical correctness.",
            "- Labels, permissions, source freshness and medical safety require human review.",
            "- Re-run with educator-approved course content and independent gold judgements.",
        ]
    )
    (OUTPUT / "mvp_rag_validation.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines[:16]))


if __name__ == "__main__":
    main()
