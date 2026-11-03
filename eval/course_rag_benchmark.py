"""Offline course-material retrieval evaluation against manually labelled passages.

Run only after an instructor has supplied permitted course files and gold labels.
No student records, external API requests, or production database changes.
"""
import argparse
import csv
import json
import math
import statistics
import sys
from pathlib import Path
from time import perf_counter

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))

REQUIRED = {"id", "topic", "query", "gold_source", "gold_anchor"}


def load_labels(path: Path) -> list[dict]:
    """Repeated case IDs can label several distinct relevant passages."""
    cases: dict[str, dict] = {}
    with path.open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        if not REQUIRED <= set(reader.fieldnames or []):
            raise ValueError(f"CSV columns required: {', '.join(sorted(REQUIRED))}")
        for row in reader:
            case_id, topic, query = (row[key].strip() for key in ("id", "topic", "query"))
            source, anchor = (row[key].strip() for key in ("gold_source", "gold_anchor"))
            if not all((case_id, topic, query)):
                raise ValueError("Each row needs a case ID, topic and query.")
            if bool(source) != bool(anchor):
                raise ValueError(f"{case_id}: source and anchor must both be filled or both blank.")
            if case_id not in cases:
                cases[case_id] = {"id": case_id, "topic": topic, "query": query, "gold": []}
            case = cases[case_id]
            if (case["topic"], case["query"]) != (topic, query):
                raise ValueError(f"{case_id}: conflicting topic/query across gold rows.")
            if source:
                gold = (source, anchor)
                if gold in case["gold"]:
                    raise ValueError(f"{case_id}: duplicate gold passage.")
                case["gold"].append(gold)
            elif case["gold"]:
                raise ValueError(f"{case_id}: negative case cannot also contain a gold passage.")
    if not cases:
        raise ValueError("No labelled questions; obtain labels before running evaluation.")
    return list(cases.values())


def evaluate(materials_root: Path, labels_path: Path, k: int = 4) -> dict:
    from app.rag.medical_hybrid import MedicalHybridRetriever

    if k < 1:
        raise ValueError("k must be at least one.")
    cases = load_labels(labels_path)
    rag = MedicalHybridRetriever(materials_root)
    rows: list[dict] = []
    for case in cases:
        topic = case["topic"]
        if topic not in rag.indices:
            raise ValueError(f"Unknown topic in {case['id']}: {topic}")
        matches = set()
        if case["gold"]:
            for source, anchor in case["gold"]:
                found = [
                    (chunk.source, chunk.text)
                    for chunk in rag.indices[topic].passages
                    if chunk.source == source and anchor.casefold() in chunk.text.casefold()
                ]
                if len(found) != 1:
                    raise ValueError(
                        f"{case['id']}: gold anchor {anchor!r} in {source!r} matches "
                        f"{len(found)} indexed chunks (expected exactly one)."
                    )
                matches.add(found[0])
        start = perf_counter()
        retrieved = rag.retrieve(case["query"], topic, k=k)
        elapsed = (perf_counter() - start) * 1000
        hit_positions = [i + 1 for i, p in enumerate(retrieved)
                         if (p.source, p.text) in matches]
        positives = len(matches)
        rows.append({
            "id": case["id"], "topic": topic, "query": case["query"],
            "gold_passages": positives, "retrieved": len(retrieved),
            "first_relevant_rank": min(hit_positions) if hit_positions else None,
            "hit_at_1": int(1 in hit_positions) if positives else None,
            "hit_at_k": int(bool(hit_positions)) if positives else None,
            "recall_at_1": (int(1 in hit_positions) / positives) if positives else None,
            "recall_at_k": (len(hit_positions) / positives) if positives else None,
            "precision_at_1": int(1 in hit_positions) if positives else None,
            "precision_at_k": len(hit_positions) / k if positives else None,
            "mrr_at_k": 1 / min(hit_positions) if hit_positions else 0.0 if positives else None,
            "abstained": not retrieved if not positives else None,
            "source_traceable": all(bool(p.source) for p in retrieved),
            "retrieved_sources": [
                {"source": p.source, "page": p.metadata.get("page"), "score": p.score}
                for p in retrieved
            ],
            "latency_ms": round(elapsed, 3),
        })
    labelled = [row for row in rows if row["gold_passages"]]
    negatives = [row for row in rows if not row["gold_passages"]]
    latency = sorted(row["latency_ms"] for row in rows)
    metrics = {
        "total_questions": len(rows),
        "labelled_questions": len(labelled),
        "negative_questions": len(negatives),
        "hit_at_1": statistics.mean(r["hit_at_1"] for r in labelled) if labelled else None,
        "hit_at_k": statistics.mean(r["hit_at_k"] for r in labelled) if labelled else None,
        "recall_at_1": statistics.mean(r["recall_at_1"] for r in labelled) if labelled else None,
        "recall_at_k": statistics.mean(r["recall_at_k"] for r in labelled) if labelled else None,
        "precision_at_1": statistics.mean(r["precision_at_1"] for r in labelled) if labelled else None,
        "precision_at_k": statistics.mean(r["precision_at_k"] for r in labelled) if labelled else None,
        "mrr_at_k": statistics.mean(r["mrr_at_k"] for r in labelled) if labelled else None,
        "negative_abstention": statistics.mean(r["abstained"] for r in negatives) if negatives else None,
        "source_traceability": statistics.mean(r["source_traceable"] for r in rows),
        "mean_latency_ms": statistics.mean(latency),
        "p95_latency_ms": latency[math.ceil(len(latency) * 0.95) - 1],
    }
    return {
        "warning": (
            "Engineering retrieval evaluation only. Labels must be independently reviewed. "
            "Search scores and source presence do not establish clinical accuracy. "
            "With one gold chunk per question, Precision@4 cannot exceed 25%."
        ),
        "k": k,
        "metrics": metrics,
        "material_status": {topic: rag.material_status(topic) for topic in rag.indices},
        "cases": rows,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--materials-dir", type=Path, required=True, help="Local topic folders with files")
    parser.add_argument("--labels", type=Path, required=True, help="UTF-8 manually labelled CSV")
    parser.add_argument("--output", type=Path, help="Optional private JSON result file")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--marginal", type=float, help="Optional provisional Recall@1 target")
    parser.add_argument("--ideal", type=float, help="Optional provisional Recall@1 target")
    args = parser.parse_args()
    report = evaluate(args.materials_dir, args.labels, args.k)
    m = report["metrics"]
    print(f"Questions: {m['total_questions']}, labelled: {m['labelled_questions']}, "
          f"negatives: {m['negative_questions']}")
    for label in ("hit_at_1", "recall_at_1", "recall_at_k", "precision_at_1",
                  "precision_at_k", "mrr_at_k", "negative_abstention", "source_traceability"):
        value = m[label]
        print(f"{label}: {'N/A' if value is None else f'{value:.3f}'}")
    print(f"Retrieval latency mean/p95: {m['mean_latency_ms']:.2f}/{m['p95_latency_ms']:.2f} ms")
    if m["recall_at_1"] is not None:
        for name, threshold in (("marginal", args.marginal), ("ideal", args.ideal)):
            if threshold is not None:
                if not 0 <= threshold <= 1:
                    parser.error(f"{name} threshold must be in [0, 1]")
                print(f"Provisional {name} target {threshold:.0%}: "
                      f"{'MET' if m['recall_at_1'] >= threshold else 'NOT MET'}")
    print(report["warning"])
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
        print(f"Wrote {args.output}")


if __name__ == "__main__":
    main()
