"""Ensure advisor-reviewed CSV exports and draft diagnostic YAML remain in sync."""
import csv
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parents[2]
REVIEW = ROOT / "docs" / "review"
TOPICS = ["asthma", "high_blood_pressure", "migraine", "pneumonia", "type2_diabetes"]


def _csv_rows(path: Path) -> list[dict[str, str]]:
    with path.open(encoding="utf-8-sig", newline="") as stream:
        return list(csv.DictReader(stream))


def test_all_84_diagnostic_items_and_answers_match_review_csv():
    total = 0
    for topic in TOPICS:
        rows = _csv_rows(REVIEW / f"{topic}_review.csv")
        items = {r["id"]: r for r in rows if r["type"] == "ITEM"}
        with (ROOT / "content" / "topics" / topic / "items.yaml").open(encoding="utf-8") as stream:
            actual = yaml.safe_load(stream)
        assert len(items) == len(actual) == (24 if topic == "high_blood_pressure" else 15)
        for item in actual:
            row = items[item["id"]]
            assert item["kc"] == row["kc"]
            assert item["level"] == row["level"]
            assert item["stem"] == row["text"]
            assert item["answer"] == row["answer"]
            assert item["explanation"] == row["explanation_or_correction"]
            assert item["reviewed_by"] is None and not row["reviewed_by"].strip()
            choices = {}
            for key in "ABCD":
                option = item["options"][key]
                text = option["text"] if isinstance(option, dict) else option
                assert text == row["option_" + key]
                choices[key] = text
                if isinstance(option, dict) and "misconception" in option:
                    assert f"{key}={option['misconception']}" in row["distractor_misconceptions"]
            assert len(set(choices.values())) == 4
            assert item["answer"] in choices
            total += 1
    assert total == 84


def test_all_topics_review_preserves_source_notes_and_changed_answer_keys():
    aggregate = _csv_rows(REVIEW / "ALL_TOPICS_LAVIN_REVIEW.csv")
    assert len(aggregate) == 147
    by_id = {r["id"]: r for r in aggregate}
    assert len(by_id) == 147
    for topic in TOPICS:
        for item in _csv_rows(REVIEW / f"{topic}_review.csv"):
            assert by_id[item["id"]]["topic_id"] == topic
            assert all(by_id[item["id"]][key] == value for key, value in item.items())
    assert by_id["PNE.3-q3"]["answer"] == "C"
    assert by_id["PNE.4-q2"]["answer"] == "D"
    assert by_id["T2D.4-q2"]["answer"] == "D"


def test_original_advisor_comments_are_preserved_for_all_13_annotated_items():
    revisions = _csv_rows(REVIEW / "LAVIN_REVISION_LOG.csv")
    assert len(revisions) == 30
    assert len({r["id"] for r in revisions}) == 30
    annotated = [r for r in revisions if r["reviewer_comment"].strip()]
    assert len(annotated) == 13
    for row in annotated:
        assert row["reviewer_comment"] == next(
            r["reviewer_comment"]
            for r in _csv_rows(REVIEW / row["file"])
            if r["id"] == row["id"]
        )
