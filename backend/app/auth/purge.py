"""Delete everything that belongs to a student (design §8.3).

Generic on purpose: every table with a `student_id` column is purged, so tables added later (learner
state, evidence, consent, ...) are covered without touching this file. `request_log` is the one
exception: its rows are kept for class statistics, with the student_id replaced by "deleted". The audit
log and the quizzes' `assigned_to` lists hold the student_id in JSON, so they are scrubbed separately.
"""
from sqlalchemy import delete, update
from sqlmodel import Session, SQLModel, select

from app.storage.models import AuditLog, Quiz

ANONYMIZE = {"request_log"}
DELETED = "deleted"
AUDIT_PERSONAL = ("student_id", "focus_kcs", "goal")  # audit details that identify or describe a student


def _scrub_json(db: Session, student_id: str, account_id: int | None, actor_id: int | None) -> int:
    """Remove the student from JSON columns: quiz assignments and audit rows (the rows stay, anonymized)."""
    touched = 0
    for quiz in db.exec(select(Quiz).where(Quiz.assigned_to.is_not(None))).all():
        if student_id in quiz.assigned_to:
            quiz.assigned_to = [s for s in quiz.assigned_to if s != student_id]  # [] stays "nobody"
            db.add(quiz)
            touched += 1
    for row in db.exec(select(AuditLog)).all():
        details = row.details or {}
        about = details.get("student_id") == student_id
        own = account_id is not None and row.account_id == account_id
        if not (about or own):
            continue
        if about:
            row.details = {k: v for k, v in details.items() if k not in AUDIT_PERSONAL}
        if own:
            row.account_id = None
        db.add(row)
        touched += 1
    return touched


def purge_student(db: Session, student_id: str, account_id: int | None = None,
                  actor_id: int | None = None) -> dict[str, int]:
    """Purge or anonymize all rows of `student_id` (and the audit rows of its `account_id`). With `actor_id`
    the deletion is audited in the same transaction. Returns affected rows per table. Caller commits."""
    counts: dict[str, int] = {}
    # reverse dependency order: children before the tables they reference
    for table in reversed(SQLModel.metadata.sorted_tables):
        if "student_id" not in table.c:
            continue
        where = table.c.student_id == student_id
        stmt = (update(table).where(where).values(student_id=DELETED) if table.name in ANONYMIZE
                else delete(table).where(where))
        counts[table.name] = db.exec(stmt).rowcount
    counts["audit_log"] = _scrub_json(db, student_id, account_id, actor_id)
    if actor_id is not None:
        db.add(AuditLog(account_id=actor_id, action="admin.student.delete", target=f"account:{account_id}",
                        details={"rows": sum(counts.values())}))
    return counts
