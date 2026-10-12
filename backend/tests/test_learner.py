"""Learner model: knowledge models (BKT and rule), preferences, recommender, facade, consent, persistence."""
import sqlite3

import pytest

from app.core.config import get_settings
from app.core.schemas import AskRequest, Evidence, RequestContext
from app.core.services import build_services
from app.learner.preference import PreferenceSignal
from app.pipeline.steps.learner_context import LearnerContextStep

S = "student-1"


def strong(kc, correct, item=None):
    return Evidence(kc_id=kc, kind="strong", correct=correct, item_id=item, source="check")


def diag(kc, correct):
    return Evidence(kc_id=kc, kind="diagnostic", correct=correct, source="onboarding")


def weak(kc, signal="confusion"):
    return Evidence(kc_id=kc, kind="weak", signal=signal, source="understand")


@pytest.fixture
def make(use_config):
    def _make(knowledge="bkt", **learner):
        services = build_services(use_config({"learner": {"knowledge": knowledge, **learner}}))
        services.learner.set_consent(S, True)
        return services.learner
    return _make


def rows(table):
    path = get_settings().database_url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        con.row_factory = sqlite3.Row
        return [dict(r) for r in con.execute(f"SELECT * FROM {table}")]  # noqa: S608


# ------------------------------------------------------------------------- knowledge models
@pytest.mark.parametrize("knowledge", ["bkt", "rule"])
def test_correct_answers_raise_and_wrong_answers_lower(make, knowledge):
    lm = make(knowledge)
    prior = lm.knowledge.state(S, ["HBP.1"])["HBP.1"]
    assert prior.p_mastery == 0.2 and prior.level == "basic" and prior.n_obs == 0
    ups = [lm.observe(S, strong("HBP.1", True)).p_mastery for _ in range(4)]
    assert ups == sorted(ups) and ups[-1] > 0.7
    assert lm.knowledge.state(S, ["HBP.1"])["HBP.1"].level == "advanced"
    downs = [lm.observe(S, strong("HBP.1", False)).p_mastery for _ in range(3)]
    assert downs == sorted(downs, reverse=True) and downs[-1] < ups[-1]
    assert lm.knowledge.state(S, ["HBP.1"])["HBP.1"].n_obs == 7


@pytest.mark.parametrize("knowledge", ["bkt", "rule"])
def test_weak_evidence_moves_less_than_strong(make, knowledge):
    lm = make(knowledge)
    for _ in range(3):
        lm.observe(S, strong("HBP.1", True))
        lm.observe(S, strong("HBP.2", True))
    p1, p2 = (lm.knowledge.state(S, [k])[k].p_mastery for k in ("HBP.1", "HBP.2"))
    after_weak = lm.observe(S, weak("HBP.1")).p_mastery
    after_strong = lm.observe(S, strong("HBP.2", False)).p_mastery
    assert after_weak < p1 and p1 - after_weak < p2 - after_strong
    assert lm.knowledge.state(S, ["HBP.1"])["HBP.1"].n_obs == 3  # weak signals are not graded answers


def test_bkt_diagnostic_has_no_learning_step(make):
    lm = make("bkt")
    d = lm.observe(S, diag("HBP.1", True)).p_mastery
    s = lm.observe(S, strong("HBP.2", True)).p_mastery
    assert d == pytest.approx(0.18 / 0.38, abs=1e-6)
    assert s == pytest.approx(0.18 / 0.38 + (1 - 0.18 / 0.38) * 0.1, abs=1e-6)


def test_bkt_per_level_override(make):
    lm = make("bkt", bkt_by_level={"advanced": {"guess": 0.45}})
    basic_item = lm.observe(S, strong("HBP.1", True, item="HBP.1-q1")).p_mastery  # level basic
    advanced_item = lm.observe(S, strong("HBP.2", True, item="HBP.2-q4")).p_mastery  # level advanced
    assert advanced_item < basic_item  # a correct answer is weaker evidence when guessing is easier


def test_rule_formula(make):
    lm = make("rule", rule={"last_n": 3, "weak_penalty": 0.05})
    assert lm.observe(S, strong("HBP.3", True)).p_mastery == pytest.approx(2 / 3)
    for c in (False, True, True):
        lm.observe(S, strong("HBP.3", c))
    assert lm.knowledge.state(S, ["HBP.3"])["HBP.3"].p_mastery == pytest.approx(3 / 5)  # last 3: F T T
    assert lm.observe(S, weak("HBP.3")).p_mastery == pytest.approx(3 / 5 - 0.05)
    assert lm.observe(S, weak("HBP.3")).p_mastery == pytest.approx(3 / 5 - 0.10)
    assert lm.observe(S, strong("HBP.3", True)).p_mastery == pytest.approx(4 / 5)  # penalties reset; T T T
    assert lm.observe(S, weak("HBP.4")).p_mastery == pytest.approx(0.2 - 0.05)  # no answers: prior - penalty


def test_invalid_evidence_is_rejected(make):
    lm = make()
    with pytest.raises(ValueError, match="unknown KC"):
        lm.observe(S, strong("NOPE.1", True))
    with pytest.raises(ValueError, match="needs `correct`"):
        lm.observe(S, Evidence(kc_id="HBP.1", kind="strong", source="check"))


def test_evidence_log_has_ids_and_numbers_only(make):
    lm = make()
    lm.observe(S, strong("HBP.6", False, item="HBP.6-q1"))
    lm.observe(S, Evidence(kc_id="HBP.6", kind="weak", signal="misconception", misconception_id="HBP.MC2",
                           source="understand"))
    log = rows("evidence_log")
    assert [(r["kind"], r["item_id"], r["misconception_id"], r["weight"]) for r in log] == [
        ("strong", "HBP.6-q1", None, 1.0), ("weak", None, "HBP.MC2", 2.0)]
    assert set(log[0]) == {"id", "student_id", "kc_id", "kind", "source", "item_id", "correct", "signal",
                           "misconception_id", "weight", "created_at"}  # no free-text column


def test_observe_request_caps_weak_updates_per_kc(make):
    lm = make()
    states = lm.observe_request(S, [weak("HBP.1"), weak("HBP.1", "misconception"), weak("HBP.2"),
                                    strong("HBP.1", True)])
    assert [s.kc_id for s in states] == ["HBP.1", "HBP.2", "HBP.1"]
    assert sum(r["kind"] == "weak" for r in rows("evidence_log")) == 2


# ----------------------------------------------------------------------- consent and reset
def test_without_consent_nothing_is_personalized_or_stored(use_config):
    lm = build_services(use_config()).learner
    ctx = lm.context("nobody", "high_blood_pressure")
    assert ctx.personalized is False and ctx.kc_states == {} and ctx.next_kc is None
    assert lm.observe("nobody", strong("HBP.1", True)) is None
    assert lm.update_preferences("nobody", PreferenceSignal(dimension="detail", value="detailed",
                                                            explicit=True)) is None
    for table in ("evidence_log", "learner_kc_state", "learner_preference", "learner_topic_level"):
        assert rows(table) == []


def test_withdrawing_consent_forgets_the_profile(make):
    lm = make()
    lm.observe(S, strong("HBP.1", True))
    lm.set_consent(S, False)
    assert rows("evidence_log") == [] and rows("learner_kc_state") == []
    assert lm.context(S, "high_blood_pressure").personalized is False


def test_reset_keeps_consent(make):
    lm = make()
    lm.observe(S, strong("HBP.1", True))
    lm.update_preferences(S, PreferenceSignal(dimension="detail", value="detailed", explicit=True))
    lm.reset(S)
    assert rows("evidence_log") == [] and rows("learner_preference") == []
    ctx = lm.context(S, "high_blood_pressure")
    assert ctx.personalized and ctx.kc_states["HBP.1"].p_mastery == 0.2
    assert ctx.preferences.detail == "concise"


def test_deleting_the_account_purges_learner_tables(api):
    alice = api.make_student()
    lm = api.services.learner
    lm.set_consent(alice.student_id, True)
    lm.observe(alice.student_id, strong("HBP.1", True))
    lm.context(alice.student_id, "high_blood_pressure")
    api.accounts.delete_student(alice.id)
    for table in ("evidence_log", "learner_kc_state", "learner_topic_level", "consent"):
        assert rows(table) == [], table


# ----------------------------------------------------------------------------- preferences
def test_explicit_preferences_apply_at_once(make):
    lm = make()
    signal = PreferenceSignal(dimension="sequencing", value="concept_first", explicit=True,
                              source="onboarding")
    p = lm.update_preferences(S, signal)
    assert (p.sequencing, p.source) == ("concept_first", "onboarding")
    assert lm.context(S, "high_blood_pressure").preferences.sequencing == "concept_first"


def test_implicit_preferences_need_three_consistent_signals(make):
    lm = make()
    def hint(v):
        return lm.update_preferences(S, PreferenceSignal(dimension="detail", value=v, explicit=False,
                                                         source="implicit"))
    assert hint("detailed").detail == "concise"
    assert hint("detailed").detail == "concise"
    assert hint("concise").detail == "concise"  # inconsistent: streak restarts
    hint("detailed")
    hint("detailed")
    assert hint("detailed").detail == "detailed"
    lm.update_preferences(S, PreferenceSignal(dimension="detail", value="concise", explicit=True))
    assert hint("detailed").detail == "concise"  # an explicit choice reset the streak


def test_invalid_preference_value():
    with pytest.raises(ValueError):
        PreferenceSignal(dimension="detail", value="example_first", explicit=True)


# ----------------------------------------------------------------------------- recommender
def master(lm, kc, n=6):
    for _ in range(n):
        lm.observe(S, strong(kc, True))


def test_recommender_follows_prerequisites(make):
    lm = make()
    rec = lm.recommender
    assert rec.next_kc(S, "high_blood_pressure").kc_id == "HBP.1"  # only KC without prerequisites
    master(lm, "HBP.1")
    assert rec.next_kc(S, "high_blood_pressure").kc_id in {"HBP.2", "HBP.3"}
    master(lm, "HBP.2")
    master(lm, "HBP.3")
    nxt = rec.next_kc(S, "high_blood_pressure")
    assert nxt.kc_id in {"HBP.4", "HBP.5"}
    assert nxt.reason == "prerequisites ready, lowest mastery in this topic"
    lm.observe(S, strong("HBP.4", True))  # HBP.4 now above the prior; HBP.5 is the lowest
    assert rec.next_kc(S, "high_blood_pressure").kc_id == "HBP.5"


def test_recommender_prefers_lowest_mastery_then_fewer_observations(make):
    lm = make()
    master(lm, "HBP.1")
    lm.observe(S, strong("HBP.2", True))
    lm.observe(S, strong("HBP.2", False))  # HBP.2 below HBP.3? compare actual values
    p2 = lm.knowledge.state(S, ["HBP.2"])["HBP.2"].p_mastery
    expected = "HBP.2" if p2 < 0.2 else "HBP.3"
    assert lm.recommender.next_kc(S, "high_blood_pressure").kc_id == expected


def test_recommender_moves_to_another_topic_when_one_is_done(make):
    lm = make()
    for kc in ("HBP.1", "HBP.2", "HBP.3", "HBP.4", "HBP.5", "HBP.6"):
        master(lm, kc, 8)
    nxt = lm.recommender.next_kc(S, "high_blood_pressure")
    assert nxt.kc_id == "AST.1" and nxt.reason.endswith("in Asthma")  # topics are searched in order


# ---------------------------------------------------------------------- context and the step
def test_focus_level_from_question_kcs_is_the_weakest(make):
    lm = make()
    master(lm, "HBP.1")
    ctx = lm.context(S, "high_blood_pressure", kc_ids=["HBP.1", "HBP.2", "UNKNOWN.9"])
    assert ctx.kc_states["HBP.1"].level == "advanced" and ctx.focus_level == "basic"  # HBP.2 is unseen
    assert lm.context(S, "high_blood_pressure", kc_ids=["HBP.1"]).focus_level == "advanced"


def test_focus_level_from_topic_mean_with_hysteresis(make):
    lm = make()
    assert lm.context(S, "high_blood_pressure").focus_level == "basic"
    for kc in ("HBP.1", "HBP.2", "HBP.3", "HBP.4"):
        master(lm, kc)
    assert lm.context(S, "high_blood_pressure").focus_level == "intermediate"  # mean ~0.67
    assert rows("learner_topic_level")[0]["level"] == "intermediate"
    assert set(lm.context(S, "high_blood_pressure").kc_states) == {f"HBP.{n}" for n in range(1, 7)}


async def test_learner_context_step(use_config):
    services = build_services(use_config())
    services.learner.set_consent(S, True)
    ctx = RequestContext(request_id="r", request=AskRequest(student_id=S, topic="high_blood_pressure",
                                                            question="q"))
    ctx = await LearnerContextStep(services).run(ctx)
    assert ctx.learner.personalized and ctx.learner.focus_level == "basic"
    assert ctx.learner.next_kc.kc_id == "HBP.1"
    assert ctx.learner.to_cloud_labels().level == "basic"


def test_ask_reports_level_and_next_kc_with_consent(api):
    alice = api.make_student()
    api.login("alice")
    body = {"topic": "high_blood_pressure", "question": "What do the two numbers mean?"}
    first = api.client.post("/api/v1/ask", json=body).json()
    assert first["kc_level"] is None and first["next_kc"] is None  # no consent yet: unpersonalized
    api.services.learner.set_consent(alice.student_id, True)
    second = api.client.post("/api/v1/ask", json=body).json()
    assert second["kc_level"] == "basic" and second["next_kc"]["kc_id"] == "HBP.1"
    assert "Teaching level for this student: basic" in api.local_llm.sent_text()
