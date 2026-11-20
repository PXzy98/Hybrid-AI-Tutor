"""Class statistics (v5 V2): how many students use the tutor, how many questions, which modules, quiz
averages. Counts only, from `request_log` (one row per question, no question text is read here), course
membership and quiz attempts. Every question and attempt of the course counts, also of students who left
it: the counts must not change when an instructor removes a member, or two snapshots would give that student's
activity by subtraction (so the active students may exceed the students enrolled now).

Suppression (so that no number describes one or a few students):
- the minimum group is `max(MIN_GROUP, learner.class_summary_min_group)`, as for the class insights;
- a count that between 1 and `min_group - 1` students contributed is None; a count of 0 describes nobody and
  is shown as 0;
- complementary suppression: a total shown next to a breakdown (weeks, modules, courses, recent versus older)
  must not let a hidden row be derived by subtraction, so when exactly one small part would be unknown, the
  smallest shown part (or the total) is hidden as well;
- quiz attempts below the minimum group are hidden and the mean score is rounded to tenths (0.1 steps), so two
  snapshots of the averages do not give one student's score.
"""
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta

from sqlalchemy import Engine, Float, String, cast, distinct, func
from sqlmodel import Session, col, select

from app.pipeline.steps.generate import LOCAL_CAPABILITY_NOTE
from app.platform.course_scope import GENERAL_TOPIC
from app.storage.models import Course, CourseMember, Module, Quiz, QuizAttempt, RequestLog

MIN_GROUP = 5  # the core's lower bound; the setting `learner.class_summary_min_group` may raise it
WEEKS = 8  # weeks of the per-week counts, the current one included
SCORE_STEP = 0.1  # quiz mean scores are rounded to this step


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
    attempts: int | None  # None below the minimum group
    mean_score: float | None  # share of correct answers in steps of 0.1; None below the minimum group


@dataclass
class CourseStatistics:
    course_id: int
    min_group: int  # the minimum group in effect (at least MIN_GROUP)
    students_enrolled: int
    active_students: int | None  # students who asked at least one question (also those who left since)
    active_students_7d: int | None
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
    active_students_7d: int | None
    questions_total: int | None
    questions_7d: int | None


@dataclass
class SystemStatistics:
    min_group: int
    courses: list[CourseRow]
    students_enrolled: int
    active_students_7d: int | None  # different students, whatever the number of their courses
    questions_total: int | None
    questions_7d: int | None


@dataclass(frozen=True)
class Tally:
    """Rows of one group (a course, a module, a week): how many and by how many different students."""
    questions: int = 0
    students: int = 0


def effective_group(min_group: int) -> int:
    return max(MIN_GROUP, min_group)


def _small(t: Tally, group: int) -> bool:
    return 0 < t.students < group


def _count(value: int, students: int, group: int) -> int | None:
    """0 describes nobody and is shown; a count that fewer than `group` (but some) students contributed is
    hidden."""
    return None if 0 < students < group else value


def _complement(total_shown: bool, parts: list[Tally], group: int, *, shown: list[bool] | None = None,
                virtual: int = 0, hide_parts: bool = True) -> tuple[bool, set[int]]:
    """Complementary suppression of a total and its breakdown. `parts` are the displayed rows, `virtual` the
    number of trailing entries of `parts` that are not displayed (rows older than the window, other topics).
    When the total is shown and exactly one part is unknown to the viewer (hidden, or not displayed but not
    empty) and that part is small, the viewer could subtract: hide the smallest shown row as well (or the
    total, when there is none or `hide_parts` is False). Returns (hide the total, indexes of rows to hide)."""
    n = len(parts) - virtual
    hidden = {i for i in range(n) if _small(parts[i], group)}
    unknown = hidden | {i for i in range(n, len(parts)) if parts[i].questions > 0}
    if not total_shown or len(unknown) != 1 or not _small(parts[next(iter(unknown))], group):
        return False, set()
    candidates = [i for i in range(n) if i not in hidden and parts[i].questions > 0] if hide_parts else []
    if not candidates:
        return True, set()
    return False, {min(candidates, key=lambda i: (parts[i].questions, i))}


def _member_rows(*columns):
    """`request_log` rows, whoever is a member now: a stable cohort, so removing a member changes no count."""
    return select(*columns).select_from(RequestLog)


def _tally(*where) -> tuple:
    """Two aggregate columns: the number of rows and of different students, over the rows that satisfy
    `where` (all rows without any)."""
    rows, students = func.count(), func.count(distinct(RequestLog.student_id))
    if where:
        return rows.filter(*where), students.filter(*where)
    return rows, students


def _monday(day: date) -> date:
    return day - timedelta(days=day.weekday())


def _answered_locally(target: str | None, warnings) -> bool:
    """`request_log.target` is the routing decision; a question routed to the cloud that fell back to the
    local model (privacy check, no cloud connection, cloud failure) carries the fallback's note in its
    warnings."""
    return target == "local" or (target == "cloud" and LOCAL_CAPABILITY_NOTE in (warnings or []))


def _utc(day: date) -> datetime:
    return datetime(day.year, day.month, day.day, tzinfo=UTC)


def _week_bucket():
    """Monday (UTC) of the week of a row."""
    return func.date_trunc("week", func.timezone("UTC", RequestLog.created_at))


def _enrolled(db: Session, course_id: int) -> int:
    return db.exec(select(func.count()).select_from(CourseMember).where(
        CourseMember.course_id == course_id, CourseMember.role == "student",
        CourseMember.status == "active")).one()


def course_statistics(engine: Engine, course_id: int, min_group: int, *, now: datetime | None = None
                      ) -> CourseStatistics:
    group = effective_group(min_group)
    now = now or datetime.now(UTC)
    week7 = now - timedelta(days=7)
    first_week = _monday(now.date()) - timedelta(weeks=WEEKS - 1)
    window = _utc(first_week)
    here = RequestLog.course_id == course_id
    with Session(engine) as db:
        t_all = _tally()
        t_new, t_old = _tally(RequestLog.created_at >= week7), _tally(RequestLog.created_at < week7)
        t_before = _tally(RequestLog.created_at < window)
        answered = func.count().filter(col(RequestLog.target).in_(["local", "cloud"]))
        local = func.count().filter(RequestLog.target == "local")
        total = db.exec(_member_rows(*t_all, *t_new, *t_old, *t_before, answered, local).where(here)).one()
        # cloud questions that fell back to the local model carry the note in their warnings
        fallbacks = db.exec(_member_rows(RequestLog.warnings).where(
            here, RequestLog.target == "cloud",
            cast(RequestLog.warnings, String).like(f"%{LOCAL_CAPABILITY_NOTE[:30]}%"))).all()
        by_topic = {topic: Tally(n, s) for topic, n, s in db.exec(
            _member_rows(RequestLog.topic, *t_all).where(here).group_by(RequestLog.topic))}
        week = _week_bucket()
        by_week = {w.date(): Tally(n, s) for w, n, s in db.exec(
            _member_rows(week, *t_all).where(here, RequestLog.created_at >= window).group_by(week))}
        modules = db.exec(select(Module).where(Module.course_id == course_id)
                          .order_by(Module.position, Module.id)).all()
        codes = [GENERAL_TOPIC, *(m.code for m in modules)]
        other_topics = Tally(*db.exec(_member_rows(*t_all).where(here, col(RequestLog.topic).not_in(codes))
                                      ).one())
        quizzes = db.exec(select(Quiz).where(Quiz.course_id == course_id, Quiz.status != "draft")
                          .order_by(Quiz.id)).all()
        scored = (func.count(), func.avg(cast(QuizAttempt.score, Float) / func.nullif(QuizAttempt.total, 0)))
        by_quiz = {q: (n, avg) for q, n, avg in db.exec(
            select(QuizAttempt.quiz_id, *scored).select_from(QuizAttempt)
            .where(col(QuizAttempt.quiz_id).in_([q.id for q in quizzes]), QuizAttempt.total > 0)
            .group_by(QuizAttempt.quiz_id))} if quizzes else {}
        enrolled = _enrolled(db, course_id)
    everything, recent = Tally(total[0], total[1]), Tally(total[2], total[3])
    older, before = Tally(total[4], total[5]), Tally(total[6], total[7])
    questions_total, questions_7d = (_count(t.questions, t.students, group) for t in (everything, recent))
    # the total next to the recent count: the difference is the older questions, which may be few students
    hide_total, _ = _complement(questions_total is not None, [recent, older], group, virtual=1,
                                hide_parts=False)
    if hide_total:
        questions_total = None
    local_questions = total[9] + sum(LOCAL_CAPABILITY_NOTE in (w or []) for w in fallbacks)
    out = CourseStatistics(
        course_id=course_id, min_group=group, students_enrolled=enrolled,
        active_students=_count(everything.students, everything.students, group),
        active_students_7d=_count(recent.students, recent.students, group),
        questions_total=questions_total, questions_7d=questions_7d,
        local_share=(round(local_questions / total[8], 3) if total[8] and everything.students >= group
                     else None))
    starts = [first_week + timedelta(weeks=i) for i in range(WEEKS)]
    weeks = [by_week.get(d, Tally()) for d in starts]
    hide_total, hidden_weeks = _complement(out.questions_total is not None, [*weeks, before], group,
                                           virtual=1)
    if hide_total:
        out.questions_total = None
    for i, (start, t) in enumerate(zip(starts, weeks, strict=True)):
        gone = i in hidden_weeks
        out.weeks.append(WeekCount(start, None if gone else _count(t.questions, t.students, group),
                                   None if gone else _count(t.students, t.students, group)))
    listed = [(None, "", GENERAL_TOPIC), *[(m.id, m.title, m.code) for m in modules]]
    rows = [by_topic.get(code, Tally()) for _, _, code in listed]
    other = other_topics
    hide_total, hidden_rows = _complement(out.questions_total is not None, [*rows, other], group, virtual=1)
    if hide_total:
        out.questions_total = None
    for i, ((module_id, title, _), t) in enumerate(zip(listed, rows, strict=True)):
        out.modules.append(ModuleCount(module_id, title, None if i in hidden_rows
                                       else _count(t.questions, t.students, group)))
    for q in quizzes:
        n, avg = by_quiz.get(q.id, (0, None))
        shown = n == 0 or n >= group
        out.quizzes.append(QuizStat(q.id, q.title, n if shown else None,
                                    round(round(float(avg) / SCORE_STEP) * SCORE_STEP, 1)
                                    if avg is not None and n >= group else None))
    return out


def system_statistics(engine: Engine, min_group: int, *, now: datetime | None = None) -> SystemStatistics:
    """The admin's view: the same counts for every course, and the totals."""
    group = effective_group(min_group)
    now = now or datetime.now(UTC)
    week7 = now - timedelta(days=7)
    t_all = _tally()
    t_new, t_old = _tally(RequestLog.created_at >= week7), _tally(RequestLog.created_at < week7)
    with Session(engine) as db:
        courses = db.exec(select(Course).order_by(Course.code)).all()
        per_course = {r[0]: (Tally(*r[1:3]), Tally(*r[3:5]), Tally(*r[5:7])) for r in db.exec(
            _member_rows(RequestLog.course_id, *t_all, *t_new, *t_old).group_by(RequestLog.course_id))}
        overall = db.exec(_member_rows(*t_all, *t_new, *t_old)).one()
        enrolled = dict(db.exec(select(CourseMember.course_id, func.count()).where(
            CourseMember.role == "student", CourseMember.status == "active")
            .group_by(CourseMember.course_id)).all())
    empty = (Tally(), Tally(), Tally())
    totals = [per_course.get(c.id, empty)[0] for c in courses]
    recents = [per_course.get(c.id, empty)[1] for c in courses]
    everything, recent, older = Tally(overall[0], overall[1]), Tally(overall[2], overall[3]), Tally(
        overall[4], overall[5])
    total_q, recent_q = (_count(t.questions, t.students, group) for t in (everything, recent))
    # the same rule as for a course, per course row and for the system rows
    shown_total = [_count(t.questions, t.students, group) for t in totals]
    shown_recent = [_count(t.questions, t.students, group) for t in recents]
    for i, c in enumerate(courses):
        _, new, old = per_course.get(c.id, empty)
        if _complement(shown_total[i] is not None and shown_recent[i] is not None, [new, old], group,
                       virtual=1, hide_parts=False)[0]:
            shown_total[i] = None
    if _complement(total_q is not None, [recent, older], group, virtual=1, hide_parts=False)[0]:
        total_q = None
    hide_total, hidden = _complement(total_q is not None, totals, group)
    total_q = None if hide_total else total_q
    for i in hidden:
        shown_total[i] = None
    hide_total, hidden = _complement(recent_q is not None, recents, group)
    recent_q = None if hide_total else recent_q
    for i in hidden:
        shown_recent[i] = None
    rows = [CourseRow(c.id, c.code, c.title, c.status, enrolled.get(c.id, 0),
                      _count(recents[i].students, recents[i].students, group), shown_total[i],
                      shown_recent[i]) for i, c in enumerate(courses)]
    return SystemStatistics(group, rows, sum(enrolled.get(c.id, 0) for c in courses),
                            _count(recent.students, recent.students, group), total_q, recent_q)
