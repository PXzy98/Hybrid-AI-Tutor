"""Labelled two-course RAG evaluation, without student data or generated gold labels.

Instructor-labelled anchors must exist uniquely in the approved, already-built
versioned index. Output contains aggregate metrics only, never evaluation queries.
"""
import csv
import json
from collections import defaultdict
from dataclasses import dataclass
from math import ceil
from pathlib import Path
from time import perf_counter

from app.core.schemas import Chunk
from app.rag.course_retriever import CourseRetriever


class EvaluationError(ValueError):
    """Incompatible, missing or unverified gold labels or index."""


@dataclass(frozen=True)
class GoldLabel:
    case_id: str
    course_id: int
    module_id: int | None
    question: str
    source: str
    anchor: str
    negative: bool


def load_labels(path: Path) -> list[GoldLabel]:
    """Read instructor-authored labels, including repeated IDs for multiple gold chunks."""
    rows: list[GoldLabel] = []
    with Path(path).open(encoding="utf-8-sig", newline="") as stream:
        reader = csv.DictReader(stream)
        required = {"id", "course_id", "module_id", "question", "gold_source",
                    "gold_anchor", "negative"}
        if not reader.fieldnames or set(reader.fieldnames) != required:
            raise EvaluationError("Label CSV must have the documented seven columns.")
        for row in reader:
            try:
                cid = int(row["course_id"])
                module = int(row["module_id"]) if row["module_id"].strip() else None
                negative = row["negative"].strip().lower()
                if negative not in {"true", "false"}:
                    raise ValueError("negative must be true or false")
                label = GoldLabel(
                    case_id=row["id"].strip(), course_id=cid, module_id=module,
                    question=row["question"].strip(), source=row["gold_source"].strip(),
                    anchor=row["gold_anchor"].strip(), negative=negative == "true",
                )
            except (ValueError, AttributeError, TypeError, KeyError) as exc:
                raise EvaluationError("Invalid course retrieval gold label.") from exc
            if (not label.case_id or cid <= 0 or (module is not None and module <= 0)
                    or not label.question or len(label.question) > 4000):
                raise EvaluationError("Incomplete or invalid gold label.")
            if label.negative and (label.source or label.anchor):
                raise EvaluationError("Negative labels must have no gold evidence.")
            if not label.negative and (not label.source or not label.anchor):
                raise EvaluationError("Positive labels need a source and an exact anchor.")
            rows.append(label)
    if not rows:
        raise EvaluationError("No labelled evaluation cases provided.")
    return rows


def _indexed_passages(root: Path, course_id: int) -> list[Chunk]:
    base = Path(root) / "courses" / str(course_id) / "index"
    try:
        manifest = json.loads((base / "current.json").read_text(encoding="utf-8"))
        version = manifest["index_version"]
        if type(version) is not int or version < 1:
            raise ValueError("Invalid version")
        data = json.loads((base / f"v{version}" / "passages.json").read_text(encoding="utf-8"))
        passages = [Chunk.model_validate(row) for row in data]
        if not passages or any(chunk.metadata.get("course_id") != course_id for chunk in passages):
            raise ValueError("Invalid course scope")
    except (OSError, ValueError, KeyError, TypeError) as exc:
        raise EvaluationError("Course index is unavailable or invalid.") from exc
    return passages


def evaluate_two_course_rag(
    *, retriever: CourseRetriever, index_root: Path, labels: list[GoldLabel], k: int = 4,
) -> dict:
    """Compute Hit@1, Recall@K, MRR@K, abstention and latency over two or more courses."""
    if type(k) is not int or not 1 <= k <= 20:
        raise EvaluationError("Invalid retrieval cutoff.")
    if len({label.course_id for label in labels}) < 2:
        raise EvaluationError("At least two distinct courses must be labelled.")
    grouped: dict[tuple[int, str], list[GoldLabel]] = defaultdict(list)
    for label in labels:
        grouped[(label.course_id, label.case_id)].append(label)
    index_cache = {cid: _indexed_passages(index_root, cid)
                   for cid in {label.course_id for label in labels}}

    hit1 = 0
    total_recall = 0.0
    recall1 = 0.0
    precision1 = 0.0
    precisionk = 0.0
    traceable = 0
    retrieved_total = 0
    mrr = 0.0
    negatives = 0
    abstained = 0
    times = []
    for (course_id, _), group in grouped.items():
        first = group[0]
        if any((r.question, r.module_id, r.negative) !=
               (first.question, first.module_id, first.negative) for r in group):
            raise EvaluationError("Repeated case ID has inconsistent question or scope.")
        if first.negative and len(group) != 1:
            raise EvaluationError("Negative cases must not have duplicate labels.")
        gold = {(r.source, r.anchor) for r in group if not r.negative}
        if len(gold) != len(group) and not first.negative:
            raise EvaluationError("Duplicate gold evidence labels.")
        for source, anchor in gold:
            matches = [p for p in index_cache[course_id]
                       if p.source == source and anchor in p.text
                       and (first.module_id is None or p.metadata.get("module_id")
                            in (None, first.module_id))]
            if len(matches) != 1:
                raise EvaluationError("Gold anchor must match exactly one indexed passage.")
        start = perf_counter()
        retrieved = retriever.retrieve(course_id, first.module_id, first.question, k)
        times.append(1000 * (perf_counter() - start))
        indexed = index_cache[course_id]
        for passage in retrieved:
            if passage.metadata.get("course_id") != course_id:
                raise EvaluationError("Retriever returned cross-course evidence.")
            if not any(p.source == passage.source and p.text == passage.text
                       and p.metadata.get("module_id") == passage.metadata.get("module_id")
                       for p in indexed):
                raise EvaluationError("Retriever returned a passage absent from the active index.")
        traceable += len(retrieved)
        retrieved_total += len(retrieved)
        if first.negative:
            negatives += 1
            abstained += not retrieved
            continue
        ranks = [i for i, chunk in enumerate(retrieved, 1)
                 if any(chunk.source == source and anchor in chunk.text
                        for source, anchor in gold)]
        hit1 += bool(ranks and ranks[0] == 1)
        recall1 += sum(
            any(p.source == source and anchor in p.text for p in retrieved[:1])
            for source, anchor in gold
        ) / len(gold)
        total_recall += sum(
            any(p.source == source and anchor in p.text for p in retrieved)
            for source, anchor in gold
        ) / len(gold)
        precision1 += bool(ranks and ranks[0] == 1)
        # Use k (not returned-count) as denominator as in the original MVP metric plan.
        # Repeated occurrences of the same passage do not count as distinct relevant hits.
        distinct_relevant = {(p.source, p.text) for i, p in enumerate(retrieved, 1) if i in ranks}
        precisionk += len(distinct_relevant) / k
        mrr += 1 / min(ranks) if ranks else 0

    positives = len(grouped) - negatives
    durations = sorted(times)
    return {
        "courses": len(index_cache),
        "cases": len(grouped),
        "positive_cases": positives,
        "negative_cases": negatives,
        "k": k,
        "hit_at_1": round(hit1 / positives, 4) if positives else None,
        "recall_at_1": round(recall1 / positives, 4) if positives else None,
        "recall_at_k": round(total_recall / positives, 4) if positives else None,
        "precision_at_1": round(precision1 / positives, 4) if positives else None,
        "precision_at_k": round(precisionk / positives, 4) if positives else None,
        "mrr_at_k": round(mrr / positives, 4) if positives else None,
        "source_traceability": round(traceable / retrieved_total, 4) if retrieved_total else None,
        "negative_abstention": round(abstained / negatives, 4) if negatives else None,
        "mean_latency_ms": round(sum(times) / len(times), 3),
        "p95_latency_ms": round(durations[ceil(0.95 * len(durations)) - 1], 3),
    }
