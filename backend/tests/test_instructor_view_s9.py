"""S9: profile_for_instructor and the end-of-term export; fictional learners only."""
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import pytest

from app.core.schemas import CourseRef
from app.learner.instructor_view import NotVisible, export_course_profiles, profile_for_instructor
from app.learner.visibility_policy import (
    ActivityRecord,
    CheckAnswerRecord,
    LearnerSignal,
    MisconceptionRecord,
    VisibilityState,
)
from app.platform.access import CourseAccess

T0 = datetime(2026, 11, 5, tzinfo=UTC)
BEFORE, AFTER = T0 - timedelta(days=2), T0 + timedelta(days=1)
COURSE = CourseRef(id=7, code="MED 0000", title="Fictional course", course_type="medical_science")
INSTRUCTOR = CourseAccess(course=COURSE, account_id=2, role="instructor", student_id=None)


@dataclass
class FakeStore:
    states: dict[str, VisibilityState]
    audits: list[tuple] = field(default_factory=list)
    audit_ok: bool = True

    def visibility(self, course_id, student_id):
        return self.states.get(student_id)

    def kc_signals(self, course_id, student_id):
        return [LearnerSignal(course_id, student_id, BEFORE, "KC-1", 0.9),  # before consent: hidden
                LearnerSignal(course_id, student_id, AFTER, "KC-1", 0.3),
                LearnerSignal(course_id, student_id, AFTER, "KC-2", 0.8)]

    def check_answers(self, course_id, student_id):
        return [CheckAnswerRecord(course_id, student_id, BEFORE, "KC-1-q1", True),
                CheckAnswerRecord(course_id, student_id, AFTER, "KC-1-q2", False)]

    def misconceptions(self, course_id, student_id):
        return [MisconceptionRecord(course_id, student_id, AFTER, "MC-1", False),
                MisconceptionRecord(course_id, student_id, AFTER + timedelta(hours=1), "MC-2", False),
                MisconceptionRecord(course_id, student_id, AFTER + timedelta(hours=2), "MC-2", True)]

    def activity(self, course_id, student_id):
        return [ActivityRecord(course_id, student_id, AFTER + timedelta(hours=3), "session")]

    def audit_view(self, course_id, student_id, viewer_account_id):
        self.audits.append((course_id, student_id, viewer_account_id))
        return self.audit_ok


def _state(student="fictional-a", **changes):
    data = dict(course_id=7, student_id=student, mode="B", acknowledged_at=T0, visible_since=T0)
    data.update(changes)
    return VisibilityState(**data)


def test_mode_b_overview_shows_only_data_since_consent_and_is_audited():
    store = FakeStore({"fictional-a": _state()})
    view = profile_for_instructor(INSTRUCTOR, "fictional-a", store=store)
    assert [(k.kc_code, k.p_mastery, k.level) for k in view.kcs] == [("KC-1", 0.3, "basic"),
                                                                     ("KC-2", 0.8, "advanced")]
    assert view.checks_answered == 1 and view.open_misconceptions == 1
    assert view.last_active == AFTER + timedelta(hours=3) and view.visible_since == T0
    assert store.audits == [(7, "fictional-a", 2)]


@pytest.mark.parametrize("state", [
    _state(mode="A", acknowledged_at=None, visible_since=None),
    _state(hidden_from_instructor=True, visible_since=None),
    _state(acknowledged_at=None, visible_since=None),
    _state(course_id=8),
    None,
])
def test_what_must_not_be_seen_is_not_returned(state):
    store = FakeStore({"fictional-a": state} if state else {})
    with pytest.raises(NotVisible):
        profile_for_instructor(INSTRUCTOR, "fictional-a", store=store)
    assert store.audits == []


def test_students_no_store_and_failed_audits_get_nothing():
    store = FakeStore({"fictional-a": _state()})
    student = CourseAccess(course=COURSE, account_id=3, role="student", student_id="fictional-b")
    with pytest.raises(NotVisible):
        profile_for_instructor(student, "fictional-a", store=store)
    with pytest.raises(NotVisible):
        profile_for_instructor(INSTRUCTOR, "fictional-a")  # no store installed
    store.audit_ok = False
    with pytest.raises(NotVisible):
        profile_for_instructor(INSTRUCTOR, "fictional-a", store=store)


def test_end_of_term_export_uses_the_same_conditions():
    store = FakeStore({"fictional-a": _state(),
                       "fictional-b": _state("fictional-b", hidden_from_instructor=True, visible_since=None),
                       "fictional-c": _state("fictional-c", mode="A", acknowledged_at=None,
                                             visible_since=None)})
    exported = export_course_profiles(INSTRUCTOR, ["fictional-a", "fictional-b", "fictional-c", "unknown"],
                                      store=store)
    assert [v.student_id for v in exported] == ["fictional-a"]
    assert store.audits == [(7, "fictional-a", 2)]
