"""Class statistics (v5 V2): how many students use the tutor, how many questions, which modules, quiz
averages. Counts only, from `request_log` (one row per question, no question text is read here), course
membership and quiz attempts. Every question and attempt of the course counts, also of students who left
it: the counts must not change when an instructor removes a member, or two snapshots would give that student's
activity by subtraction (so the active students may exceed the students enrolled now).

Suppression (so that no number describes one or a few students):
- the minimum group is `max(MIN_GROUP, learner.class_summary_min_group)`, as for the class insights;
- a count that between 1 and `min_group - 1` students contributed is None; a count of 0 describes nobody and
  is shown as 0;
- complementary suppression, applied jointly: the released question counts form a system of sums (the total
  is the 7-day count plus the older ones, the weeks plus the questions before the window, the module rows plus
  the other topics; for the admin the system total is the sum of the course totals, and so on). A cell that is
  hidden or not shown is unknown; when exactly one cell of a sum is unknown and it is small (or hidden), a
  shown cell of that sum is hidden as well, and this repeats over all sums until nothing changes, because one
  cell belongs to several sums;
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


def _suppress(cells: dict[str, Tally], virtual: set[str], sums: list[tuple[str, list[str]]], group: int
              ) -> set[str]:
    """Joint complementary suppression. `cells` are all counts that take part, `virtual` the keys that are
    never displayed (rows older than the window, other topics, ...), `sums` the equations `total = parts`.
    A cell is unknown to the viewer when hidden, or virtual and not empty; it is sensitive when between 1 and
    `group - 1` students contributed. Until nothing changes: in a sum with exactly one unknown cell that is
    sensitive or hidden, hide one more displayed cell of it (the smallest non-empty part, else the total).
    Returns the keys of the hidden cells."""
    hidden = {k for k, t in cells.items() if k not in virtual and _small(t, group)}

    def unknown(key: str) -> bool:
        return key in hidden or (key in virtual and cells[key].questions > 0)

    def shown(key: str) -> bool:
        return key not in virtual and key not in hidden and cells[key].questions > 0

    changed = True
    while changed:
        changed = False
        for total, parts in sums:
            gaps = [k for k in (total, *parts) if unknown(k)]
            if len(gaps) != 1 or not (gaps[0] in hidden or _small(cells[gaps[0]], group)):
                continue
            candidates = [k for k in parts if shown(k)]
            if candidates:
                hidden.add(min(candidates, key=lambda k: cells[k].questions))
                changed = True
            elif shown(total):
                hidden.add(total)
                changed = True
    return hidden


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
    local_questions = total[9] + sum(LOCAL_CAPABILITY_NOTE in (w or []) for w in fallbacks)
    starts = [first_week + timedelta(weeks=i) for i in range(WEEKS)]
    weeks = [by_week.get(d, Tally()) for d in starts]
    listed = [(None, "", GENERAL_TOPIC), *[(m.id, m.title, m.code) for m in modules]]
    rows = [by_topic.get(code, Tally()) for _, _, code in listed]
    cells = {"total": everything, "7d": recent, "older": older, "before": before, "other": other_topics,
             **{f"w{i}": t for i, t in enumerate(weeks)}, **{f"m{i}": t for i, t in enumerate(rows)}}
    week_keys, module_keys = [f"w{i}" for i in range(WEEKS)], [f"m{i}" for i in range(len(rows))]
    hidden = _suppress(cells, {"older", "before", "other"}, [
        ("total", ["7d", "older"]), ("total", [*week_keys, "before"]), ("total", [*module_keys, "other"])],
        group)

    def released(key: str) -> int | None:
        return None if key in hidden else cells[key].questions

    out = CourseStatistics(
        course_id=course_id, min_group=group, students_enrolled=enrolled,
        active_students=_count(everything.students, everything.students, group),
        active_students_7d=_count(recent.students, recent.students, group),
        questions_total=released("total"), questions_7d=released("7d"),
        local_share=(round(local_questions / total[8], 3) if total[8] and everything.students >= group
                     else None))
    for i, (start, t) in enumerate(zip(starts, weeks, strict=True)):
        gone = f"w{i}" in hidden
        out.weeks.append(WeekCount(start, released(f"w{i}"), None if gone else _count(t.students, t.students,
                                                                                       group)))
    for i, (module_id, title, _) in enumerate(listed):
        out.modules.append(ModuleCount(module_id, title, released(f"m{i}")))
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
    cells = {"T": everything, "R": recent, "O": older}
    for i, c in enumerate(courses):
        cells.update({f"t{i}": totals[i], f"r{i}": recents[i], f"o{i}": per_course.get(c.id, empty)[2]})
    ids = range(len(courses))
    hidden = _suppress(cells, {"O", *(f"o{i}" for i in ids)}, [
        ("T", ["R", "O"]), ("T", [f"t{i}" for i in ids]), ("R", [f"r{i}" for i in ids]),
        *[(f"t{i}", [f"r{i}", f"o{i}"]) for i in ids]], group)

    def released(key: str) -> int | None:
        return None if key in hidden else cells[key].questions

    shown_total, shown_recent = [released(f"t{i}") for i in ids], [released(f"r{i}") for i in ids]
    total_q, recent_q = released("T"), released("R")
    rows = [CourseRow(c.id, c.code, c.title, c.status, enrolled.get(c.id, 0),
                      _count(recents[i].students, recents[i].students, group), shown_total[i],
                      shown_recent[i]) for i, c in enumerate(courses)]
    return SystemStatistics(group, rows, sum(enrolled.get(c.id, 0) for c in courses),
                            _count(recent.students, recent.students, group), total_q, recent_q)
