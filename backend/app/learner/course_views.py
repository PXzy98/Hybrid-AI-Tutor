"""Visibility, individual overviews and learning plans on the database (task S9; course-structure.md 4.5).

The rules live in `visibility_policy`, `learning_plan` and `instructor_view`; this module reads and writes
the rows they work on: the visibility fields of `course_member`, the learner tables of one course, the
`learning_plan` table and the audit log. Nothing here holds or returns question text.
"""
from collections.abc import Sequence

from sqlalchemy import Engine, delete, update
from sqlmodel import Session, select

from app.learner.learning_plan import (
    LearningPlan,
    change_visibility,
    validate_learning_plan,
    visible_learning_plan,
)
from app.learner.visibility_policy import (
    ActivityRecord,
    CheckAnswerRecord,
    LearnerSignal,
    MisconceptionRecord,
    VisibilityState,
)
from app.platform.settings import effective_settings
from app.storage.models import (
    Account,
    AuditLog,
    CourseMember,
    EvidenceLog,
    LearnerKcState,
    LearnerMisconception,
    RequestLog,
    SessionTurn,
    utcnow,
)
from app.storage.models import LearningPlan as PlanRow


def _member(db: Session, course_id: int, student_id: str) -> CourseMember | None:
    """The active student membership of this pseudonymous student in the course."""
    return db.exec(select(CourseMember).join(Account, CourseMember.account_id == Account.id).where(
        CourseMember.course_id == course_id, CourseMember.role == "student",
        CourseMember.status == "active", Account.student_id == student_id)).first()


def _state(member: CourseMember, course_id: int, student_id: str) -> VisibilityState:
    mode = effective_settings(course_id).visibility_mode
    return VisibilityState(course_id, student_id, mode, member.visibility_ack_at, member.visible_since,
                           member.hidden_from_instructor)


def visibility_state(engine: Engine, course_id: int, student_id: str) -> VisibilityState | None:
    with Session(engine) as db:
        member = _member(db, course_id, student_id)
        return _state(member, course_id, student_id) if member else None


def change_student_visibility(engine: Engine, course_id: int, student_id: str, action: str,
                              account_id: int) -> VisibilityState:
    """The student acknowledges mode B, opts out or opts back in. Raises VisibilityDenied when the action
    is not possible (for example acknowledging in mode A)."""
    with Session(engine) as db:
        member = _member(db, course_id, student_id)
        if member is None:
            raise LookupError("not a student of this course")
        new = change_visibility(_state(member, course_id, student_id), action=action, at=utcnow(),
                                actor="student", actor_authorized=True)
        member.visibility_ack_at, member.visible_since = new.acknowledged_at, new.visible_since
        member.hidden_from_instructor = new.hidden_from_instructor
        db.add(member)
        db.add(AuditLog(account_id=account_id, action=f"learner.visibility.{action}",
                        target=f"course:{course_id}", details={}))
        db.commit()
        return new


def reset_visibility(db: Session, course_id: int) -> None:
    """The course's visibility mode changed: nobody is visible until they acknowledge mode B (again).
    An opt-out is the student's own choice and stays. The caller commits."""
    db.exec(update(CourseMember).where(CourseMember.course_id == course_id)
            .values(visible_since=None, visibility_ack_at=None))


def course_student_ids(engine: Engine, course_id: int) -> list[str]:
    """student_ids of the active students of the course."""
    with Session(engine) as db:
        rows = db.exec(select(Account.student_id).join(CourseMember, CourseMember.account_id == Account.id)
                       .where(CourseMember.course_id == course_id, CourseMember.role == "student",
                              CourseMember.status == "active")).all()
    return sorted(s for s in rows if s)


class DbLearnerViewStore:
    """`instructor_view.LearnerViewStore` on the course tables."""

    def __init__(self, engine: Engine) -> None:
        self.engine = engine

    def visibility(self, course_id: int, student_id: str) -> VisibilityState | None:
        return visibility_state(self.engine, course_id, student_id)

    def _rows(self, table, course_id: int, student_id: str, *where):
        with Session(self.engine) as db:
            return db.exec(select(table).where(table.course_id == course_id, table.student_id == student_id,
                                               *where)).all()

    def kc_signals(self, course_id: int, student_id: str) -> Sequence[LearnerSignal]:
        return [LearnerSignal(course_id, student_id, r.last_seen, r.kc_id, r.p_mastery)
                for r in self._rows(LearnerKcState, course_id, student_id) if r.last_seen is not None]

    def check_answers(self, course_id: int, student_id: str) -> Sequence[CheckAnswerRecord]:
        return [CheckAnswerRecord(course_id, student_id, r.created_at, r.item_id, bool(r.correct))
                for r in self._rows(EvidenceLog, course_id, student_id, EvidenceLog.source == "check")
                if r.item_id and r.correct is not None]

    def misconceptions(self, course_id: int, student_id: str) -> Sequence[MisconceptionRecord]:
        return [MisconceptionRecord(course_id, student_id, r.updated_at, r.misconception_id,
                                    r.status == "resolved")
                for r in self._rows(LearnerMisconception, course_id, student_id)]

    def activity(self, course_id: int, student_id: str) -> Sequence[ActivityRecord]:
        return [ActivityRecord(course_id, student_id, r.created_at, "question")
                for r in self._rows(RequestLog, course_id, student_id)]

    def audit_view(self, course_id: int, student_id: str, viewer_account_id: int) -> bool:
        with Session(self.engine) as db:
            db.add(AuditLog(account_id=viewer_account_id, action="learner.overview.view",
                            target=f"course:{course_id}", details={"student_id": student_id}))
            db.commit()
        return True


# --------------------------------------------------------------------------------------- learning plans
def _plan(row: PlanRow | None) -> LearningPlan | None:
    if row is None:
        return None
    return LearningPlan(row.course_id, row.student_id, tuple(row.focus_kcs), row.goal, row.notes,
                        row.updated_at)


def shown_plan(engine: Engine, course_id: int, student_id: str) -> LearningPlan | None:
    """The plan the student and the instructor may see now (none in mode A, after an opt-out, or from before
    the current consent)."""
    with Session(engine) as db:
        member = _member(db, course_id, student_id)
        if member is None:
            return None
        row = db.exec(select(PlanRow).where(PlanRow.course_id == course_id,
                                            PlanRow.student_id == student_id)).first()
        return visible_learning_plan(_state(member, course_id, student_id), _plan(row))


def save_plan(engine: Engine, course_id: int, student_id: str, *, focus_kcs: list[str], goal: str,
              notes: str, known_kcs: set[str], account_id: int) -> LearningPlan:
    """The instructor sets the plan. Raises VisibilityDenied unless the student is visible (mode B,
    acknowledged, not opted out) and the plan is valid; the change is audited in the same transaction."""
    with Session(engine) as db:
        member = _member(db, course_id, student_id)
        if member is None:
            raise LookupError("not a student of this course")
        plan = LearningPlan(course_id, student_id, tuple(focus_kcs), goal, notes, utcnow())

        def audit(cid: int, sid: str) -> bool:
            db.add(AuditLog(account_id=account_id, action="learner.plan.update", target=f"course:{cid}",
                            details={"student_id": sid, "focus_kcs": list(focus_kcs), "goal": goal}))
            return True

        plan = validate_learning_plan(state=_state(member, course_id, student_id), plan=plan,
                                      known_kcs=known_kcs, authorized_instructor=True, audit_update=audit)
        row = db.exec(select(PlanRow).where(PlanRow.course_id == course_id,
                                            PlanRow.student_id == student_id)).first()
        row = row or PlanRow(course_id=course_id, student_id=student_id, goal=goal)
        row.focus_kcs, row.goal, row.notes, row.updated_at = list(focus_kcs), goal, notes, plan.created_at
        db.add(row)
        db.commit()
        return plan


# ------------------------------------------------------------------------- a student's own deletion
def delete_own_course_data(engine: Engine, learner, course_id: int, student_id: str) -> None:
    """`DELETE .../me/learning-data` (course-structure.md 4.4): the student's learner data, plan and
    conversations in this course; request logs stay for the class statistics without the student.
    Preferences, consent, the membership and other courses are untouched."""
    learner.delete_course_data(student_id)
    with Session(engine) as db:
        db.exec(delete(PlanRow).where(PlanRow.course_id == course_id, PlanRow.student_id == student_id))
        db.exec(delete(SessionTurn).where(SessionTurn.course_id == course_id,
                                          SessionTurn.student_id == student_id))
        db.exec(update(RequestLog).where(RequestLog.course_id == course_id,
                                         RequestLog.student_id == student_id)
                .values(student_id="deleted", session_id="deleted"))
        db.commit()

