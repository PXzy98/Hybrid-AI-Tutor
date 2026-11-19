"""Class statistics (v5 V2): how many students use the tutor, how many questions, which modules, quiz
averages. Counts only, from `request_log` (one row per question, no question text is read here), course
membership and quiz attempts. A count that a group smaller than the minimum group contributed is suppressed
(None), as in the class summary, so no number describes one or two students.
"""
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from statistics import mean

from sqlalchemy import Engine, func
from sqlmodel import Session, col, select

from app.pipeline.steps.generate import LOCAL_CAPABILITY_NOTE
from app.platform.course_scope import GENERAL_TOPIC
from app.storage.models import Course, CourseMember, Module, Quiz, QuizAttempt, RequestLog

WEEKS = 8  # weeks of the per-week counts, the current one included
DELETED = "deleted"  # request_log.student_id after the account was deleted: not a student to count


@dataclass(frozen=True)
class WeekCount:
    week_start: date  # Monday (UTC)
    questions: int | None  # None: fewer than the minimum group asked that week
    students: int | None


@dataclass(frozen=True)
class ModuleCount:
    module_id: int | None  # None: questions about the whole course
    title: str
    questions: int | None  # None: fewer than the minimum group asked about it


@dataclass(frozen=True)
class QuizStat:
    quiz_id: int
    title: str
    attempts: int
    mean_score: float | None  # share of correct answers; None below the minimum group


@dataclass
class CourseStatistics:
    course_id: int
    min_group: int
    students_enrolled: int
    active_students: int  # asked at least one question
    active_students_7d: int
    questions_total: int | None
    questions_7d: int | None
    local_share: float | None  # share of the questions answered by the local model
    weeks: list[WeekCount] = field(default_factory=list)
    modules: list[ModuleCount] = field(default_factory=list)
    quizzes: list[QuizStat] = field(default_factory=list)


@dataclass(frozen=True)
class CourseRow:
    course_id: int
    code: str
    title: str
    status: str
    students_enrolled: int
    active_students_7d: int
    questions_total: int | None
    questions_7d: int | None


@dataclass
class SystemStatistics:
    min_group: int
    courses: list[CourseRow]
    students_enrolled: int
    active_students_7d: int
    questions_total: int | None
    questions_7d: int | None


def _shown(count: int, students: int, min_group: int) -> int | None:
    return count if students >= min_group else None


def _students(rows) -> int:
    return len({sid for sid in rows if sid and sid != DELETED})


def _enrolled(db: Session, course_id: int) -> int:
    return db.exec(select(func.count()).select_from(CourseMember).where(
        CourseMember.course_id == course_id, CourseMember.role == "student",
        CourseMember.status == "active")).one()


def _answered_locally(row) -> bool:
    """`request_log.target` is the routing decision; a question routed to the cloud that fell back to the
    local model (privacy check, no cloud connection, cloud failure) carries the fallback's note in its
    warnings."""
    return row.target == "local" or (row.target == "cloud" and LOCAL_CAPABILITY_NOTE in (row.warnings or []))


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def course_statistics(engine: Engine, course_id: int, min_group: int, *, now: datetime | None = None
                      ) -> CourseStatistics:
    now = now or datetime.now(UTC)
    week7 = now - timedelta(days=7)
    first_week = _monday(now.date()) - timedelta(weeks=WEEKS - 1)
    with Session(engine) as db:
        rows = db.exec(select(RequestLog.student_id, RequestLog.topic, RequestLog.created_at,
                              RequestLog.target, RequestLog.warnings)
                       .where(RequestLog.course_id == course_id)).all()
        modules = db.exec(select(Module).where(Module.course_id == course_id)
                          .order_by(Module.position, Module.id)).all()
        quizzes = db.exec(select(Quiz).where(Quiz.course_id == course_id, Quiz.status != "draft")
                          .order_by(Quiz.id)).all()
        attempts = db.exec(select(QuizAttempt).where(col(QuizAttempt.quiz_id).in_([q.id for q in quizzes])
                                                     )).all() if quizzes else []
        enrolled = _enrolled(db, course_id)

    def at(r) -> datetime:
        return r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=UTC)

    recent = [r for r in rows if at(r) >= week7]
    students, students_7d = _students(r.student_id for r in rows), _students(r.student_id for r in recent)
    answered = [r for r in rows if r.target in ("local", "cloud")]
    out = CourseStatistics(
        course_id=course_id, min_group=min_group, students_enrolled=enrolled,
        active_students=students, active_students_7d=students_7d,
        questions_total=_shown(len(rows), students, min_group),
        questions_7d=_shown(len(recent), students_7d, min_group),
        local_share=(round(sum(_answered_locally(r) for r in answered) / len(answered), 3)
                     if answered and students >= min_group else None))
    for i in range(WEEKS):
        start = first_week + timedelta(weeks=i)
        week = [r for r in rows if _monday(at(r).date()) == start]
        n = _students(r.student_id for r in week)
        out.weeks.append(WeekCount(start, _shown(len(week), n, min_group), n if n >= min_group else None))
    by_topic = {m.code: (m.id, m.title) for m in modules}
    for code, (module_id, title) in [(GENERAL_TOPIC, (None, "")), *by_topic.items()]:
        asked = [r for r in rows if r.topic == code]
        n = _students(r.student_id for r in asked)
        out.modules.append(ModuleCount(module_id, title, _shown(len(asked), n, min_group)))
    for q in quizzes:
        own = [a for a in attempts if a.quiz_id == q.id and a.total]
        score = round(mean(a.score / a.total for a in own), 3) if len(own) >= min_group else None
        out.quizzes.append(QuizStat(q.id, q.title, len(own), score))
    return out


def system_statistics(engine: Engine, min_group: int, *, now: datetime | None = None) -> SystemStatistics:
    """The admin's view: the same counts for every course, and the totals."""
    now = now or datetime.now(UTC)
    week7 = now - timedelta(days=7)
    with Session(engine) as db:
        courses = db.exec(select(Course).order_by(Course.code)).all()
        rows = db.exec(select(RequestLog.course_id, RequestLog.student_id, RequestLog.created_at)).all()
        enrolled = {c.id: _enrolled(db, c.id) for c in courses}

    def recent(r) -> bool:
        created = r.created_at if r.created_at.tzinfo else r.created_at.replace(tzinfo=UTC)
        return created >= week7

    out: list[CourseRow] = []
    for c in courses:
        own = [r for r in rows if r.course_id == c.id]
        last = [r for r in own if recent(r)]
        n, n7 = _students(r.student_id for r in own), _students(r.student_id for r in last)
        out.append(CourseRow(c.id, c.code, c.title, c.status, enrolled[c.id], n7,
                             _shown(len(own), n, min_group), _shown(len(last), n7, min_group)))
    scoped = [r for r in rows if r.course_id is not None]
    last = [r for r in scoped if recent(r)]
    # the active count is per course (a student of two courses is two students: the course is the unit), but
    # whether a total may be shown depends on how many different students asked
    total7 = sum(row.active_students_7d for row in out)
    distinct, distinct7 = _students(r.student_id for r in scoped), _students(r.student_id for r in last)
    return SystemStatistics(min_group, out, sum(enrolled.values()), total7,
                            _shown(len(scoped), distinct, min_group), _shown(len(last), distinct7, min_group))
