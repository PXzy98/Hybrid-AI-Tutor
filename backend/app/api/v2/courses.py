"""Courses, members and invitation codes (api-v2.md 3.3; course-structure.md 3.2 and 3.3; task Z9).

Course-scoped routes start with `require_course_role`: a course the caller cannot see is a 404. Students
may read the course itself; everything else here is for the course's instructors (and admins).
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, File, Request, UploadFile
from pydantic import BaseModel, Field

from app.auth.deps import AnyUser, CurrentUser
from app.platform.access import CourseAccess, require_course_role, require_system_role
from app.platform.courses import CourseError

router = APIRouter(tags=["courses"])
Creator = Annotated[CurrentUser, Depends(require_system_role("admin", "instructor"))]
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
CourseMemberAccess = Annotated[CourseAccess, Depends(require_course_role("instructor", "student"))]
# a privacy profile name (app/privacy/profiles/*.yaml, task Z7): checked by the service, not by the schema,
# so a new profile file is a new course type without an API change
CourseTypeName = Annotated[str, Field(min_length=1, max_length=64, examples=["medical_science", "ece"])]


class CourseOut(BaseModel):
    id: int
    code: str
    title: str
    term_label: str
    course_type: CourseTypeName
    visibility_mode: Literal["A", "B"]
    status: Literal["active", "archived"]
    my_role: Literal["instructor", "student"] | None


class CourseIn(BaseModel):
    code: str = Field(min_length=1, max_length=32)
    title: str = Field(min_length=1, max_length=200)
    course_type: CourseTypeName
    term_label: str = Field("", max_length=64)


class CoursePatch(BaseModel):
    code: str | None = Field(None, min_length=1, max_length=32)
    title: str | None = Field(None, min_length=1, max_length=200)
    term_label: str | None = Field(None, max_length=64)


class MemberOut(BaseModel):
    id: int
    role: Literal["instructor", "student"]
    status: Literal["pending", "active"]
    account_id: int | None
    username: str | None
    display_name: str | None
    email: str | None
    created_at: datetime


class RejectedRow(BaseModel):
    row: int
    email: str
    reason: str


class ImportReportOut(BaseModel):
    added: list[str]
    pending: list[str]
    unchanged: list[str]
    rejected: list[RejectedRow]


class InstructorIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)


class TemporaryPasswordOut(BaseModel):
    temporary_password: str  # shown once; the student must change it at the next login


class InviteOut(BaseModel):
    expires_at: datetime | None
    uses: int
    max_uses: int | None
    created_at: datetime
    expired: bool


class NewInviteOut(InviteOut):
    code: str  # shown only now: the code is stored as a hash; rotate again if it is lost


def _courses(request: Request):
    return request.app.state.services.courses


def _course_out(view) -> CourseOut:
    return CourseOut(**view.__dict__)


# -------------------------------------------------------------------------------------------- courses
@router.get("/courses", response_model=list[CourseOut], operation_id="courses_list")
def list_courses(request: Request, user: AnyUser):
    return [_course_out(v) for v in _courses(request).visible_courses(user.account_id)]


@router.post("/courses", response_model=CourseOut, status_code=201, operation_id="courses_create")
def create_course(request: Request, body: CourseIn, user: Creator):
    """The creator becomes the course's first instructor."""
    return _course_out(_courses(request).create(user.account_id, **body.model_dump()))


@router.get("/courses/{course_id}", response_model=CourseOut, operation_id="courses_get")
def get_course(request: Request, access: CourseMemberAccess):
    return _course_out(_courses(request).get(access.course.id, my_role=access.role))


@router.patch("/courses/{course_id}", response_model=CourseOut, operation_id="courses_update")
def update_course(request: Request, body: CoursePatch, access: CourseInstructor):
    return _course_out(_courses(request).update(access.course.id, **body.model_dump(exclude_none=True)))


@router.post("/courses/{course_id}/archive", response_model=CourseOut, operation_id="courses_archive",
             responses={409: {"description": "the course still has students (end the term first)"}})
def archive_course(request: Request, access: CourseInstructor):
    return _course_out(_courses(request).archive(access.course.id))


# -------------------------------------------------------------------------------------------- members
@router.get("/courses/{course_id}/members", response_model=list[MemberOut], operation_id="members_list")
def list_members(request: Request, access: CourseInstructor):
    return [MemberOut(**m.__dict__) for m in _courses(request).members(access.course.id)]


@router.post("/courses/{course_id}/members/import", response_model=ImportReportOut,
             operation_id="members_import")
async def import_members(request: Request, access: CourseInstructor,
                         file: Annotated[UploadFile, File(description="CSV with an `email` column")]):
    """Students from a CSV (`email`, optional `display_name`; other columns are ignored and not stored)."""
    limit = request.app.state.services.settings.limits.accounts.max_roster_bytes
    data = await file.read(limit + 1)
    if len(data) > limit:
        raise CourseError(f"the file is larger than {limit} bytes")
    report = _courses(request).import_roster(access.course.id, data)
    return ImportReportOut(added=report.added, pending=report.pending, unchanged=report.unchanged,
                           rejected=[RejectedRow(**r) for r in report.rejected])


@router.post("/courses/{course_id}/members/instructors", response_model=MemberOut, status_code=201,
             operation_id="members_add_instructor")
def add_instructor(request: Request, body: InstructorIn, access: CourseInstructor):
    """A co-instructor: an existing instructor account, by e-mail (an admin creates instructor accounts)."""
    return MemberOut(**_courses(request).add_instructor(access.course.id, body.email).__dict__)


@router.delete("/courses/{course_id}/members/{member_id}", status_code=204, operation_id="members_remove")
def remove_member(request: Request, member_id: int, access: CourseInstructor):
    _courses(request).remove_member(access.course.id, member_id)


@router.post("/courses/{course_id}/members/{member_id}/reset-password", response_model=TemporaryPasswordOut,
             operation_id="members_reset_password")
def reset_password(request: Request, member_id: int, access: CourseInstructor):
    return TemporaryPasswordOut(temporary_password=_courses(request).reset_student_password(access.course.id,
                                                                                             member_id))


# ------------------------------------------------------------------------------------ invitation code
@router.get("/courses/{course_id}/invite", response_model=InviteOut | None, operation_id="invite_get")
def get_invite(request: Request, access: CourseInstructor):
    """The current code's expiry and use count (not the code itself; null when there is none)."""
    view = _courses(request).invite(access.course.id)
    return InviteOut(**view.__dict__) if view else None


@router.post("/courses/{course_id}/invite/rotate", response_model=NewInviteOut, operation_id="invite_rotate")
def rotate_invite(request: Request, access: CourseInstructor):
    """A new invitation code; the previous one stops working."""
    code, view = _courses(request).rotate_invite(access.course.id)
    return NewInviteOut(code=code, **view.__dict__)
