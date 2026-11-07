"""Rule 14: the Chinese-input rules only match Chinese text and leave English input unchanged."""
import json
import re
from pathlib import Path

import pytest

from app.privacy.recognizers.grade import GradeRecognizer
from app.privacy.recognizers.zh_person import ChinesePersonRecognizer

CASES = Path(__file__).resolve().parents[2] / "eval" / "privacy-filter" / "cases.jsonl"
HAN = re.compile(r"[一-鿿]")


def _cases() -> list[dict]:
    return [json.loads(line) for line in CASES.read_text(encoding="utf-8").splitlines() if line.strip()]


def _zh_score() -> re.Pattern:
    (pattern,) = [p for p in GradeRecognizer().patterns if p.name == "zh score"]
    return re.compile(pattern.regex)


@pytest.fixture(scope="module")
def english_texts() -> list[str]:
    texts = [c["text"] for c in _cases() if not HAN.search(c["text"])]
    assert len(texts) > 300
    return texts


def test_chinese_name_rule_never_matches_english_text(english_texts):
    recognizer = ChinesePersonRecognizer()
    assert [t for t in english_texts if recognizer.analyze(t, ["PERSON"])] == []
    # pinyin self-introductions are left to the English recognizers
    assert recognizer.analyze("Hello, I am Zhang Wei. What is asthma?", ["PERSON"]) == []


def test_chinese_score_rule_never_matches_english_text(english_texts):
    pattern = _zh_score()
    assert [t for t in english_texts if pattern.search(t)] == []


def test_chinese_rules_still_find_chinese_input():
    chinese = [c for c in _cases() if HAN.search(c["text"])]
    assert chinese
    recognizer, pattern = ChinesePersonRecognizer(), _zh_score()
    for case in chinese:
        for entity in case["entities"]:
            if entity["type"] == "PERSON":
                found = [case["text"][r.start:r.end] for r in recognizer.analyze(case["text"], ["PERSON"])]
                assert entity["text"] in found
            if entity["type"] == "GRADE":
                assert pattern.search(case["text"]).group(0) == entity["text"]
