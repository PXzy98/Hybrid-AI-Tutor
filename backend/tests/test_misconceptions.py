"""Step 12: misconception tracking and corrections (design §5.1, §6, §8.1)."""
import json
from contextlib import ExitStack

import pytest
from sqlmodel import Session, select

from app.core.schemas import AskRequest, LearnerContext, RequestContext
from app.learner.checks import choose_item
from app.learner.misconceptions import NOTE_HEADER, addresses, append_corrections
from app.storage.models import LearnerMisconception
from app.verify.checkers.medical_safety import problems
from tests.conftest import Api

HBP = "high_blood_pressure"


@pytest.fixture
def dev(make_client):
    """`dev(overrides)`: the app with a logged-in, consenting student; closed after the test."""
    with ExitStack() as stack:
        def _make(overrides: dict | None = None, consent: bool = True) -> Api:
            cfg = {"content": {"serve_unreviewed": True}, **(overrides or {})}
            api = Api(stack.enter_context(make_client(cfg)))
            api.student = api.make_student()
            api.sid = api.student.student_id
            api.login("alice")
            if consent:
                api.services.learner.set_consent(api.sid, True)
            return api

        yield _make


def tagged_choice(api, item_id: str, mc_id: str | None = None) -> str:
    item = api.services.content.item(item_id)
    return next(k for k, o in item.options.items()
                if o.misconception and (mc_id is None or o.misconception == mc_id))


def check(api, item_id: str, choice: str) -> dict:
    r = api.client.post("/api/v1/check", json={"item_id": item_id, "choice": choice})
    assert r.status_code == 200, r.text
    return r.json()


def ask(api, question="What do the two numbers mean?") -> dict:
    r = api.client.post("/api/v1/ask", json={"topic": HBP, "question": question})
    assert r.status_code == 200, r.text
    return r.json()


def open_on_me(api) -> list[dict]:
    return api.client.get("/api/v1/learner/me", params={"topic": HBP}).json()["topics"][0]["misconceptions"]


def status(api, mc_id: str) -> str | None:
    row = api.services.learner.repo.misconception(api.sid, mc_id)
    return row.status if row else None


def stated(mc_id: str, kc: str) -> str:
    return json.dumps({"k": [kc], "t": "check_my_answer", "c": False, "m": [mc_id]})


# ------------------------------------------------------------------------------ transitions
def test_status_transitions(dev):
    api = dev()
    t = api.services.learner.tracker
    assert t.weak_signal(api.sid, "HBP.MC5") == "suspected"
    assert t.weak_signal(api.sid, "HBP.MC5") == "confirmed"  # second weak signal
    assert t.distractor_chosen(api.sid, "HBP.MC4") == "confirmed"  # strong evidence at once
    item = api.services.content.item("HBP.1-q4")  # its distractors target MC4 and MC5
    assert t.answered_correctly(api.sid, item) == ["HBP.MC4", "HBP.MC5"]
    assert status(api, "HBP.MC4") == status(api, "HBP.MC5") == "resolved"
    assert t.weak_signal(api.sid, "HBP.MC5") == "suspected"  # reopened, counting from 1 again
    assert api.services.learner.repo.misconception(api.sid, "HBP.MC5").evidence_count == 1
    assert t.weak_signal(api.sid, "HBP.MC99") is None


def test_only_ids_and_counts_are_stored(dev):
    api = dev()
    api.services.learner.tracker.weak_signal(api.sid, "HBP.MC3")
    with Session(api.services.engine) as db:
        row = db.exec(select(LearnerMisconception)).one()
    assert set(row.model_dump()) == {"id", "student_id", "misconception_id", "kc_id", "status",
                                     "evidence_count", "updated_at"}


def test_without_consent_nothing_is_tracked(dev):
    api = dev(consent=False)
    check(api, "HBP.1-q2", tagged_choice(api, "HBP.1-q2", "HBP.MC5"))
    api.understand_llm.replies = [stated("HBP.MC5", "HBP.1")]
    ask(api, "The bottom number is when the heart stops, right?")
    assert api.services.learner.repo.misconceptions(api.sid) == []


def test_reset_forgets_misconceptions(dev):
    api = dev()
    check(api, "HBP.1-q2", tagged_choice(api, "HBP.1-q2", "HBP.MC5"))
    assert api.client.delete("/api/v1/learner/me").status_code == 204
    assert api.services.learner.repo.misconceptions(api.sid) == []


# ------------------------------------------------------------------------------ API flow
def test_distractor_shows_in_what_i_know_and_a_correct_answer_resolves_it(dev):
    api = dev()
    content = api.services.content
    check(api, "HBP.1-q2", tagged_choice(api, "HBP.1-q2", "HBP.MC5"))
    shown = open_on_me(api)
    mc = content.misconception("HBP.MC5")
    assert shown == [{"kc_id": "HBP.1", "statement": mc.statement, "correction": mc.correction,
                      "status": "confirmed"}]
    check(api, "HBP.1-q4", content.item("HBP.1-q4").answer)  # also targets MC5
    assert open_on_me(api) == [] and status(api, "HBP.MC5") == "resolved"


def test_stated_misconception_is_suspected_then_confirmed(dev):
    api = dev()  # learner.weak_evidence stays off: tracking does not depend on it
    api.understand_llm.replies = [stated("HBP.MC2", "HBP.6")]
    ask(api, "My readings are normal now, so I can stop my pills, right?")
    assert [m["status"] for m in open_on_me(api)] == ["suspected"]
    ask(api, "My readings are normal now, so I can stop my pills, right?")
    assert [m["status"] for m in open_on_me(api)] == ["confirmed"]


def test_unreviewed_corrections_are_tracked_but_not_shown(dev):
    api = dev({"content": {"serve_unreviewed": False}})
    api.services.learner.tracker.distractor_chosen(api.sid, "HBP.MC5")
    assert status(api, "HBP.MC5") == "confirmed"
    assert api.services.learner.context(api.sid, HBP).misconceptions == []
    assert open_on_me(api) == []


# ------------------------------------------------------------------------------ answers
def test_local_prompt_addresses_the_open_misconception(dev):
    api = dev()
    check(api, "HBP.1-q2", tagged_choice(api, "HBP.1-q2", "HBP.MC5"))
    api.understand_llm.replies = [json.dumps({"k": ["HBP.1"], "t": "definition", "c": False, "m": []})]
    body = ask(api, "What is diastolic pressure?")
    system = api.local_llm.last_messages[0]["content"]
    mc = api.services.content.misconception("HBP.MC5")
    assert "Address this misunderstanding" in system and mc.statement in system and mc.correction in system
    assert system.count("Address this misunderstanding") == 1
    assert NOTE_HEADER not in body["answer"]  # local route: the model addresses it, no appended note


def test_prompt_keeps_to_the_questions_kcs_and_at_most_two(dev):
    api = dev()
    t = api.services.learner.tracker
    for mc in ("HBP.MC3", "HBP.MC4", "HBP.MC5", "HBP.MC2"):  # three on HBP.1, one on HBP.6
        t.distractor_chosen(api.sid, mc)
    refs = api.services.learner.context(api.sid, HBP, ["HBP.6"]).misconceptions
    assert [m.id for m in refs] == ["HBP.MC2"]
    assert len(api.services.learner.context(api.sid, HBP, ["HBP.1"]).misconceptions) == 2


def test_suspected_and_confirmed_order(dev):
    api = dev()
    t = api.services.learner.tracker
    t.distractor_chosen(api.sid, "HBP.MC4")
    t.weak_signal(api.sid, "HBP.MC5")  # more recent, but only suspected
    assert [m.id for m in t.refs(api.sid, ["HBP.1"])] == ["HBP.MC4", "HBP.MC5"]


def cloud_ctx(api, answer: str, target="cloud") -> RequestContext:
    api.services.learner.tracker.distractor_chosen(api.sid, "HBP.MC2")
    learner: LearnerContext = api.services.learner.context(api.sid, HBP, ["HBP.6"])
    return RequestContext(request_id="r", request=AskRequest(student_id=api.sid, topic=HBP, question="q"),
                          learner=learner, answer=answer, target=target)


def test_cloud_answer_gets_the_correction_unless_it_already_addresses_it(dev):
    api = dev()
    correction = api.services.content.misconception("HBP.MC2").correction
    ctx = cloud_ctx(api, "Medicines lower blood pressure.")
    append_corrections(ctx)
    assert ctx.answer == f"Medicines lower blood pressure.\n\n{NOTE_HEADER} {correction}"
    addressed = ("Normal readings while you take a medicine usually show the treatment is working, so "
                 "stopping or changing it should be discussed with a clinician.")
    ctx = cloud_ctx(api, addressed)
    append_corrections(ctx)
    assert ctx.answer == addressed
    ctx = cloud_ctx(api, "Medicines lower blood pressure.", target="local")
    append_corrections(ctx)
    assert ctx.answer == "Medicines lower blood pressure."


def test_keyword_check():
    correction = "Both numbers matter. Either the top or the bottom number can be raised."
    answer = "Both numbers matter: the bottom number can be raised too, not only the top."
    assert addresses(answer, correction)
    assert not addresses("Salt makes the body hold water.", correction)


def test_every_correction_passes_medical_safety(api):
    for mc in api.services.content.all_misconceptions():
        assert problems(f"General answer.\n\n{NOTE_HEADER} {mc.correction}") == [], mc.id


# ------------------------------------------------------------------------------ check items
def test_check_item_prefers_one_that_targets_an_open_misconception(dev):
    api = dev()
    content, repo = api.services.content, api.services.learner.repo
    plain = choose_item(content, repo, api.sid, "HBP.1", "basic")
    targeted = choose_item(content, repo, api.sid, "HBP.1", "basic", {"HBP.MC4"})
    assert "HBP.MC4" not in content.targeted_misconceptions(plain)
    assert targeted.id == "HBP.1-q4"


def test_attach_check_uses_open_misconceptions(dev):
    api = dev()
    api.services.learner.tracker.distractor_chosen(api.sid, "HBP.MC4")
    api.understand_llm.replies = [json.dumps({"k": ["HBP.1"], "t": "definition", "c": False, "m": []})]
    assert ask(api, "What is systolic pressure?")["check_item"]["id"] == "HBP.1-q4"
