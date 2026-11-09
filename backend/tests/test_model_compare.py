"""Z2: the 9B vs 27B harness (eval/model-compare/run.py) without any model call: parsing, judging, sizing,
and a whole run against a fake API."""
import importlib.util
import json
from pathlib import Path

EVAL = Path(__file__).resolve().parents[2] / "eval" / "model-compare" / "run.py"
spec = importlib.util.spec_from_file_location("model_compare", EVAL)
mc = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mc)


def test_the_answer_letter_and_the_judge_verdict_are_parsed():
    assert mc.parse_letter("B") == "B" and mc.parse_letter("The answer is C.") == "C"
    assert mc.parse_letter("none of these") is None
    order = ["27b", "9b"]  # A was the 27B answer
    assert mc._winner('{"winner": "A", "reason": "x"}', order) == "27b"
    assert mc._winner('ok {"winner": "B"}', order) == "9b"
    assert mc._winner('{"winner": "tie"}', order) == "tie" and mc._winner("no json", order) == "unparsed"


def test_the_kv_cache_counts_only_the_full_attention_layers():
    per_token = mc.kv_gib_per_token(mc.SIZES["9b"])  # 2 x 8 layers x 4 heads x 256 x 2 bytes
    assert abs(per_token * 2**30 - 2 * 8 * 4 * 256 * 2) < 1e-6
    assert mc.kv_gib_per_token(mc.SIZES["27b"]) == 2 * per_token
    assert any("| 27b |" in line for line in mc.sizing())


class FakeApi:
    def __init__(self) -> None:
        self.calls = []

    def complete(self, model, system, user, max_tokens):
        self.calls.append(model)
        text = '{"winner": "A", "reason": "fine"}' if model == mc.JUDGE else "A"
        return {"text": text, "seconds": 0.1, "prompt_tokens": 10, "completion_tokens": 1, "cost": 0.001}


def test_a_whole_run_against_a_fake_api(tmp_path, monkeypatch):
    monkeypatch.setattr(mc, "OpenRouter", lambda key: FakeApi())
    monkeypatch.setattr(mc, "Passages", lambda: (lambda query, topic, k=4: ["passage one", "passage two"]))
    monkeypatch.setenv("OPENROUTER_API_KEY", "fake-key-for-tests")
    monkeypatch.setattr("sys.argv", ["run.py", "--smoke", "--out", str(tmp_path)])
    mc.main()
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "SMOKE RUN: 3 check items, 2 open questions" in report
    summary = json.loads((tmp_path / "summary.json").read_text(encoding="utf-8"))
    assert len(summary["mcq"]) == 3 * 2 * 2 and len(summary["judged"]) == 2
    lines = (tmp_path / "answers.jsonl").read_text(encoding="utf-8").splitlines()
    mc.main()  # cached: nothing is asked again
    assert (tmp_path / "answers.jsonl").read_text(encoding="utf-8").splitlines() == lines
