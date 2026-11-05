"""S9 learning-plan and opt-out tests; fictional learners only."""
from datetime import UTC, datetime, timedelta

import pytest

from app.learner.learning_plan import LearningPlan, change_visibility, validate_learning_plan
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
    mode_b = change_visibility(_state(), action="mode_b", at=T0, actor_authorized=True)
    assert mode_b.mode == "B" and mode_b.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(mode_b)
    acknowledged = change_visibility(mode_b, action="acknowledge", at=T0, actor_authorized=True)
    assert _update(acknowledged) == _plan()


def test_opt_out_and_in_reset_visibility_window():
    state = change_visibility(_state(), action="mode_b", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", at=T0, actor_authorized=True)
    out = change_visibility(state, action="opt_out", at=T0 + timedelta(minutes=1),
                            actor_authorized=True)
    assert out.hidden_from_instructor and out.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(out)
    moment = T0 + timedelta(hours=2)
    again = change_visibility(out, action="opt_in", at=moment, actor_authorized=True)
    assert again.visible_since == moment
    with pytest.raises(VisibilityDenied):
        _update(again, _plan(created=T0))
    assert _update(again, _plan(created=moment))


def test_mode_a_clears_consent_and_disables_plan():
    state = change_visibility(_state(), action="mode_b", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", at=T0, actor_authorized=True)
    disabled = change_visibility(state, action="mode_a", at=T0, actor_authorized=True)
    assert disabled.visible_since is None
    with pytest.raises(VisibilityDenied):
        _update(disabled)


@pytest.mark.parametrize("changes", [
    {"cid": 202}, {"student": "other"}, {"kc": ("UNKNOWN",)},
    {"kc": ("KC-1", "KC-1")}, {"kc": ()},
])
def test_plan_course_student_and_knowledge_scope(changes):
    state = change_visibility(_state(), action="mode_b", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", at=T0, actor_authorized=True)
    with pytest.raises(VisibilityDenied):
        _update(state, _plan(**changes))


def test_update_must_be_authorized_and_audited():
    state = change_visibility(_state(), action="mode_b", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", at=T0, actor_authorized=True)
    with pytest.raises(VisibilityDenied):
        _update(state, auth=False)
    with pytest.raises(VisibilityDenied):
        _update(state, audit=lambda *_: False)


def test_no_backdated_or_unauthorized_visibility():
    with pytest.raises(VisibilityDenied):
        change_visibility(_state(), action="mode_b", at=T0, actor_authorized=False)
    with pytest.raises(VisibilityDenied):
        change_visibility(_state(), action="acknowledge", at=T0, actor_authorized=True)


def test_plan_notes_are_bounded():
    state = change_visibility(_state(), action="mode_b", at=T0, actor_authorized=True)
    state = change_visibility(state, action="acknowledge", at=T0, actor_authorized=True)
    bad = LearningPlan(101, "fictional-s", ("KC-1",), "basic", "x" * 501, T0)
    with pytest.raises(VisibilityDenied):
        _update(state, bad)
