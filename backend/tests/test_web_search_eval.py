"""T13 / G1-106: the web search comparison harness (eval/web-search/run.py) without any network call: URL
matching, statistics, the question files, and a whole run against fake search, answer and judge clients."""
import importlib.util
import json
from pathlib import Path

from app.core.schemas import Chunk

EVAL = Path(__file__).resolve().parents[2] / "eval" / "web-search"
spec = importlib.util.spec_from_file_location("web_search_eval", EVAL / "run.py")
ws = importlib.util.module_from_spec(spec)
spec.loader.exec_module(ws)


def test_reference_pages_and_sites_are_matched():
    ref = "https://www.cdc.gov/flu/season/index.html"
    assert ws.reference_hit(ref, ["https://cdc.gov/flu/season/index.html/"]) == {"page": True, "site": True}
    assert ws.reference_hit(ref, ["https://www.cdc.gov/other"]) == {"page": False, "site": True}
    assert ws.reference_hit(ref, ["https://nih.gov/x"]) == {"page": False, "site": False}
    assert ws.reference_hit("", ["https://nih.gov/x"]) == {"page": None, "site": None}
    # the same paper under the addresses that PubMed, SearXNG and arXiv use
    assert ws.same_page("https://pubmed.ncbi.nlm.nih.gov/40373211/", "https://www.ncbi.nlm.nih.gov/pubmed/40373211")
    assert ws.same_page("https://arxiv.org/abs/2512.24354", "https://arxiv.org/pdf/2512.24354v2.pdf")
    assert not ws.same_page("https://arxiv.org/abs/2512.24354", "https://arxiv.org/abs/2512.24355")
    assert (ws.site("https://www.ebi.ac.uk/x") == "ebi.ac.uk"
            and ws.site("https://pubmed.ncbi.nlm.nih.gov/1") == "nih.gov")


def test_statistics():
    lo, hi = ws.wilson(5, 10)
    assert 0.23 < lo < 0.24 and 0.76 < hi < 0.77
    assert ws.sign_test(0, 0) == 1.0 and ws.sign_test(10, 0) < 0.01
    assert ws.pct([3, 1, 2], 0.5) == 2 and ws.pct([], 0.5) is None
    assert ws.parse_json('noise {"verdict": "correct"} end') == {"verdict": "correct"}
    assert ws.parse_json("no json") == {}


def test_the_question_files_are_complete_and_fictional():
    questions = ws.load_jsonl(EVAL / "questions.jsonl")
    assert {q["subject"] for q in questions} == set(ws.SUBJECTS)
    for q in questions:
        assert set(q) >= {"id", "subject", "course_type", "needs_fresh", "question", "reference_answer",
                          "reference_url"}
        assert not q["needs_fresh"] or q["reference_url"].startswith("https://")
    assert len({q["id"] for q in questions}) == len(questions)
    privacy = ws.load_jsonl(EVAL / "privacy_questions.jsonl")
    assert privacy and all(p["pii"] for p in privacy)


class FakeOpenAI:
    def __init__(self) -> None:
        self.calls = []

    async def respond(self, model, messages, *, allowlist=None):
        self.calls.append((model, allowlist is not None, messages[-1]["content"]))
        return {"text": "An answer.", "seconds": 0.1, "input_tokens": 100, "output_tokens": 20,
                "searches": int(allowlist is not None), "cited": ["https://nih.gov/a"] if allowlist else [],
                "sources": [], "cost": 0.001, "status": "completed"}


class FakeJudge:
    async def ask(self, system, user):
        text = '{"winner": "A"}' if "two answers" in system else '{"verdict": "correct", "supported": "yes"}'
        return {"text": text, "cost": 0.0001}


async def fake_search(query, allowlist, *, engines=None, settings=None, transport=None):
    return [Chunk(text="A web passage.", source="https://nih.gov/a", topic="web", score=0)]


def test_a_whole_run_against_fakes(tmp_path):
    api = FakeOpenAI()
    assert ws.main(["--smoke", "--out", str(tmp_path)], openai=api, judge=FakeJudge(),
                   search=fake_search) == 0
    runs = ws.load_jsonl(tmp_path / "runs.jsonl")
    assert {r["arm"] for r in runs} == set(ws.ARMS) and not any("error" in r for r in runs)
    assert len(runs) == 3 * len(ws.ARMS)
    # A has no passages, B and C carry the web passage into the prompt, D asks with the allow-list
    prompts = {(m, tool): c for m, tool, c in api.calls}
    assert any("A web passage." in c for c in prompts.values())
    assert (ws.LOW_COST_MODEL, True) in prompts
    judged = ws.load_jsonl(tmp_path / "judge.jsonl")
    assert sum(j["key"].startswith("grade|") for j in judged) == len(runs)
    report = (tmp_path / "report.md").read_text(encoding="utf-8")
    assert "## Performance" in report and "## Pairwise" in report and "B SearXNG vs C Tavily" in report
    # a rerun asks nothing new
    before = len(api.calls)
    ws.main(["--smoke", "--out", str(tmp_path)], openai=api, judge=FakeJudge(), search=fake_search)
    assert len(api.calls) == before
    assert json.loads((tmp_path / "privacy.json").read_text(encoding="utf-8")) == []
