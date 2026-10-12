"""Domain content: the HBP draft is valid and follows the authoring rules; every validation rule bites."""
import copy
import csv
import re
import sys
from collections import Counter
from pathlib import Path

import pytest
import yaml

from app.core.config import get_settings
from app.learner.content import ContentError, ContentStore, find_cycle

REPO = Path(__file__).resolve().parents[2]
CONTENT = REPO / "content" / "topics"
HBP = CONTENT / "high_blood_pressure"


@pytest.fixture(scope="module")
def store() -> ContentStore:
    return ContentStore(CONTENT, serve_unreviewed=True)


# ------------------------------------------------------------------------- real content
def test_all_topics_load(store):
    assert sorted(store.topics()) == sorted(get_settings().topics())
    assert all(store.kcs(t) for t in store.topics())


def test_hbp_draft_shape(store):
    tc = store.topic("high_blood_pressure")
    assert tc.name == "High Blood Pressure" and "TBD" in tc.guideline
    assert [k.id for k in tc.kcs] == [f"HBP.{n}" for n in range(1, 7)]
    assert len(tc.items) == 24 and 10 <= len(tc.misconceptions) <= 12
    for k in tc.kcs:
        levels = Counter(i.level for i in tc.items if i.kc == k.id)
        assert sum(levels.values()) == 4 and set(levels) == {"basic", "intermediate", "advanced"}, k.id
    used = {o.misconception for i in tc.items for o in i.options.values() if o.misconception}
    assert used == {m.id for m in tc.misconceptions}  # every misconception can be detected by some item


def test_answer_positions_are_spread(store):
    """Students must not be able to guess 'always A'."""
    counts = Counter(i.answer for i in store.topic("high_blood_pressure").items)
    assert set(counts) == {"A", "B", "C", "D"} and max(counts.values()) <= 0.4 * sum(counts.values())


def test_hbp_files_follow_the_authoring_rules():
    for name in ("kcs.yaml", "items.yaml", "misconceptions.yaml"):
        text = (HBP / name).read_text(encoding="utf-8")
        assert text.startswith("# DRAFT — generated, not medically reviewed."), name
        assert not re.search(r"\b\d+\s?(?:mg|mcg|ml|units?)\b", text, re.I), f"{name}: looks like a dose"
        reading = re.search(r"\b\d{2,3}\s*(?:/|over)\s*\d{2,3}\b", text)
        assert not reading, f"{name}: looks like a BP threshold"
        assert "reviewed_by: null" in text or name == "kcs.yaml"


def test_unreviewed_items_are_not_served_by_default():
    strict, dev = ContentStore(CONTENT), ContentStore(CONTENT, serve_unreviewed=True)
    assert strict.items("HBP.1") == [] and len(dev.items("HBP.1")) == 4
    assert strict.reviewed_item_count("high_blood_pressure") == 0
    assert len(strict.items("HBP.1", reviewed_only=False)) == 4


def test_public_item_hides_key_and_tags(store):
    pub = store.item("HBP.6-q1").public()
    assert set(pub.options) == {"A", "B", "C", "D"} and pub.kc_id == "HBP.6"
    dumped = pub.model_dump_json()
    assert "HBP.MC" not in dumped and "answer" not in dumped and "explanation" not in dumped


def test_lookups(store):
    assert store.prerequisites("HBP.6") == ["HBP.2", "HBP.4"]
    assert store.topic_of("HBP.3") == "high_blood_pressure"
    assert store.misconception("HBP.MC2").kc == "HBP.6"
    assert {m.id for m in store.misconceptions("HBP.1")} == {"HBP.MC3", "HBP.MC4", "HBP.MC5"}
    assert store.kc("NOPE") is None and store.item("NOPE") is None and store.kcs("nope") == []


# --------------------------------------------------------------- validation (broken copies)
def write_topic(root: Path, kcs: dict, items: list, mcs: list, name: str = "topic_a") -> None:
    d = root / name
    d.mkdir(parents=True)
    (d / "kcs.yaml").write_text(yaml.safe_dump(kcs), encoding="utf-8")
    (d / "items.yaml").write_text(yaml.safe_dump(items), encoding="utf-8")
    (d / "misconceptions.yaml").write_text(yaml.safe_dump(mcs), encoding="utf-8")


def valid():
    kcs = {"topic": "topic_a", "name": "Topic A", "kcs": [
        {"id": "A.1", "name": "one", "difficulty": "basic", "prerequisites": []},
        {"id": "A.2", "name": "two", "difficulty": "intermediate", "prerequisites": ["A.1"]}]}
    items = [{"id": "A.1-q1", "kc": "A.1", "level": "basic", "stem": "?", "answer": "B",
              "options": {"A": {"text": "wrong", "misconception": "A.MC1"},
                          "B": "right", "C": "c", "D": "d"}}]
    mcs = [{"id": "A.MC1", "kc": "A.1", "statement": "s", "correction": "c"}]
    return kcs, items, mcs


def test_valid_fixture_loads(tmp_path):
    write_topic(tmp_path, *valid())
    assert ContentStore(tmp_path).kcs("topic_a")[1].prerequisites == ["A.1"]


def _break(kind):
    kcs, items, mcs = copy.deepcopy(valid())
    match kind:
        case "duplicate id":
            mcs.append({"id": "A.1", "kc": "A.1", "statement": "s", "correction": "c"})
        case "unknown prerequisite":
            kcs["kcs"][1]["prerequisites"] = ["A.9"]
        case "cycle":
            kcs["kcs"][0]["prerequisites"] = ["A.2"]
        case "three options":
            del items[0]["options"]["D"]
        case "answer not an option":
            items[0]["answer"] = "D"
            del items[0]["options"]["D"]
        case "unknown misconception tag":
            items[0]["options"]["A"]["misconception"] = "A.MC9"
        case "misconception with unknown kc":
            mcs[0]["kc"] = "A.7"
        case "item with unknown kc":
            items[0]["kc"] = "A.7"
        case "answer tagged as misconception":
            items[0]["answer"] = "A"
        case "unknown field":
            items[0]["hint"] = "typo field"
    return kcs, items, mcs


@pytest.mark.parametrize(("kind", "message"), [
    ("duplicate id", "duplicate ID 'A.1'"),
    ("unknown prerequisite", "unknown prerequisite 'A.9'"),
    ("cycle", "prerequisite cycle A.1 -> A.2 -> A.1"),
    ("three options", "exactly the options A, B, C, D"),
    ("answer not an option", "answer 'D' is not one of its options"),
    ("unknown misconception tag", "unknown misconception 'A.MC9'"),
    ("misconception with unknown kc", "misconception A.MC1 refers to unknown KC 'A.7'"),
    ("item with unknown kc", "item A.1-q1 refers to unknown KC 'A.7'"),
    ("answer tagged as misconception", "tags its correct answer with a misconception"),
    ("unknown field", "invalid format"),
])
def test_each_validation_rule(tmp_path, kind, message):
    write_topic(tmp_path, *_break(kind))
    with pytest.raises(ContentError) as e:
        ContentStore(tmp_path)
    assert message in str(e.value)


def test_find_cycle():
    assert find_cycle({"a": ["b"], "b": ["c"], "c": []}) is None
    assert find_cycle({"a": ["b"], "b": ["c"], "c": ["a"]}) == ["a", "b", "c", "a"]
    assert find_cycle({"a": ["a"]}) == ["a", "a"]


def test_invalid_content_stops_startup(use_config, tmp_path):
    from app.core.services import build_services

    write_topic(tmp_path / "content", *_break("cycle"))
    with pytest.raises(ContentError):
        build_services(use_config({"content": {"dir": str(tmp_path / "content")}}))


# ----------------------------------------------------------------------- API + review export
def test_topics_endpoint_counts(api):
    api.make_student()
    api.login("alice")
    topics = {t["id"]: t for t in api.client.get("/api/v1/topics").json()}
    assert topics["high_blood_pressure"] == {"id": "high_blood_pressure", "name": "High Blood Pressure",
                                             "kc_count": 6, "reviewed_item_count": 0}
    assert topics["asthma"]["kc_count"] == 1


def test_review_export(tmp_path, monkeypatch):
    sys.path.insert(0, str(REPO / "scripts"))
    monkeypatch.setattr(sys, "path", sys.path)
    import export_content_review

    export_content_review.main(["high_blood_pressure", "--out", str(tmp_path)])
    rows = list(csv.DictReader((tmp_path / "high_blood_pressure_review.csv").open(encoding="utf-8-sig")))
    assert Counter(r["type"] for r in rows) == {"TOPIC": 1, "KC": 6, "ITEM": 24, "MISCONCEPTION": 12}
    item = next(r for r in rows if r["id"] == "HBP.6-q1")
    assert item["answer"] and item["option_D"] and "HBP.MC2" in item["distractor_misconceptions"]
    assert all(r["reviewer_comment"] == "" for r in rows)
