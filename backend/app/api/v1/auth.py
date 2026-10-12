from fastapi import APIRouter, HTTPException, Request, Response, status
from pydantic import BaseModel, Field

from app.api.deps import ServicesDep
from app.auth.deps import CurrentUserDep
from app.auth.service import AccountLocked, InvalidCredentials, PasswordPolicyError

router = APIRouter(prefix="/auth", tags=["auth"])

GENERIC_LOGIN_ERROR = "invalid username or password"


class LoginBody(BaseModel):
    username: str = Field(min_length=1, max_length=64)
    password: str = Field(min_length=1, max_length=256)


class ChangePasswordBody(BaseModel):
    current_password: str = Field(min_length=1, max_length=256)
    new_password: str = Field(min_length=1, max_length=256)


class Me(BaseModel):
    username: str
    display_name: str
    role: str
    must_change_password: bool


@router.post("/login", response_model=Me)
def login(body: LoginBody, response: Response, services: ServicesDep):
    cfg = services.settings.auth
    try:
        account, token = services.accounts.login(body.username, body.password)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, GENERIC_LOGIN_ERROR) from None
    except AccountLocked:
        raise HTTPException(status.HTTP_429_TOO_MANY_REQUESTS,
                            "too many failed attempts; try again later") from None
    response.set_cookie(cfg.cookie_name, token, max_age=int(cfg.session_ttl_hours * 3600), httponly=True,
                        samesite="lax", secure=cfg.cookie_secure, path="/")
    return Me(username=account.username, display_name=account.display_name, role=account.role,
              must_change_password=account.must_change_password)


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(request: Request, response: Response, services: ServicesDep):
    cfg = services.settings.auth
    services.accounts.logout(request.cookies.get(cfg.cookie_name))
    response.delete_cookie(cfg.cookie_name, path="/")


@router.get("/me", response_model=Me)
def me(user: CurrentUserDep):
    """Allowed even when a password change is pending, so the client knows to ask for it."""
    return Me(username=user.username, display_name=user.display_name, role=user.role,
              must_change_password=user.must_change_password)


@router.post("/change-password", response_model=Me)
def change_password(body: ChangePasswordBody, user: CurrentUserDep, services: ServicesDep):
    try:
        account = services.accounts.change_password(user.account_id, body.current_password, body.new_password,
                                                    keep_token_hash=user.token_hash)
    except InvalidCredentials:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "current password is wrong") from None
    except PasswordPolicyError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    return Me(username=account.username, display_name=account.display_name, role=account.role,
              must_change_password=account.must_change_password)
