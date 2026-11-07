"""S11 two-course evaluation on fictional indexed materials only."""
import csv

import pytest

from app.rag.course_retriever import IndexedCourseRetriever
from app.rag.evaluation import EvaluationError, evaluate_two_course_rag, load_labels


def _setup(tmp_path):
    for cid, label in [(101, "Quartzzyme"), (202, "Heliometric")]:
        directory = tmp_path / "courses" / str(cid) / "materials" / "_course"
        directory.mkdir(parents=True)
        (directory / "syllabus.md").write_text(
            "# Fictional syllabus\n" + label + " is part of the invented coursework.",
            encoding="utf-8",
        )
    retriever = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    retriever.rebuild(101)
    retriever.rebuild(202)
    return retriever


def _csv(path, rows):
    with path.open("w", newline="", encoding="utf-8") as stream:
        writer = csv.writer(stream)
        writer.writerow(["id", "course_id", "module_id", "question", "gold_source",
                         "gold_anchor", "negative"])
        writer.writerows(rows)


def _rows():
    return [
        ["q1", "101", "", "Quartzzyme fictional coursework",
         "course/101/_course/syllabus.md", "Quartzzyme is part", "false"],
        ["q2", "202", "", "Heliometric invented coursework",
         "course/202/_course/syllabus.md", "Heliometric is part", "false"],
        ["q3", "101", "", "xyzabc zzzzqvo", "", "", "true"],
    ]


def test_two_course_metrics_and_query_text_not_emitted(tmp_path):
    retriever = _setup(tmp_path)
    csv_path = tmp_path / "labels.csv"
    _csv(csv_path, _rows())
    result = evaluate_two_course_rag(
        retriever=retriever, index_root=tmp_path, labels=load_labels(csv_path), k=4,
    )
    assert result["courses"] == 2
    assert result["positive_cases"] == 2 and result["negative_cases"] == 1
    assert result["hit_at_1"] == 1
    assert result["recall_at_k"] == 1
    assert result["mrr_at_k"] == 1
    assert "Quartzzyme" not in repr(result)
    assert result["mean_latency_ms"] >= 0


def test_invented_or_missing_gold_anchor_is_rejected(tmp_path):
    retriever = _setup(tmp_path)
    path = tmp_path / "labels.csv"
    rows = _rows()
    rows[0][5] = "not actually in the course material"
    _csv(path, rows)
    with pytest.raises(EvaluationError, match="anchor"):
        evaluate_two_course_rag(
            retriever=retriever, index_root=tmp_path, labels=load_labels(path),
        )


def test_single_course_cannot_claim_multi_course_evaluation(tmp_path):
    retriever = _setup(tmp_path)
    path = tmp_path / "labels.csv"
    _csv(path, _rows()[:1])
    with pytest.raises(EvaluationError, match="two"):
        evaluate_two_course_rag(
            retriever=retriever, index_root=tmp_path, labels=load_labels(path),
        )


def test_wrong_course_gold_source_rejected(tmp_path):
    retriever = _setup(tmp_path)
    path = tmp_path / "labels.csv"
    rows = _rows()
    rows[0][4] = "course/202/_course/syllabus.md"
    _csv(path, rows)
    with pytest.raises(EvaluationError, match="anchor"):
        evaluate_two_course_rag(
            retriever=retriever, index_root=tmp_path, labels=load_labels(path),
        )


@pytest.mark.parametrize("change", [
    ("negative", "true"),
    ("gold_source", ""),
])
def test_inconsistent_positive_negative_labels_fail(tmp_path, change):
    field, value = change
    row = _rows()[0]
    row[{"negative": 6, "gold_source": 4}[field]] = value
    path = tmp_path / "labels.csv"
    _csv(path, [row])
    with pytest.raises(EvaluationError):
        load_labels(path)


def test_full_mvp_metric_set_and_fixed_k_precision(tmp_path):
    retriever = _setup(tmp_path)
    path = tmp_path / "labels.csv"
    _csv(path, _rows())
    metrics = evaluate_two_course_rag(
        retriever=retriever, index_root=tmp_path, labels=load_labels(path), k=4,
    )
    assert metrics["recall_at_1"] == 1
    assert metrics["recall_at_k"] == 1
    assert metrics["precision_at_1"] == metrics["hit_at_1"] == 1
    assert metrics["precision_at_k"] == 0.25  # 1 labelled passage in 4 slots
    assert metrics["source_traceability"] == 1


def test_retriever_must_not_invent_sources(tmp_path):
    retriever = _setup(tmp_path)
    path = tmp_path / "labels.csv"
    _csv(path, _rows())

    class ForgedRetriever:
        def retrieve(self, course_id, module_id, query, k):
            result = retriever.retrieve(course_id, module_id, query, k)
            return [p.model_copy(update={"source": "course/101/forged/private.txt"})
                    for p in result]

    metrics = evaluate_two_course_rag(
        retriever=ForgedRetriever(), index_root=tmp_path, labels=load_labels(path),
    )
    assert metrics["source_traceability"] == 0  # every returned passage was invented
    assert metrics["hit_at_1"] == 0


def test_a_modified_passage_containing_the_anchor_is_not_relevant(tmp_path):
    retriever = _setup(tmp_path)
    path = tmp_path / "labels.csv"
    _csv(path, _rows())

    class StaleRetriever:
        def retrieve(self, course_id, module_id, query, k):
            return [p.model_copy(update={"text": p.text + " (stale copy)"})
                    for p in retriever.retrieve(course_id, module_id, query, k)]

    metrics = evaluate_two_course_rag(retriever=StaleRetriever(), index_root=tmp_path,
                                      labels=load_labels(path))
    assert metrics["source_traceability"] == 0
    assert metrics["hit_at_1"] == metrics["recall_at_k"] == metrics["mrr_at_k"] == 0
