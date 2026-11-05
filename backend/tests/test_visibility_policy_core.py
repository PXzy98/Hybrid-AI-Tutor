"""S9 consent and audit policy tests; no real learners or network."""
from datetime import UTC, datetime, timedelta

import pytest

from app.learner.visibility_policy import (
    LearnerSignal,
    VisibilityDenied,
    VisibilityState,
    instructor_visible_signals,
)

START = datetime(2026, 11, 5, tzinfo=UTC)


def _state(**changes):
    data = dict(course_id=100, student_id="fictional-a", mode="B",
                acknowledged_at=START, visible_since=START)
    data.update(changes)
    return VisibilityState(**data)


def _signal(*, cid=100, student="fictional-a", when=None, p=0.6):
    return LearnerSignal(course_id=cid, student_id=student,
                         created_at=when or START, kc_id="KC-fake", p_mastery=p)


def _view(state=None, signals=(), *, auth=True, audit=None):
    return instructor_visible_signals(
        state=state or _state(), signals=signals, authorized_instructor=auth,
        audit_view=audit if audit is not None else lambda *_: True,
    )


@pytest.mark.parametrize("change", [
    {"mode": "A"}, {"hidden_from_instructor": True},
    {"acknowledged_at": None}, {"visible_since": None},
    {"visible_since": START - timedelta(seconds=1)},
])
def test_denied_when_consent_is_not_valid(change):
    with pytest.raises(VisibilityDenied):
        _view(_state(**change), [_signal()])


def test_role_required_even_when_consent_is_present():
    with pytest.raises(VisibilityDenied):
        _view(signals=[_signal()], auth=False)


def test_only_post_acknowledgement_course_signals_are_visible():
    seen = []
    signals = [_signal(when=START - timedelta(minutes=1)), _signal(),
               _signal(when=START + timedelta(minutes=1))]
    result = _view(signals=signals, audit=lambda cid, sid: seen.append((cid, sid)) or True)
    assert result == tuple(signals[1:])
    assert seen == [(100, "fictional-a")]


@pytest.mark.parametrize("bad", [
    {"cid": 200}, {"student": "fictional-b"},
    {"when": datetime(2026, 11, 5)}, {"p": 1.5},
])
def test_mismatched_or_invalid_data_fails_closed(bad):
    with pytest.raises(VisibilityDenied):
        _view(signals=[_signal(), _signal(**bad)])


def test_audit_is_mandatory_and_must_succeed():
    with pytest.raises(VisibilityDenied):
        instructor_visible_signals(state=_state(), signals=[_signal()],
                                   authorized_instructor=True)
    with pytest.raises(VisibilityDenied):
        _view(signals=[_signal()], audit=lambda *_: False)


def test_empty_overview_is_still_audited():
    calls = []
    assert _view(signals=[], audit=lambda cid, sid: calls.append((cid, sid)) or True) == ()
    assert calls == [(100, "fictional-a")]


def test_no_question_text_can_enter_signal_data():
    with pytest.raises(TypeError):
        LearnerSignal(course_id=100, student_id="fictional-a", created_at=START,
                      kc_id="KC-fake", p_mastery=0.8, question="a private question")
