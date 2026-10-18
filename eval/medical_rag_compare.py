"""Reproducible snippet-anchor retrieval comparison (not medical correctness evaluation).

From repository root: .venv/Scripts/python eval/medical_rag_compare.py
"""
import json
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.rag.medical_hybrid import MedicalHybridRetriever
from app.rag.medical_tfidf import MedicalTfidfRetriever


def evaluate(retriever, cases: list[dict], k: int = 4) -> dict:
    rows = []
    for case in cases:
        start = perf_counter()
        passages = retriever.retrieve(case["query"], case["topic"], k=k)
        elapsed = (perf_counter() - start) * 1000
        hits = [
            case["anchor"].casefold() in passage.text.casefold()
            for passage in passages
        ]
        first = next((i + 1 for i, hit in enumerate(hits) if hit), None)
        rows.append({
            **case,
            "first_relevant_rank": first,
            "hit_at_1": first == 1,
            "hit_at_4": first is not None,
            "reciprocal_rank": 1 / first if first else 0,
            "latency_ms": round(elapsed, 2),
            "retrieved_scores": [p.score for p in passages],
        })
    latencies = sorted(r["latency_ms"] for r in rows)
    return {
        "queries": len(rows),
        "hit_at_1": round(statistics.mean(r["hit_at_1"] for r in rows), 4),
        "hit_at_4": round(statistics.mean(r["hit_at_4"] for r in rows), 4),
        "mrr_at_4": round(statistics.mean(r["reciprocal_rank"] for r in rows), 4),
        "mean_latency_ms": round(statistics.mean(latencies), 2),
        "p95_latency_ms": latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))],
        "cases": rows,
    }


def main():
    cases = json.loads((ROOT / "eval" / "medical_rag_cases.json").read_text(encoding="utf-8"))
    baseline = MedicalTfidfRetriever()
    hybrid = MedicalHybridRetriever()
    for case in cases:
        filename = {
            "high_blood_pressure": "hypertension.txt",
            "type2_diabetes": "type2_diabetes.txt",
            "asthma": "asthma.txt",
            "migraine": "migraine.txt",
            "pneumonia": "pneumonia.txt",
        }[case["topic"]]
        original = (ROOT / "data" / "medical_rag" / "raw" / filename).read_text(encoding="utf-8")
        if case["anchor"].casefold() not in original.casefold():
            raise ValueError(f"Expected anchor absent in corpus: {case!r}")
    results = {
        "note": "20 small hand-authored snippet-anchor tests. Measures whether a text fragment is retrieved, not clinical relevance, truth, grounded generation or generalization.",
        "baseline": evaluate(baseline, cases),
        "hybrid": evaluate(hybrid, cases),
    }
    destination = ROOT / "eval" / "results"
    destination.mkdir(exist_ok=True)
    (destination / "medical_rag_compare.json").write_text(
        json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8",
    )
    lines = [
        "# Medical RAG baseline vs hybrid — anchor retrieval",
        "",
        "Small, manually authored checks against exact source phrases (not gold chunk judgments or clinical validation).",
        "",
        "| Retriever | Hit@1 | Hit@4 | MRR@4 | Mean ms | P95 ms |",
        "|---|---:|---:|---:|---:|---:|",
    ]
    for name in ("baseline", "hybrid"):
        s = results[name]
        lines.append(
            f"| {name} | {s['hit_at_1']:.1%} | {s['hit_at_4']:.1%} | "
            f"{s['mrr_at_4']:.3f} | {s['mean_latency_ms']:.2f} | {s['p95_latency_ms']:.2f} |"
        )
    lines.extend(["", "## Hybrid misses in Top-4"])
    for r in results["hybrid"]["cases"]:
        if not r["hit_at_4"]:
            lines.append(f"- {r['topic']}: {r['query']} (anchor: {r['anchor']})")
    if all(r["hit_at_4"] for r in results["hybrid"]["cases"]):
        lines.append("- None in this small test set")
    (destination / "medical_rag_compare.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
