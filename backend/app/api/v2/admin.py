"""Admin: instructor accounts (api-v2.md 3.2; course-structure.md 3.2; task Z9).

An admin creates instructor (or admin) accounts by e-mail with a one-time temporary password, deactivates
them, changes between instructor and admin, and resets passwords. Nobody deactivates themselves or changes
their own role, so an admin always remains. System settings and model connections have their own modules.
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field

from app.api.v2.errors import ApiError, ErrorCode
from app.auth.deps import CurrentUser
from app.auth.service import AccountError, AccountNotFound, UsernameTaken
from app.platform.access import require_system_role

router = APIRouter(prefix="/admin", tags=["admin"])
Admin = Annotated[CurrentUser, Depends(require_system_role("admin"))]


class StaffOut(BaseModel):
    account_id: int
    username: str
    email: str | None
    display_name: str
    role: Literal["instructor", "admin"]
    active: bool
    must_change_password: bool
    last_login_at: datetime | None


class StaffIn(BaseModel):
    email: str = Field(min_length=3, max_length=254)
    display_name: str = Field(min_length=1, max_length=100)
    role: Literal["instructor", "admin"] = "instructor"


class StaffPatch(BaseModel):
    active: bool | None = None
    role: Literal["instructor", "admin"] | None = None
    display_name: str | None = Field(None, min_length=1, max_length=100)


class NewStaffOut(StaffOut):
    temporary_password: str  # shown once; must be changed at the first login


class TemporaryPasswordOut(BaseModel):
    temporary_password: str


def _out(a) -> StaffOut:
    return StaffOut(account_id=a.id, username=a.username, email=a.email, display_name=a.display_name,
                    role=a.role, active=a.active, must_change_password=a.must_change_password,
                    last_login_at=a.last_login_at)


def _accounts(request: Request):
    return request.app.state.services.accounts


def _account_error(e: AccountError) -> ApiError:
    if isinstance(e, AccountNotFound):
        return ApiError(404, ErrorCode.not_found, "instructor account not found")
    if isinstance(e, UsernameTaken):
        return ApiError(409, ErrorCode.conflict, "an account with this e-mail exists")
    return ApiError(422, ErrorCode.invalid, str(e))


@router.get("/instructors", response_model=list[StaffOut], operation_id="admin_instructors_list")
def list_instructors(request: Request, _: Admin):
    return [_out(a) for a in _accounts(request).list_staff()]


@router.post("/instructors", response_model=NewStaffOut, status_code=201,
             operation_id="admin_instructors_create",
             responses={409: {"description": "an account with this e-mail exists"}})
def create_instructor(request: Request, body: StaffIn, _: Admin):
    try:
        account, temp = _accounts(request).create_staff(body.email, body.display_name, body.role)
    except AccountError as e:
        raise _account_error(e) from None
    return NewStaffOut(**_out(account).model_dump(), temporary_password=temp)


@router.patch("/instructors/{account_id}", response_model=StaffOut, operation_id="admin_instructors_update")
def update_instructor(request: Request, account_id: int, body: StaffPatch, user: Admin):
    try:
        return _out(_accounts(request).update_staff(account_id, acting_account_id=user.account_id,
                                                    **body.model_dump(exclude_none=True)))
    except AccountError as e:
        raise _account_error(e) from None


@router.post("/instructors/{account_id}/reset-password", response_model=TemporaryPasswordOut,
             operation_id="admin_instructors_reset_password")
def reset_password(request: Request, account_id: int, _: Admin):
    """A temporary password; all sessions of the account end."""
    try:
        return TemporaryPasswordOut(temporary_password=_accounts(request).reset_staff_password(account_id))
    except AccountError as e:
        raise _account_error(e) from None
