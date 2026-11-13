"""End of term (course-structure.md 3.5; task Z9): export, then delete the course's student data.

The export is a ZIP in the data volume (`courses/<course_id>/exports/<export_id>.zip`), kept for
`limits.courses.export_retention_hours`:
- `class_summary.json`: the aggregates of every module (small groups suppressed, as on the dashboard);
- `students.json`: only in visibility mode B, the individual overviews the instructor may see, built by the
  same function as the overview endpoint (`export_course_profiles`), so the two can never differ;
- `quizzes.json`: each quiz's results as the results endpoint gives them (aggregates; individual results
  only of visible students);
- `survey.json`: the end-of-term survey averages (none below the minimum group).

Then, for that course: student memberships, learner state, evidence, misconceptions, plans, conversations,
request logs, usage counters, quiz attempts and the survey (window, answers, who answered) are deleted;
published quizzes are closed. The course, its content, materials, settings and instructors
stay; accounts stay. Nothing here reads or writes question text.

`maintenance()` runs in the worker: it deletes expired exports of every course (also courses nobody opens
again), and for a day after a term ended it deletes rows that requests still running at the end of term
wrote for students who are no longer members.
"""
import io
import json
import re
import secrets
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import Engine, delete, update
from sqlmodel import Session, col, select

from app.admin.summary import class_summary
from app.learner import course_views
from app.learner.course_data import delete_course_data
from app.learner.instructor_view import export_course_profiles
from app.learner.repository import COURSE_TABLES
from app.platform.access import CourseAccess
from app.platform.course_scope import CourseScope
from app.storage.models import (
    Account,
    AuditLog,
    CourseInvite,
    CourseMember,
    CourseSurveyResponse,
    CourseSurveySubmission,
    LearningPlan,
    Quiz,
    QuizAttempt,
    RequestLog,
    SessionTurn,
    SurveyWindow,
    UsageCounter,
    utcnow,
)

EXPORT_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")
STUDENT_TABLES = (*COURSE_TABLES, LearningPlan, SessionTurn, RequestLog, UsageCounter, QuizAttempt,
                  CourseSurveySubmission)
SWEEP_HOURS = 24  # how long after an end of term late writes are looked for (far above any request timeout)
DELETED = "deleted"  # student_id of request logs kept after a student deleted their own data


@dataclass(frozen=True)
class TermEnded:
    export_id: str
    expires_at: datetime
    students_removed: int
    students_exported: int  # individual overviews in the export (0 in visibility mode A)
    deleted: dict[str, int]


def exports_dir(data_root: Path, course_id: int) -> Path:
    return data_root / "courses" / str(course_id) / "exports"


def _build_export(engine: Engine, scope: CourseScope, access: CourseAccess, min_group: int, settings
                  ) -> tuple[bytes, int]:
    students = course_views.course_student_ids(engine, access.course.id)
    summaries = [class_summary(engine, scope.learner, scope.content, code, min_group,
                               members=students).model_dump(mode="json")
                 for code in scope.content.topics()]
    store = course_views.DbLearnerViewStore(engine, settings, scope.content)
    profiles = [p.model_dump(mode="json") for p in export_course_profiles(access, students, store=store)]
    from app.api.v2.survey import survey_results
    from app.learner.quizzes import quiz_results

    with Session(engine) as db:
        quizzes = db.exec(select(Quiz).where(Quiz.course_id == access.course.id).order_by(col(Quiz.id))).all()
    quiz_out = [{"title": q.title, "kind": q.kind, **quiz_results(
        engine, q, viewer_account_id=access.account_id, min_group=min_group).model_dump(mode="json")}
        for q in quizzes]
    meta = {"course_code": access.course.code, "course_title": access.course.title,
            "exported_at": utcnow().isoformat(), "students": len(students),
            "individual_overviews": len(profiles)}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("export.json", json.dumps(meta, indent=2))
        archive.writestr("class_summary.json", json.dumps(summaries, indent=2))
        if profiles:
            archive.writestr("students.json", json.dumps(profiles, indent=2))
        archive.writestr("quizzes.json", json.dumps(quiz_out, indent=2))
        archive.writestr("survey.json", survey_results(engine, access.course.id).model_dump_json(indent=2))
    return buffer.getvalue(), len(profiles)


def end_term(engine: Engine, data_root: Path, scope: CourseScope, access: CourseAccess, *, min_group: int,
             retention_hours: int, settings) -> TermEnded:
    """Build the export, write it, then delete the student data of the course. If the export cannot be
    written, nothing is deleted."""
    course_id = access.course.id
    purge_expired(data_root, course_id, retention_hours)
    data, exported = _build_export(engine, scope, access, min_group, settings)
    now = utcnow()
    export_id = f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(6)}"
    folder = exports_dir(data_root, course_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{export_id}.zip").write_bytes(data)

    deleted = delete_course_data(engine, course_id)  # learner state, levels, evidence, misconceptions
    with Session(engine) as db:
        # the survey window first: its row lock orders this against answers in flight (api/v2/survey.py)
        for table in (SurveyWindow, LearningPlan, SessionTurn, RequestLog, UsageCounter, QuizAttempt,
                      CourseSurveyResponse, CourseSurveySubmission):
            deleted[table.__tablename__] = db.exec(delete(table).where(table.course_id == course_id)).rowcount
        db.exec(update(Quiz).where(Quiz.course_id == course_id, Quiz.status == "published")
                .values(status="closed"))
        removed = db.exec(delete(CourseMember).where(CourseMember.course_id == course_id,
                                                     CourseMember.role == "student")).rowcount
        db.exec(delete(CourseInvite).where(CourseInvite.course_id == course_id))  # the old code is void
        db.add(AuditLog(account_id=access.account_id, action="course.end_term", target=f"course:{course_id}",
                        details={"export_id": export_id, "students_removed": removed,
                                 "students_exported": exported, "deleted": deleted}))
        db.commit()
    return TermEnded(export_id, now + timedelta(hours=retention_hours), removed, exported, deleted)


def purge_expired(data_root: Path, course_id: int, retention_hours: int) -> None:
    """Delete the course's exports that are older than the retention time."""
    folder = exports_dir(data_root, course_id)
    if not folder.is_dir():
        return
    limit = utcnow().timestamp() - retention_hours * 3600
    for path in folder.glob("*.zip"):
        if path.stat().st_mtime < limit:
            path.unlink(missing_ok=True)


def export_file(data_root: Path, course_id: int, export_id: str, retention_hours: int) -> Path | None:
    """The export's file, or None when the ID is unknown or the export expired."""
    if not EXPORT_ID.fullmatch(export_id):  # also keeps the ID from naming any other path
        return None
    purge_expired(data_root, course_id, retention_hours)
    path = exports_dir(data_root, course_id) / f"{export_id}.zip"
    return path if path.is_file() else None


def purge_all_expired(data_root: Path, retention_hours: int) -> None:
    """Expired exports of every course."""
    for folder in (data_root / "courses").glob("*/exports"):
        if folder.parent.name.isdigit():
            purge_expired(data_root, int(folder.parent.name), retention_hours)


def sweep_removed_students(engine: Engine, course_id: int) -> int:
    """Delete the course's rows of students who are not active members: a request that was waiting on a
    model when the term ended writes its log, turns, usage and learner updates afterwards. Returns the
    number of deleted rows."""
    members = (select(Account.student_id).join(CourseMember, CourseMember.account_id == Account.id)
               .where(CourseMember.course_id == course_id, CourseMember.status == "active",
                      col(Account.student_id).is_not(None)))
    removed = 0
    with Session(engine) as db:
        for table in STUDENT_TABLES:
            removed += db.exec(delete(table).where(table.course_id == course_id,
                                                   col(table.student_id).not_in(members),
                                                   table.student_id != DELETED)).rowcount
        db.commit()
    return removed


def maintenance(engine: Engine, data_root: Path, retention_hours: int) -> None:
    """Run by the worker every few minutes."""
    purge_all_expired(data_root, retention_hours)
    since = utcnow() - timedelta(hours=SWEEP_HOURS)
    with Session(engine) as db:
        targets = db.exec(select(AuditLog.target).where(AuditLog.action == "course.end_term",
                                                        AuditLog.created_at >= since).distinct()).all()
    for target in targets:
        if target and target.startswith("course:") and target[7:].isdigit():
            sweep_removed_students(engine, int(target[7:]))
