"""What an instructor may see about one student (task S9; course-structure.md section 4.5).

`profile_for_instructor` checks the course's visibility mode, the student's opt-out and `visible_since`
itself, so no endpoint can forget a condition. The data comes from a `LearnerViewStore` (implemented on the
Z4 tables); without one every request is refused, as in visibility mode A. Every view, including an
export, is audited through the store before anything is returned.
"""
from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from pydantic import BaseModel

from app.core.schemas import Level
from app.learner.knowledge.bkt_math import level_with_hysteresis
from app.learner.visibility_policy import (
    ActivityRecord,
    CheckAnswerRecord,
    LearnerSignal,
    MisconceptionRecord,
    VisibilityDenied,
    VisibilityState,
    instructor_visible_records,
)
from app.platform.access import CourseAccess
from app.platform.settings import effective_settings


class NotVisible(Exception):
    """The instructor may not see this student's individual data (mode A, opted out, or unknown)."""


class KcView(BaseModel):
    kc_code: str
    level: Level
    p_mastery: float


class InstructorProfileView(BaseModel):
    student_id: str
    visible_since: datetime
    kcs: list[KcView] = []
    open_misconceptions: int = 0
    checks_answered: int = 0
    last_active: datetime | None = None


class LearnerViewStore(Protocol):
    """Read access to one student's course data plus the audit log (implemented on the Z4 tables)."""

    def visibility(self, course_id: int, student_id: str) -> VisibilityState | None: ...
    def kc_signals(self, course_id: int, student_id: str) -> Sequence[LearnerSignal]: ...
    def check_answers(self, course_id: int, student_id: str) -> Sequence[CheckAnswerRecord]: ...
    def misconceptions(self, course_id: int, student_id: str) -> Sequence[MisconceptionRecord]: ...
    def activity(self, course_id: int, student_id: str) -> Sequence[ActivityRecord]: ...

    def audit_view(self, course_id: int, student_id: str, viewer_account_id: int) -> bool:
        """Durably record the view; return exactly True on success."""
        ...


_store: LearnerViewStore | None = None


def set_view_store(store: LearnerViewStore | None) -> None:
    """Install the store at startup (Z4); None restores the refuse-everything default."""
    global _store
    _store = store


def profile_for_instructor(viewer: CourseAccess, student_id: str, *,
                           store: LearnerViewStore | None = None) -> InstructorProfileView:
    if viewer.role != "instructor":
        raise NotVisible("instructors only")
    store = store or _store
    if store is None or not student_id:
        raise NotVisible("individual overviews are not available")
    course_id = viewer.course.id
    state = store.visibility(course_id, student_id)
    if state is None or (state.course_id, state.student_id) != (course_id, student_id):
        raise NotVisible("individual overviews are not available")
    records = [*store.kc_signals(course_id, student_id), *store.check_answers(course_id, student_id),
               *store.misconceptions(course_id, student_id), *store.activity(course_id, student_id)]
    try:
        # One gate and one audit for every part of the overview.
        shown = instructor_visible_records(
            state=state, records=records, authorized_instructor=True,
            audit_view=lambda cid, sid: store.audit_view(cid, sid, viewer.account_id),
        )
    except VisibilityDenied as exc:
        raise NotVisible("individual overviews are not available") from exc

    eff = effective_settings(course_id)
    latest: dict[str, LearnerSignal] = {}
    for record in shown:
        if isinstance(record, LearnerSignal) and (
                record.kc_id not in latest or record.created_at >= latest[record.kc_id].created_at):
            latest[record.kc_id] = record
    kcs = [KcView(kc_code=kc, p_mastery=s.p_mastery,
                  level=level_with_hysteresis(s.p_mastery, None, eff.level_basic_below,
                                              eff.level_advanced_above, eff.level_hysteresis))
           for kc, s in sorted(latest.items())]
    open_mc: dict[str, MisconceptionRecord] = {}
    misconceptions = [r for r in shown if isinstance(r, MisconceptionRecord)]
    for record in sorted(misconceptions, key=lambda r: r.created_at):  # the latest state of each
        open_mc[record.misconception_id] = record
    return InstructorProfileView(
        student_id=student_id, visible_since=state.visible_since, kcs=kcs,
        open_misconceptions=sum(not r.resolved for r in open_mc.values()),
        checks_answered=sum(isinstance(r, CheckAnswerRecord) for r in shown),
        last_active=max((r.created_at for r in shown), default=None),
    )


def export_course_profiles(viewer: CourseAccess, student_ids: Sequence[str], *,
                           store: LearnerViewStore | None = None) -> list[InstructorProfileView]:
    """End-of-term export (course-structure.md 3.5): the overviews the instructor may see, with the same
    conditions; students who are not visible are left out. Each exported overview is audited."""
    out = []
    for student_id in student_ids:
        try:
            out.append(profile_for_instructor(viewer, student_id, store=store))
        except NotVisible:
            continue
    return out
