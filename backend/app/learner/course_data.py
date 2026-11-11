"""One course's learner data as a whole: export and deletion (course-structure.md 3.5 and 4.4).

For the callers that work on a course rather than on one request: the end of term (export, then delete
every student's data of the course) and a student deleting their own data in one course. Preferences and
consent are global and are neither exported nor deleted here. The rows hold IDs, flags and numbers only
(never question text), keyed by the pseudonymous student_id.

These functions do not check who may see a student: the end-of-term export of individual data goes
through `app.learner.instructor_view.export_course_profiles`, which applies the visibility rules.
"""
from collections.abc import Sequence
from datetime import datetime

from pydantic import BaseModel
from sqlalchemy import Engine, delete, func
from sqlmodel import Session, col, select

from app.learner.repository import COURSE_TABLES
from app.storage.models import EvidenceLog, LearnerKcState, LearnerMisconception, LearnerTopicLevel


class KcStateRow(BaseModel):
    kc_id: str
    p_mastery: float
    level: str
    n_obs: int
    last_seen: datetime | None = None


class ModuleLevelRow(BaseModel):
    module: str
    level: str
    updated_at: datetime


class EvidenceRow(BaseModel):
    kc_id: str
    kind: str
    source: str
    item_id: str | None = None
    correct: bool | None = None
    signal: str | None = None
    misconception_id: str | None = None
    weight: float
    created_at: datetime


class MisconceptionRow(BaseModel):
    misconception_id: str
    kc_id: str
    status: str
    evidence_count: int
    updated_at: datetime


class StudentCourseData(BaseModel):
    student_id: str
    kc_states: list[KcStateRow] = []
    module_levels: list[ModuleLevelRow] = []
    evidence: list[EvidenceRow] = []
    misconceptions: list[MisconceptionRow] = []


def course_students(engine: Engine, course_id: int) -> list[str]:
    """student_ids that have any learner data in the course."""
    found: set[str] = set()
    with Session(engine) as db:
        for table in COURSE_TABLES:
            found.update(db.exec(select(table.student_id).where(table.course_id == course_id).distinct()))
    return sorted(found)


def export_course_data(engine: Engine, course_id: int, student_ids: Sequence[str] | None = None,
                       ) -> list[StudentCourseData]:
    """The learner data of the course, one entry per student (all of them, or only `student_ids`)."""
    wanted = course_students(engine, course_id) if student_ids is None else sorted(set(student_ids))
    out = {sid: StudentCourseData(student_id=sid) for sid in wanted}
    if not out:
        return []

    def rows(table):
        stmt = select(table).where(table.course_id == course_id, col(table.student_id).in_(wanted))
        return db.exec(stmt.order_by(col(table.id))).all()

    with Session(engine) as db:
        for r in rows(LearnerKcState):
            out[r.student_id].kc_states.append(KcStateRow(
                kc_id=r.kc_id, p_mastery=r.p_mastery, level=r.level, n_obs=r.n_obs, last_seen=r.last_seen))
        for r in rows(LearnerTopicLevel):
            out[r.student_id].module_levels.append(ModuleLevelRow(
                module=r.topic, level=r.level, updated_at=r.updated_at))
        for r in rows(EvidenceLog):
            out[r.student_id].evidence.append(EvidenceRow(
                kc_id=r.kc_id, kind=r.kind, source=r.source, item_id=r.item_id, correct=r.correct,
                signal=r.signal, misconception_id=r.misconception_id, weight=r.weight,
                created_at=r.created_at))
        for r in rows(LearnerMisconception):
            out[r.student_id].misconceptions.append(MisconceptionRow(
                misconception_id=r.misconception_id, kc_id=r.kc_id, status=r.status,
                evidence_count=r.evidence_count, updated_at=r.updated_at))
    return [out[sid] for sid in wanted]


def delete_course_data(engine: Engine, course_id: int, student_id: str | None = None) -> dict[str, int]:
    """Delete the learner data of the course: every student's (end of term), or one student's.

    Returns the number of deleted rows per table. Other courses, preferences and consent are untouched.
    """
    deleted: dict[str, int] = {}
    with Session(engine) as db:
        for table in COURSE_TABLES:
            where = [table.course_id == course_id]
            if student_id is not None:
                where.append(table.student_id == student_id)
            deleted[table.__tablename__] = db.exec(
                select(func.count()).select_from(table).where(*where)).one()
            db.exec(delete(table).where(*where))
        db.commit()
    return deleted
