"""End of term (course-structure.md 3.5; task Z9): export, then delete the course's student data.

The export is a ZIP in the data volume (`courses/<course_id>/exports/<export_id>.zip`), kept for
`limits.courses.export_retention_hours`:
- `class_summary.json`: the aggregates of every module (small groups suppressed, as on the dashboard);
- `students.json`: only in visibility mode B, the individual overviews the instructor may see, built by the
  same function as the overview endpoint (`export_course_profiles`), so the two can never differ.

Then, for that course: student memberships, learner state, evidence, misconceptions, plans, conversations,
request logs and usage counters are deleted. The course, its content, materials, settings and instructors
stay; accounts stay. Nothing here reads or writes question text.
"""
import io
import json
import re
import secrets
import zipfile
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path

from sqlalchemy import Engine, delete
from sqlmodel import Session

from app.admin.summary import class_summary
from app.learner import course_views
from app.learner.course_data import delete_course_data
from app.learner.instructor_view import export_course_profiles
from app.platform.access import CourseAccess
from app.platform.course_scope import CourseScope
from app.storage.models import (
    AuditLog,
    CourseInvite,
    CourseMember,
    LearningPlan,
    RequestLog,
    SessionTurn,
    UsageCounter,
    utcnow,
)

EXPORT_ID = re.compile(r"^[0-9]{8}T[0-9]{6}Z-[0-9a-f]{12}$")


@dataclass(frozen=True)
class TermEnded:
    export_id: str
    expires_at: datetime
    students_removed: int
    students_exported: int  # individual overviews in the export (0 in visibility mode A)
    deleted: dict[str, int]


def exports_dir(data_root: Path, course_id: int) -> Path:
    return data_root / "courses" / str(course_id) / "exports"


def _build_export(engine: Engine, scope: CourseScope, access: CourseAccess, min_group: int
                  ) -> tuple[bytes, int]:
    students = course_views.course_student_ids(engine, access.course.id)
    summaries = [class_summary(engine, scope.learner, scope.content, code, min_group,
                               members=students).model_dump(mode="json")
                 for code in scope.content.topics()]
    store = course_views.DbLearnerViewStore(engine)
    profiles = [p.model_dump(mode="json") for p in export_course_profiles(access, students, store=store)]
    meta = {"course_code": access.course.code, "course_title": access.course.title,
            "exported_at": utcnow().isoformat(), "students": len(students),
            "individual_overviews": len(profiles)}
    buffer = io.BytesIO()
    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("export.json", json.dumps(meta, indent=2))
        archive.writestr("class_summary.json", json.dumps(summaries, indent=2))
        if profiles:
            archive.writestr("students.json", json.dumps(profiles, indent=2))
    return buffer.getvalue(), len(profiles)


def end_term(engine: Engine, data_root: Path, scope: CourseScope, access: CourseAccess, *, min_group: int,
             retention_hours: int) -> TermEnded:
    """Build the export, write it, then delete the student data of the course. If the export cannot be
    written, nothing is deleted."""
    course_id = access.course.id
    purge_expired(data_root, course_id, retention_hours)
    data, exported = _build_export(engine, scope, access, min_group)
    now = utcnow()
    export_id = f"{now:%Y%m%dT%H%M%SZ}-{secrets.token_hex(6)}"
    folder = exports_dir(data_root, course_id)
    folder.mkdir(parents=True, exist_ok=True)
    (folder / f"{export_id}.zip").write_bytes(data)

    deleted = delete_course_data(engine, course_id)  # learner state, levels, evidence, misconceptions
    with Session(engine) as db:
        for table in (LearningPlan, SessionTurn, RequestLog, UsageCounter):
            deleted[table.__tablename__] = db.exec(delete(table).where(table.course_id == course_id)).rowcount
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
