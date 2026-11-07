"""S9 learning-plan and opt-out tests; fictional learners only."""
from datetime import UTC, datetime, timedelta

import pytest

from app.learner.learning_plan import (
    LearningPlan,
    change_visibility,
    validate_learning_plan,
    visible_learning_plan,
)
from app.learner.visibility_policy import VisibilityDenied, VisibilityState

T0 = datetime(2026, 11, 5, tzinfo=UTC)


def _state():
    return VisibilityState(101, "fictional-s", "A", None, None)


def _plan(*, student="fictional-s", created=None, kc=("KC-1",), cid=101):
    return LearningPlan(cid, student, kc, "intermediate", "Review lecture one.", created or T0)


def _update(state, plan=None, *, auth=True, audit=None, kcs=None):
    return validate_learning_plan(
        state=state, plan=plan or _plan(), known_kcs=kcs or {"KC-1", "KC-2"},
        authorized_instructor=auth, audit_update=audit if audit is not None else lambda *_: True,
    )


def test_mode_a_to_b_requires_acknowledgement():
    mode_b = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    assert mode_b.mode == "B" and mode_b.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(mode_b)
    acknowledged = change_visibility(mode_b, action="acknowledge", actor="student", at=T0,
                                     actor_authorized=True)
    assert _update(acknowledged) == _plan()


def test_opt_out_and_in_reset_visibility_window():
    state = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", actor="student", at=T0, actor_authorized=True)
    out = change_visibility(state, action="opt_out", actor="student", at=T0 + timedelta(minutes=1),
                            actor_authorized=True)
    assert out.hidden_from_instructor and out.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(out)
    moment = T0 + timedelta(hours=2)
    again = change_visibility(out, action="opt_in", actor="student", at=moment, actor_authorized=True)
    assert again.visible_since == moment
    with pytest.raises(VisibilityDenied):
        _update(again, _plan(created=T0))
    assert _update(again, _plan(created=moment))


def test_mode_a_clears_consent_and_disables_plan():
    state = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", actor="student", at=T0, actor_authorized=True)
    disabled = change_visibility(state, action="mode_a", actor="instructor", at=T0, actor_authorized=True)
    assert disabled.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(disabled)


@pytest.mark.parametrize("changes", [
    {"cid": 202}, {"student": "other"}, {"kc": ("UNKNOWN",)},
    {"kc": ("KC-1", "KC-1")}, {"kc": ()},
])
def test_plan_course_student_and_knowledge_scope(changes):
    state = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", actor="student", at=T0, actor_authorized=True)
    with pytest.raises(VisibilityDenied):
        _update(state, _plan(**changes))


def test_update_must_be_authorized_and_audited():
    state = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", actor="student", at=T0, actor_authorized=True)
    with pytest.raises(VisibilityDenied):
        _update(state, auth=False)
    with pytest.raises(VisibilityDenied):
        _update(state, audit=lambda *_: False)


def test_no_backdated_or_unauthorized_visibility():
    with pytest.raises(VisibilityDenied):
        change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=False)
    with pytest.raises(VisibilityDenied):
        change_visibility(_state(), action="acknowledge", actor="student", at=T0, actor_authorized=True)


def test_plan_notes_are_bounded():
    state = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", actor="student", at=T0, actor_authorized=True)
    bad = LearningPlan(101, "fictional-s", ("KC-1",), "basic", "x" * 501, T0)
    with pytest.raises(VisibilityDenied):
        _update(state, bad)


def _visible():
    state = change_visibility(_state(), action="mode_b", actor="instructor", at=T0, actor_authorized=True)
    return change_visibility(state, action="acknowledge", actor="student", at=T0, actor_authorized=True)


@pytest.mark.parametrize(("action", "actor"), [
    ("acknowledge", "instructor"), ("opt_in", "instructor"), ("opt_out", "instructor"),
    ("mode_a", "student"), ("mode_b", "student"),
])
def test_each_change_belongs_to_one_role(action, actor):
    with pytest.raises(VisibilityDenied):
        change_visibility(_visible(), action=action, actor=actor, at=T0, actor_authorized=True)


def test_an_opt_out_survives_mode_switches_and_a_repeated_acknowledgement():
    later = T0 + timedelta(days=1)
    out = change_visibility(_visible(), action="opt_out", actor="student", at=T0, actor_authorized=True)
    state = change_visibility(out, action="mode_a", actor="instructor", at=later, actor_authorized=True)
    state = change_visibility(state, action="mode_b", actor="instructor", at=later, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", actor="student", at=later, actor_authorized=True)
    assert state.hidden_from_instructor and state.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(state, _plan(created=later))


def test_switching_to_b_again_keeps_the_visibility_window():
    state = _visible()
    again = change_visibility(state, action="mode_b", actor="instructor", at=T0 + timedelta(days=1),
                              actor_authorized=True)
    assert again == state
    acknowledged = change_visibility(state, action="acknowledge", actor="student",
                                     at=T0 + timedelta(days=1), actor_authorized=True)
    assert acknowledged == state


def test_no_learning_plan_is_shown_after_an_opt_out_or_in_mode_a():
    state, plan = _visible(), _plan()
    assert visible_learning_plan(state, plan) == plan
    out = change_visibility(state, action="opt_out", actor="student", at=T0, actor_authorized=True)
    assert visible_learning_plan(out, plan) is None
    back = change_visibility(out, action="opt_in", actor="student", at=T0 + timedelta(hours=1),
                             actor_authorized=True)
    assert visible_learning_plan(back, plan) is None  # the old plan predates the new consent
    a = change_visibility(state, action="mode_a", actor="instructor", at=T0, actor_authorized=True)
    assert visible_learning_plan(a, plan) is None
