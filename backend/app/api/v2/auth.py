"""Auth and account (api-v2.md 3.1; task Z9): login by username or e-mail, the caller's memberships, and
joining a course with its invitation code (course-structure.md 3.3).

CSRF (task Z10): `GET /auth/csrf` gives the token for `X-CSRF-Token` (app.auth.csrf); `login` and `join`
return the new session's token in the `X-CSRF-Token` response header. Failed logins and join attempts are
limited per client address; `logout-all` ends every session of the account.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.api.deps import ServicesDep
from app.api.v2.errors import ErrorCode, error
from app.auth import csrf, ratelimit
from app.auth import sessions as auth_sessions
from app.auth.deps import CurrentUserDep
from app.auth.service import AccountLocked, InvalidCredentials, PasswordPolicyError
from app.storage.models import Account, Course, CourseMember

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "invalid username or password"


class LoginIn(BaseModel):
    username: str = Field(min_length=1, max_length=254, description="username or e-mail")
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordIn(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class JoinIn(BaseModel):
    """Logged in: `code` only. New student: `code`, `email`, `display_name` and `password`."""

    code: str = Field(min_length=1, max_length=64)
    email: str | None = Field(None, max_length=254)
    display_name: str | None = Field(None, min_length=1, max_length=100)
    password: str | None = Field(None, min_length=1, max_length=256)


class MembershipOut(BaseModel):
    course_id: int
    code: str
    title: str
    role: Literal["instructor", "student"]
    course_status: str


class MeOut(BaseModel):
    account_id: int
    username: str
    email: str | None
    display_name: str
    system_role: Literal["admin", "instructor", "student"]
    must_change_password: bool
    memberships: list[MembershipOut]  # active memberships; an admin manages every course without one


class JoinOut(BaseModel):
    course_id: int
    me: MeOut


def _me(services, account_id: int) -> MeOut:
    with Session(services.engine) as db:
        account = db.get(Account, account_id)
        rows = db.exec(select(CourseMember, Course).join(Course, CourseMember.course_id == Course.id)
                       .where(CourseMember.account_id == account_id, CourseMember.status == "active")
                       .order_by(col(Course.code))).all()
        memberships = [MembershipOut(course_id=c.id, code=c.code, title=c.title, role=m.role,
                                     course_status=c.status)
                       for m, c in rows if c.status == "active" or m.role == "instructor"]
        return MeOut(account_id=account.id, username=account.username, email=account.email,
                     display_name=account.display_name, system_role=account.role,
                     must_change_password=account.must_change_password, memberships=memberships)


class CsrfOut(BaseModel):
    csrf_token: str  # send it as the X-CSRF-Token header of every POST, PUT, PATCH and DELETE


def _login(services, response: Response, username: str, password: str):
    cfg = services.settings.auth
    try:
        account, token = services.accounts.login(username, password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR) from None
    except AccountLocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "too many failed attempts; try again later") from None
    response.set_cookie(cfg.cookie_name, token, max_age=int(cfg.session_ttl_hours * 3600), httponly=True,
                        samesite="lax", secure=cfg.cookie_secure, path="/")
    response.headers[csrf.HEADER] = csrf.session_token(token)  # the new session's CSRF token
    response.delete_cookie(csrf.ANON_COOKIE, path="/")
    return account


@router.get("/csrf", response_model=CsrfOut, operation_id="auth_csrf")
def get_csrf(request: Request, response: Response, services: ServicesDep):
    """Public. With a session: its token. Without: a short-lived anonymous token (also set as a cookie)."""
    token = csrf.expected_token(request, services.settings.auth.cookie_name)
    if token is None:
        token = csrf.new_anonymous_token()
        response.set_cookie(csrf.ANON_COOKIE, token, max_age=csrf.ANON_MAX_AGE, httponly=False,
                            samesite="lax", secure=services.settings.auth.cookie_secure, path="/")
    return CsrfOut(csrf_token=token)


@router.post("/login", response_model=MeOut, operation_id="auth_login",
             responses={429: {"description": "too many failed attempts"}})
def login(body: LoginIn, request: Request, response: Response, services: ServicesDep):
    window, client = ratelimit.login_failures(request, services), ratelimit.client_address(request)
    wait = window.wait(client)
    if wait:
        return error(429, ErrorCode.usage_limit, "Too many failed logins. Try again later.",
                     retry_after_seconds=wait)
    try:
        account = _login(services, response, body.username, body.password)
    except HTTPException as e:
        if e.status_code == status.HTTP_401_UNAUTHORIZED:
            window.add(client)
        raise
    return _me(services, account.id)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT, operation_id="auth_logout")
def logout(request: Request, response: Response, services: ServicesDep):
    cfg = services.settings.auth
    services.accounts.logout(request.cookies.get(cfg.cookie_name))
    response.delete_cookie(cfg.cookie_name, path="/")
    response.delete_cookie(csrf.ANON_COOKIE, path="/")


@router.post("/logout-all", status_code=status.HTTP_204_NO_CONTENT, operation_id="auth_logout_all")
def logout_all(user: CurrentUserDep, response: Response, services: ServicesDep):
    """End every session of the account, on every device (this one included)."""
    with Session(services.engine) as db:
        auth_sessions.revoke_all(db, user.account_id)
        db.commit()
    response.delete_cookie(services.settings.auth.cookie_name, path="/")


@router.get("/me", response_model=MeOut, operation_id="auth_me")
def me(user: CurrentUserDep, services: ServicesDep):
    """Allowed even when a password change is pending, so the client knows to ask for it."""
    return _me(services, user.account_id)


@router.post("/change-password", response_model=MeOut, operation_id="auth_change_password")
def change_password(body: ChangePasswordIn, user: CurrentUserDep, services: ServicesDep):
    try:
        services.accounts.change_password(user.account_id, body.current_password, body.new_password,
                                          keep_token_hash=user.token_hash)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current password is wrong") from None
    except PasswordPolicyError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    return _me(services, user.account_id)


@router.post("/join", response_model=JoinOut, operation_id="auth_join",
             responses={400: {"description": "invalid code, or the e-mail is not on the course list"},
                        429: {"description": "too many attempts"}})
def join(body: JoinIn, request: Request, response: Response, services: ServicesDep):
    """Join a course with its invitation code (course-structure.md 3.3). Logged in (a student): the pending
    membership with the account's e-mail becomes active. Not logged in: a new account is created for an
    e-mail on the course list, every pending membership of that e-mail becomes active, and the new account
    is logged in."""
    joins = ratelimit.window(request.app.state, "join_attempts",
                             services.settings.limits.accounts.join_attempts_per_hour)
    wait = joins.allow(ratelimit.client_address(request))
    if wait:
        return error(429, ErrorCode.usage_limit, "Too many attempts. Try again later.",
                     retry_after_seconds=wait)
    found = services.accounts.resolve(request.cookies.get(services.settings.auth.cookie_name))
    if found is not None:
        account, _ = found
        course_id = services.courses.join_existing(account.id, body.code)
        return JoinOut(course_id=course_id, me=_me(services, account.id))
    if not (body.email and body.display_name and body.password):
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT,
                            "a new account needs email, display_name and password (or log in first)")
    account, course_id = services.courses.join_new(body.code, email=body.email,
                                                   display_name=body.display_name, password=body.password)
    _login(services, response, account.email, body.password)
    return JoinOut(course_id=course_id, me=_me(services, account.id))
