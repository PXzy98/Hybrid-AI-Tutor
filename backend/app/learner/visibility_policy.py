"""Fail-closed instructor visibility policy for one student's course learner signals.

This policy is not the course authorization layer. The API owner must verify course
membership and permissions before calling it, and persist the mandatory audit event.
No student question text is accepted or returned.
"""
from collections.abc import Callable, Sequence
from dataclasses import dataclass
from datetime import datetime
from typing import Literal, Protocol


class VisibilityDenied(PermissionError):
    """No individual learner data may be returned for this request."""


@dataclass(frozen=True)
class VisibilityState:
    course_id: int
    student_id: str
    mode: Literal["A", "B"]
    acknowledged_at: datetime | None
    visible_since: datetime | None
    hidden_from_instructor: bool = False


@dataclass(frozen=True)
class LearnerSignal:
    course_id: int
    student_id: str
    created_at: datetime
    kc_id: str
    p_mastery: float


AuditView = Callable[[int, str], bool]


class OverviewRecord(Protocol):
    """Any part of the individual overview (course-structure.md 4.5): KC signals, check answers,
    misconceptions, activity. Question text is never part of a record."""

    course_id: int
    student_id: str
    created_at: datetime


@dataclass(frozen=True)
class CheckAnswerRecord:
    course_id: int
    student_id: str
    created_at: datetime
    item_id: str
    correct: bool


@dataclass(frozen=True)
class MisconceptionRecord:
    course_id: int
    student_id: str
    created_at: datetime
    misconception_id: str
    resolved: bool


@dataclass(frozen=True)
class ActivityRecord:
    course_id: int
    student_id: str
    created_at: datetime
    kind: Literal["question", "check", "session"]


@dataclass(frozen=True)
class PreferenceRecord:
    """The student's answer preferences (global, not per course); `created_at` is when they last changed, so
    preferences set before the acknowledgement stay hidden like every other record."""

    course_id: int
    student_id: str
    created_at: datetime
    sequencing: str
    detail: str
    source: str  # onboarding | feedback | implicit




def _aware(value: datetime | None) -> bool:
    return value is not None and value.tzinfo is not None and value.utcoffset() is not None


def instructor_visible_signals(
    *, state: VisibilityState, signals: Sequence[LearnerSignal],
    authorized_instructor: bool = False, audit_view: AuditView | None = None,
) -> tuple[LearnerSignal, ...]:
    """Return only signals permitted by mode B consent, time window and audit.

    A course-role check must supply authorized_instructor=True. The audit callback
    must durably persist the event and return exactly True; otherwise fail closed.
    """
    for signal in signals:
        if not signal.kc_id or not 0.0 <= signal.p_mastery <= 1.0:
            raise VisibilityDenied("Individual learner data is not available.")
    return instructor_visible_records(state=state, records=signals,
                                      authorized_instructor=authorized_instructor, audit_view=audit_view)


def instructor_visible_records[R: OverviewRecord](
    *, state: VisibilityState, records: Sequence[R],
    authorized_instructor: bool = False, audit_view: AuditView | None = None,
) -> tuple[R, ...]:
    """The same gate as instructor_visible_signals for every other part of the overview."""
    if not authorized_instructor or type(state.course_id) is not int or state.course_id <= 0:
        raise VisibilityDenied("Individual learner data is not available.")
    if not state.student_id or state.mode != "B" or state.hidden_from_instructor:
        raise VisibilityDenied("Individual learner data is not available.")
    if not _aware(state.acknowledged_at) or not _aware(state.visible_since):
        raise VisibilityDenied("Individual learner data is not available.")
    if state.visible_since < state.acknowledged_at:
        raise VisibilityDenied("Individual learner data is not available.")
    for record in records:
        if (record.course_id, record.student_id) != (state.course_id, state.student_id):
            raise VisibilityDenied("Individual learner data is not available.")
        if not _aware(record.created_at):
            raise VisibilityDenied("Individual learner data is not available.")
    if audit_view is None or audit_view(state.course_id, state.student_id) is not True:
        raise VisibilityDenied("Individual learner data is not available.")
    return tuple(record for record in records if record.created_at >= state.visible_since)
