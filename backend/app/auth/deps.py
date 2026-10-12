"""FastAPI dependencies: who is calling, and may they? (privacy invariant 6)"""
from dataclasses import dataclass
from typing import Annotated, Literal

from fastapi import Depends, HTTPException, Request, status

from app.api.deps import ServicesDep


@dataclass(frozen=True)
class CurrentUser:
    account_id: int
    username: str
    display_name: str
    role: Literal["student", "instructor"]
    student_id: str | None
    must_change_password: bool
    token_hash: str


def current_user(request: Request, services: ServicesDep) -> CurrentUser:
    token = request.cookies.get(services.settings.auth.cookie_name)
    found = services.accounts.resolve(token)
    if found is None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "not logged in")
    account, session = found
    return CurrentUser(account.id, account.username, account.display_name, account.role, account.student_id,
                       account.must_change_password, session.token_hash)


CurrentUserDep = Annotated[CurrentUser, Depends(current_user)]


def _ready(user: CurrentUser) -> CurrentUser:
    if user.must_change_password:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "password change required")
    return user


def require_any(user: CurrentUserDep) -> CurrentUser:
    return _ready(user)


def require_student(user: CurrentUserDep) -> CurrentUser:
    if user.role != "student" or not user.student_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "students only")
    return _ready(user)


def require_instructor(user: CurrentUserDep) -> CurrentUser:
    if user.role != "instructor":
        raise HTTPException(status.HTTP_403_FORBIDDEN, "instructors only")
    return _ready(user)


AnyUser = Annotated[CurrentUser, Depends(require_any)]
Student = Annotated[CurrentUser, Depends(require_student)]
Instructor = Annotated[CurrentUser, Depends(require_instructor)]
