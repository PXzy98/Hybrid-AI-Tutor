"""Offline S8 course knowledge core: synthetic evidence only."""
import pytest

from app.learner.knowledge.course_core import (
    CourseEvidence,
    CourseKnowledgeCore,
    CourseKnowledgeError,
)


def _core():
    return CourseKnowledgeCore({"KC-A": [], "KC-B": ["KC-A"], "KC-C": ["KC-B"]})


def _event(*, cid=42, student="fake-student", kc="KC-A",
           kind="strong", correct=True, difficulty="intermediate"):
    return CourseEvidence(cid, student, kc, kind, correct, difficulty)


def test_priors_and_course_ability_are_separate():
    model = _core()
    a = model.initial(42, "fake-student")
    assert model.progress(a, "KC-A").probability == 0.2
    assert a.ability == 0.0
    updated = model.update(a, _event())
    assert updated.ability > 0
    assert updated.kcs["KC-A"].observations == 1
    assert a.ability == 0 and a.kcs == {}


def test_incorrect_answer_decreases_probability_and_ability():
    model = _core()
    start = model.initial(42, "fake-student")
    result = model.update(start, _event(correct=False))
    assert result.ability < 0
    assert result.kcs["KC-A"].probability < 0.2


def test_diagnostic_is_not_practice_and_strong_is():
    model = _core()
    start = model.initial(42, "fake-student")
    diagnostic = model.update(start, _event(kind="diagnostic"))
    practice = model.update(start, _event(kind="strong"))
    assert practice.kcs["KC-A"].probability > diagnostic.kcs["KC-A"].probability
    assert practice.ability == diagnostic.ability


def test_weak_signal_does_not_change_ability_or_observation_count():
    model = _core()
    start = model.initial(42, "fake-student")
    result = model.update(start, _event(kind="weak", correct=None))
    assert result.ability == start.ability
    assert result.kcs["KC-A"].observations == 0
    assert result.kcs["KC-A"].probability < model.progress(start, "KC-A").probability


def test_prerequisites_limit_dependent_effective_mastery():
    model = _core()
    start = model.initial(42, "fake-student")
    state = start
    for _ in range(10):
        state = model.update(state, _event(kc="KC-C"))
    raw = model.progress(state, "KC-C").probability
    effective = model.effective_mastery(state)
    assert effective["KC-C"] < raw
    for _ in range(10):
        state = model.update(state, _event(kc="KC-A"))
        state = model.update(state, _event(kc="KC-B"))
    assert model.effective_mastery(state)["KC-C"] > effective["KC-C"]


@pytest.mark.parametrize("bad", [
    {"cid": 43}, {"student": "other"}, {"kc": "KC-UNKNOWN"},
    {"kind": "weak", "correct": True}, {"kind": "diagnostic", "correct": None},
    {"kind": "invalid"},
])
def test_wrong_course_student_or_evidence_rejected(bad):
    model = _core()
    with pytest.raises(CourseKnowledgeError):
        model.update(model.initial(42, "fake-student"), _event(**bad))


@pytest.mark.parametrize("graph", [
    {"A": ["B"], "B": ["A"]},
    {"A": ["missing"]},
    {"A": ["A"]},
])
def test_bad_prerequisites_rejected(graph):
    with pytest.raises(CourseKnowledgeError):
        CourseKnowledgeCore(graph)


def test_student_independence_and_probability_bounds():
    model = _core()
    first = model.initial(42, "fake-student")
    second = model.initial(42, "another-fake")
    for _ in range(50):
        first = model.update(first, _event())
    assert 0 < first.kcs["KC-A"].probability < 1
    assert -4 <= first.ability <= 4
    assert model.progress(second, "KC-A").probability == 0.2


@pytest.mark.parametrize("sequence", [
    [("diagnostic", True), ("strong", False), ("strong", True)],
    [("strong", False), ("strong", False), ("diagnostic", True)],
    [("weak", None), ("strong", True), ("strong", True)],
])
def test_s8_raw_bkt_matches_v3_update_equations(sequence):
    from app.learner.knowledge.bkt_math import learn, posterior, weak_update

    model = _core()
    state = model.initial(42, "fake-student")
    expected = 0.2
    for kind, correct in sequence:
        state = model.update(state, _event(kind=kind, correct=correct))
        if kind == "weak":
            expected = weak_update(expected, 0.3, 0.6)
        else:
            expected = posterior(expected, correct, 0.1, 0.25)
            if kind == "strong":
                expected = learn(expected, 0.1)
        # v4 uses six-decimal persisted KC states; v3's pure math is otherwise identical.
        expected = round(expected, 6)
        assert model.progress(state, "KC-A").probability == pytest.approx(expected, abs=1e-6)


def test_cross_course_learner_update_never_changes_existing_state():
    model = _core()
    existing = model.initial(42, "fake-student")
    with pytest.raises(CourseKnowledgeError):
        model.update(existing, _event(cid=43))
    assert existing.kcs == {} and existing.ability == 0.0


def test_course_ability_sets_the_start_of_unobserved_kcs():
    model = _core()
    state = model.initial(42, "fake-student")
    for _ in range(5):
        state = model.update(state, _event(kc="KC-A", correct=True))
    assert state.ability > 0
    assert model.progress(state, "KC-B").probability > model.prior  # a new KC starts above the prior
    weak = model.initial(42, "another-fake")
    for _ in range(5):
        weak = model.update(weak, _event(student="another-fake", kc="KC-A", correct=False))
    assert model.progress(weak, "KC-B").probability < model.prior
    plain = CourseKnowledgeCore({"KC-A": [], "KC-B": []}, ability_weight=0.0)
    assert plain.progress(state, "KC-B").probability == plain.prior


def test_parameters_come_from_settings_and_predictions_are_probabilities():
    from app.core.config import Settings

    settings = Settings()
    model = CourseKnowledgeCore.from_settings({"KC-A": []}, settings)
    assert model.prior == settings.learner.bkt_defaults.p_init
    assert model.slip == settings.learner.bkt_defaults.slip
    p = model.predict_correct(model.initial(42, "fake-student"), "KC-A")
    assert model.guess < p < 1 - model.slip
