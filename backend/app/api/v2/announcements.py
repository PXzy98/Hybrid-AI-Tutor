"""Course announcements (V20; api-v2.md 3.11): short plain text notices from the course's instructors.

Every member of the course reads them (pinned first, then newest first); only its instructors write them. The
title and body are scanned for student data before they are stored, like an uploaded material, and the
audit log keeps IDs and field names only, never the text. An archived course takes no new or changed
announcements. Not in scope: e-mail, unread markers, scheduled publishing.
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.api.v2.errors import ApiError, ErrorCode
from app.platform.access import CourseAccess, require_course_role
from app.privacy.profiles import privacy_profile, scan_document
from app.storage.models import Announcement, AuditLog, Course, utcnow

router = APIRouter(tags=["announcements"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
CourseMemberAccess = Annotated[CourseAccess, Depends(require_course_role("instructor", "student"))]

TITLE_MAX, BODY_MAX = 200, 4000
REFUSED = "blank title, the course is archived, or the privacy scan found student data"


class AnnouncementOut(BaseModel):
    id: int
    title: str
    body: str  # plain text; line breaks are kept, nothing is rendered as Markdown or HTML
    pinned: bool
    created_at: datetime
    updated_at: datetime  # the last change of the title or the body


class AnnouncementIn(BaseModel):
    title: str = Field(min_length=1, max_length=TITLE_MAX)
    body: str = Field("", max_length=BODY_MAX)
    pinned: bool = False


class AnnouncementPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=TITLE_MAX)
    body: str | None = Field(None, max_length=BODY_MAX)
    pinned: bool | None = None


def _engine(request: Request):
    return request.app.state.services.engine


def _out(row: Announcement) -> AnnouncementOut:
    return AnnouncementOut(id=row.id, title=row.title, body=row.body, pinned=row.pinned,
                           created_at=row.created_at, updated_at=row.updated_at)


def _checked(title: str, body: str, course_type: str) -> tuple[str, str]:
    """The stripped title and body; 422 when the title is blank or the privacy scan finds student data (the
    response names the finding types, never the text)."""
    title, body = title.strip(), body.strip()
    if not title:
        raise ApiError(422, ErrorCode.invalid, "the title cannot be empty")
    found = scan_document(f"{title}\n\n{body}", privacy_profile(course_type)).blocking
    if found:
        raise ApiError(422, ErrorCode.invalid, "the privacy scan found student data: " + ", ".join(found))
    return title, body


def _active(db: Session, course_id: int) -> None:
    course = db.get(Course, course_id)
    if course is not None and course.status != "active":
        raise ApiError(422, ErrorCode.invalid, "the course is archived")


def _audit(db: Session, access: CourseAccess, action: str, details: dict) -> None:
    """IDs and field names only, never the text."""
    db.add(AuditLog(account_id=access.account_id, action=action, target=f"course:{access.course.id}",
                    details=details))


def _get(db: Session, course_id: int, announcement_id: int, *, lock: bool = False) -> Announcement:
    query = select(Announcement).where(Announcement.id == announcement_id)
    row = db.exec(query.with_for_update() if lock else query).first()
    if row is None or row.course_id != course_id:
        raise ApiError(404, ErrorCode.not_found, "announcement not found")
    return row


@router.get("/courses/{course_id}/announcements", response_model=list[AnnouncementOut],
            operation_id="announcements_list")
def list_announcements(access: CourseMemberAccess, request: Request):
    """The course's announcements: pinned first, then newest first."""
    with Session(_engine(request)) as db:
        rows = db.exec(select(Announcement).where(Announcement.course_id == access.course.id)
                       .order_by(col(Announcement.pinned).desc(), col(Announcement.created_at).desc(),
                                 col(Announcement.id).desc())).all()
        return [_out(r) for r in rows]


@router.post("/courses/{course_id}/announcements", response_model=AnnouncementOut, status_code=201,
             operation_id="announcements_create",
             responses={422: {"description": REFUSED}})
def create_announcement(body: AnnouncementIn, access: CourseInstructor, request: Request):
    title, text = _checked(body.title, body.body, access.course.course_type)
    with Session(_engine(request), expire_on_commit=False) as db:
        _active(db, access.course.id)
        now = utcnow()  # the same instant: a new announcement is not shown as edited
        row = Announcement(course_id=access.course.id, author_id=access.account_id, title=title, body=text,
                           pinned=body.pinned, created_at=now, updated_at=now)
        db.add(row)
        db.flush()
        _audit(db, access, "announcement.create", {"announcement_id": row.id})
        db.commit()
        return _out(row)


@router.patch("/courses/{course_id}/announcements/{announcement_id}", response_model=AnnouncementOut,
              operation_id="announcements_update",
              responses={422: {"description": REFUSED}})
def update_announcement(announcement_id: int, body: AnnouncementPatch, access: CourseInstructor,
                        request: Request):
    """Change the title, the body or the pin; fields left out stay as they are."""
    changes = body.model_dump(exclude_none=True)
    with Session(_engine(request), expire_on_commit=False) as db:
        row = _get(db, access.course.id, announcement_id, lock=True)
        _active(db, access.course.id)
        title, text = row.title, row.body
        if "title" in changes or "body" in changes:
            title, text = _checked(changes.get("title", row.title), changes.get("body", row.body),
                                   access.course.course_type)
        fields = sorted(name for name, value in (("title", title), ("body", text),
                                                 ("pinned", changes.get("pinned", row.pinned)))
                        if value != getattr(row, name))
        if fields:
            if "title" in fields or "body" in fields:
                row.updated_at = utcnow()
            row.title, row.body, row.pinned = title, text, changes.get("pinned", row.pinned)
            db.add(row)
            _audit(db, access, "announcement.update", {"announcement_id": announcement_id, "fields": fields})
            db.commit()
        return _out(row)


@router.delete("/courses/{course_id}/announcements/{announcement_id}", status_code=204,
               operation_id="announcements_delete")
def delete_announcement(announcement_id: int, access: CourseInstructor, request: Request):
    with Session(_engine(request)) as db:
        row = _get(db, access.course.id, announcement_id, lock=True)
        db.delete(row)
        _audit(db, access, "announcement.delete", {"announcement_id": announcement_id})
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
