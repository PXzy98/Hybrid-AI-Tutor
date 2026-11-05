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
