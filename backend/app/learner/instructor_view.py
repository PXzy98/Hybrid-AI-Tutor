"""What an instructor may see about one student (task S9; course-structure.md section 4.5).

`profile_for_instructor` checks the course's visibility mode, the student's opt-out and `visible_since`
itself, so no endpoint can forget a condition. Z1 stand-in: it refuses every request (as in visibility
mode A) until S9 implements it.
"""
from datetime import datetime

from pydantic import BaseModel

from app.core.schemas import Level
from app.platform.access import CourseAccess


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


def profile_for_instructor(viewer: CourseAccess, student_id: str) -> InstructorProfileView:
    if viewer.role != "instructor":
        raise NotVisible("instructors only")
    raise NotVisible("individual overviews are not available yet")
