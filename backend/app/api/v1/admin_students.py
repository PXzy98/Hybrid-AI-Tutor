"""Instructor: student-account management (design §7.5, §8.3). Account data only, never learning data."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel, Field

from app.api.deps import ServicesDep
from app.auth.deps import Instructor
from app.auth.service import AccountNotFound, InvalidUsername, UsernameTaken
from app.storage.models import Account

router = APIRouter(prefix="/admin/students", tags=["admin: students"])

NO_STORE = {"Cache-Control": "no-store"}  # responses that carry a temporary password


class StudentAccountOut(BaseModel):
    id: int
    username: str
    display_name: str
    active: bool
    must_change_password: bool
    created_at: datetime
    last_login_at: datetime | None

    @classmethod
    def of(cls, a: Account) -> "StudentAccountOut":
        return cls(id=a.id, username=a.username, display_name=a.display_name, active=a.active,
                   must_change_password=a.must_change_password, created_at=a.created_at,
                   last_login_at=a.last_login_at)


class CreateStudentBody(BaseModel):
    username: str = Field(min_length=3, max_length=32, description="not a real student number")
    display_name: str = Field("", max_length=80)


class CreatedStudent(BaseModel):
    account: StudentAccountOut
    temporary_password: str  # shown once; the student must change it at first login


class UpdateStudentBody(BaseModel):
    display_name: str | None = Field(None, max_length=80)
    active: bool | None = None


class TemporaryPassword(BaseModel):
    temporary_password: str


def _not_found() -> HTTPException:
    return HTTPException(status.HTTP_404_NOT_FOUND, "student not found")


@router.get("", response_model=list[StudentAccountOut])
def list_students(_: Instructor, services: ServicesDep):
    return [StudentAccountOut.of(a) for a in services.accounts.list_students()]


@router.post("", response_model=CreatedStudent, status_code=status.HTTP_201_CREATED)
def create_student(body: CreateStudentBody, _: Instructor, services: ServicesDep, response: Response):
    try:
        account, temp = services.accounts.create_student(body.username, body.display_name)
    except InvalidUsername as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    except UsernameTaken:
        raise HTTPException(status.HTTP_409_CONFLICT, "username already exists") from None
    response.headers.update(NO_STORE)
    return CreatedStudent(account=StudentAccountOut.of(account), temporary_password=temp)


@router.patch("/{account_id}", response_model=StudentAccountOut)
def update_student(account_id: int, body: UpdateStudentBody, _: Instructor, services: ServicesDep):
    try:
        account = services.accounts.update_student(account_id, body.display_name, body.active)
    except AccountNotFound:
        raise _not_found() from None
    return StudentAccountOut.of(account)


@router.post("/{account_id}/reset-password", response_model=TemporaryPassword)
def reset_password(account_id: int, _: Instructor, services: ServicesDep, response: Response):
    try:
        temp = services.accounts.reset_student_password(account_id)
    except AccountNotFound:
        raise _not_found() from None
    response.headers.update(NO_STORE)
    return TemporaryPassword(temporary_password=temp)


@router.delete("/{account_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_student(account_id: int, _: Instructor, services: ServicesDep):
    """Deletes the account, its sessions and all of its learning data; request logs are anonymized."""
    try:
        services.accounts.delete_student(account_id)
    except AccountNotFound:
        raise _not_found() from None
