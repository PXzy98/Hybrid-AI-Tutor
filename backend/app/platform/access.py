"""Who may act in a course (course-structure.md section 3.2; guide rules 7-9).

Every course-scoped v2 endpoint starts with `require_course_role(...)`. A course the caller cannot see is a
404, never a 403, so course IDs do not leak.

Z1 stand-in: there is no course directory yet, so every course-scoped request is refused. Tests and other
components install a directory on `app.state.course_directory` (see `FakeCourseDirectory`); Z9 installs the
real one.
"""
from dataclasses import dataclass, field
from typing import Annotated, Literal, Protocol

from fastapi import Depends, HTTPException, Request, status

from app.auth.deps import CurrentUser, require_any
from app.core.schemas import CourseRef

CourseRole = Literal["instructor", "student"]
SystemRole = Literal["admin", "instructor"]


@dataclass(frozen=True)
class CourseAccess:
    course: CourseRef
    account_id: int
    role: CourseRole
    student_id: str | None  # set for students only


class CourseDirectory(Protocol):
    def membership(self, account_id: int, course_id: int) -> CourseAccess | None:
        """The caller's active membership in the course, or None (not a member, pending, unknown course)."""


@dataclass
class FakeCourseDirectory:
    """In-memory directory for tests and for building against the interface before Z9."""

    members: dict[tuple[int, int], CourseAccess] = field(default_factory=dict)

    def add(self, access: CourseAccess) -> None:
        self.members[(access.account_id, access.course.id)] = access

    def membership(self, account_id: int, course_id: int) -> CourseAccess | None:
        return self.members.get((account_id, course_id))


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "course not found")


def require_course_role(*roles: CourseRole):
    """FastAPI dependency factory: yields the caller's CourseAccess if his role is one of `roles`."""
    allowed = set(roles)

    def dependency(course_id: int, request: Request,
                   user: Annotated[CurrentUser, Depends(require_any)]) -> CourseAccess:
        directory: CourseDirectory | None = getattr(request.app.state, "course_directory", None)
        access = directory.membership(user.account_id, course_id) if directory else None
        if access is None or access.role not in allowed:
            raise _not_found()
        return access

    return dependency


def require_system_role(*roles: SystemRole):
    """FastAPI dependency factory for system-level endpoints (admin pages, creating courses).

    Until Z9 adds the admin role, only "instructor" can be satisfied; "admin" alone always refuses.
    """
    allowed = set(roles)

    def dependency(user: Annotated[CurrentUser, Depends(require_any)]) -> CurrentUser:
        if user.role not in allowed:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "not allowed")
        return user

    return dependency


class DbCourseDirectory:
    """Course memberships from the database (task Z9): an active member of an active course, with an active
    account. An admin may manage every course (course-structure.md 3.2) and gets the instructor role."""

    def __init__(self, engine) -> None:
        self.engine = engine

    def membership(self, account_id: int, course_id: int) -> CourseAccess | None:
        from sqlmodel import Session, select

        from app.storage.models import Account, Course, CourseMember

        with Session(self.engine) as db:
            account, course = db.get(Account, account_id), db.get(Course, course_id)
            if account is None or not account.active or course is None:
                return None
            ref = CourseRef(id=course.id, code=course.code, title=course.title,
                            course_type=course.course_type)
            if account.role == "admin":
                return CourseAccess(course=ref, account_id=account_id, role="instructor", student_id=None)
            member = db.exec(select(CourseMember).where(CourseMember.course_id == course_id,
                                                        CourseMember.account_id == account_id,
                                                        CourseMember.status == "active")).first()
            if member is None or (course.status != "active" and member.role == "student"):
                return None
            return CourseAccess(course=ref, account_id=account_id, role=member.role,
                                student_id=account.student_id if member.role == "student" else None)
