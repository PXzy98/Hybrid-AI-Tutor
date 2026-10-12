"""Delete everything that belongs to a student (design §8.3).

Generic on purpose: every table with a `student_id` column is purged, so tables added later (learner
state, evidence, consent, ...) are covered without touching this file. `request_log` is the one
exception: its rows are kept for class statistics, with the student_id replaced by "deleted".
"""
from sqlalchemy import delete, update
from sqlmodel import Session, SQLModel

ANONYMIZE = {"request_log"}
DELETED = "deleted"


def purge_student(db: Session, student_id: str) -> dict[str, int]:
    """Purge or anonymize all rows of `student_id`. Returns affected rows per table. Caller commits."""
    counts: dict[str, int] = {}
    # reverse dependency order: children before the tables they reference
    for table in reversed(SQLModel.metadata.sorted_tables):
        if "student_id" not in table.c:
            continue
        where = table.c.student_id == student_id
        stmt = (update(table).where(where).values(student_id=DELETED) if table.name in ANONYMIZE
                else delete(table).where(where))
        counts[table.name] = db.exec(stmt).rowcount
    return counts
