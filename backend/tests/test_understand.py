"""Step 11: the understand step, weak evidence and implicit preference hints (design §5.1, §7.1, §11 E1)."""
import json
from contextlib import ExitStack
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.learner import understand
from app.pipeline.steps.update_learner import preference_hints
from app.storage.models import EvidenceLog
from tests.conftest import Api

HBP = "high_blood_pressure"
CASES = Path(__file__).resolve().parents[2] / "eval" / "understand-tagging" / "cases.jsonl"


def reply(k=(), t="other", c=False, m=()) -> str:
    return json.dumps({"k": list(k), "t": t, "c": c, "m": list(m)})


@pytest.fixture
def dev(make_client):
    """`dev(overrides)`: the app with a logged-in, consenting student; closed after the test."""
    with ExitStack() as stack:
        def _make(overrides: dict | None = None) -> Api:
            cfg = {"content": {"serve_unreviewed": True}, **(overrides or {})}
            api = Api(stack.enter_context(make_client(cfg)))
            api.student = api.make_student()
            api.login("alice")
            api.services.learner.set_consent(api.student.student_id, True)
            return api

        yield _make


def ask(api, question="What do the two numbers mean?") -> dict:
    r = api.client.post("/api/v1/ask", json={"topic": HBP, "question": question})
    assert r.status_code == 200, r.text
    return r.json()


def weak_rows(api) -> list[EvidenceLog]:
    with Session(api.services.engine) as db:
        return list(db.exec(select(EvidenceLog).where(EvidenceLog.kind == "weak")))


# ------------------------------------------------------------------------------ prompt and schema
def test_schema_enums_are_the_topics_own_ids(api):
    content = api.services.content
    s = understand.schema(content, HBP)["properties"]
    kc_ids = [k.id for k in content.kcs(HBP)]
    assert s["k"]["items"]["enum"] == kc_ids and s["k"]["maxItems"] == understand.MAX_KCS
    mc_ids = {m.id for k in kc_ids for m in content.misconceptions(k)}
    assert set(s["m"]["items"]["enum"]) == mc_ids and len(mc_ids) == 12
    assert s["t"]["enum"] == understand.QUESTION_TYPES


def test_prompt_lists_kcs_and_catalog_with_few_shot(api):
    msgs = understand.messages(api.services.content, HBP, "Why two numbers?")
    system = msgs[0]["content"]
    assert "HBP.1" in system and "HBP.MC11" in system
    assert len(msgs) == 2 + 2 * len(understand.FEW_SHOT) and msgs[-1]["content"] == "Why two numbers?"
    for q, a in understand.FEW_SHOT:  # the examples themselves pass the parser
        understand.parse(json.dumps(a), api.services.content, HBP, q)


# ------------------------------------------------------------------------------ parse
def test_parse_rejects_bad_json_and_unknown_ids(api):
    content = api.services.content
    for bad in ("not json", reply(k=["HBP.99"]), reply(k=["HBP.1"], t="check_my_answer", m=["HBP.MC99"])):
        with pytest.raises(ValueError):
            understand.parse(bad, content, HBP, "x, right?")


def test_parse_dedupes_and_caps_kcs(api):
    text = reply(k=["HBP.2", "HBP.2", "HBP.3", "HBP.4"], t="nonsense")
    u = understand.parse(text, api.services.content, HBP)
    assert u.kc_ids == ["HBP.2", "HBP.3"] and u.question_type == "other"


def test_misconception_needs_a_stated_belief(api):
    content = api.services.content
    stated = understand.parse(reply(k=["HBP.6"], t="self_management", m=["HBP.MC2"]), content, HBP,
                              "My blood pressure is normal now, so I can stop my medication, right?")
    assert stated.misconception_ids == ["HBP.MC2"]
    asked = understand.parse(reply(k=["HBP.3"], t="check_my_answer", m=["HBP.MC7"]), content, HBP,
                             "Is high blood pressure caused only by stress?")
    assert asked.misconception_ids == []
    wrong_type = understand.parse(reply(k=["HBP.6"], t="how_why", m=["HBP.MC2"]), content, HBP,
                                  "I stopped my pills since I feel fine.")
    assert wrong_type.misconception_ids == []


def test_states_belief_on_the_e1_cases():
    cases = [json.loads(line) for line in CASES.read_text("utf-8").splitlines() if line.strip()]
    for c in cases:
        if c["misconception_ids"]:
            assert understand.states_belief(c["question"]), c["id"]
        if "asks, does not assert" in c["note"]:
            assert not understand.states_belief(c["question"]), c["id"]


# ------------------------------------------------------------------------------ pipeline
def test_unknown_id_skips_the_step_and_the_answer_still_comes(dev):
    api = dev()
    api.understand_llm.replies = [reply(k=["HBP.99"])]
    body = ask(api)
    assert body["answer"]
    assert weak_rows(api) == []


def test_understand_sees_the_question_and_the_schema(dev):
    api = dev()
    ask(api, "Why do nurses measure twice?")
    call = api.understand_llm.calls[-1]
    assert call["json_schema"]["properties"]["k"]["items"]["enum"][0] == "HBP.1"
    assert call["messages"][-1]["content"] == "Why do nurses measure twice?"


def test_check_question_follows_the_tagged_kc(dev):
    api = dev()
    api.understand_llm.replies = [reply(k=["HBP.4"], t="how_why")]
    assert ask(api, "How can it lead to a stroke?")["check_item"]["kc_id"] == "HBP.4"


def test_weak_evidence_is_off_by_default(dev):
    api = dev()
    api.understand_llm.replies = [reply(k=["HBP.1"], t="check_my_answer", c=True, m=["HBP.MC5"])]
    ask(api, "I'm lost. The bottom number is when the heart stops, right?")
    assert weak_rows(api) == []


def test_weak_evidence_is_capped_at_one_update_per_kc(dev):
    api = dev({"learner": {"weak_evidence": True}})
    # confusion and a stated misconception both point at HBP.1: one weak update only
    api.understand_llm.replies = [reply(k=["HBP.1", "HBP.2"], t="check_my_answer", c=True, m=["HBP.MC5"])]
    ask(api, "I'm lost. The bottom number is when the heart stops, right?")
    rows = weak_rows(api)
    assert sorted(r.kc_id for r in rows) == ["HBP.1", "HBP.2"]
    assert all(r.source == "understand" for r in rows)


def test_no_weak_evidence_without_consent(dev):
    api = dev({"learner": {"weak_evidence": True}})
    api.services.learner.set_consent(api.student.student_id, False)
    api.understand_llm.replies = [reply(k=["HBP.1"], t="definition", c=True)]
    ask(api, "I'm lost, what is systolic?")
    assert weak_rows(api) == []


# ------------------------------------------------------------------------------ preference hints
def test_preference_hints_from_wording():
    values = lambda q: {(s.dimension, s.value) for s in preference_hints(q)}  # noqa: E731
    assert values("Can you give an example?") == {("sequencing", "example_first")}
    assert values("Explain step by step") == {("detail", "detailed")}
    assert values("Briefly, what is the general idea?") == {("detail", "concise"),
                                                             ("sequencing", "concept_first")}
    assert values("What is diastolic pressure?") == set()
    assert all(not s.explicit for s in preference_hints("in detail please"))


def test_implicit_hints_change_preferences_only_after_a_streak(dev):
    api = dev()
    prefs = lambda: api.services.learner.preferences.get(api.student.student_id)  # noqa: E731
    for _ in range(2):
        ask(api, "Explain salt step by step")
    assert prefs().detail == "concise"
    ask(api, "Explain salt step by step")
    assert prefs().detail == "detailed"
