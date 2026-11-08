"""CSRF protection for API v2 (api-v2.md section 2; task Z10).

Every state-changing request (POST, PUT, PATCH, DELETE) under `/api/v2`, including the public `login` and
`join`, sends `X-CSRF-Token`. The value comes from `GET /api/v2/auth/csrf` (and from the `X-CSRF-Token`
response header of `login` and `join`):
- with a session cookie: a token derived from the session token. The session cookie is HttpOnly, so
  another site can neither read nor compute it. Every login gets a new session, so a new token; logout ends
  it;
- without one (before login): a random token in a short-lived, readable `tutor_csrf` cookie that the
  request must repeat in the header (double submit).

API v1 is frozen and keeps working without the header (the v1 frontend predates it; SameSite=Lax cookies
remain its protection).
"""
import hashlib
import hmac
import secrets

from starlette.requests import Request

HEADER = "X-CSRF-Token"
ANON_COOKIE = "tutor_csrf"
ANON_MAX_AGE = 2 * 3600
UNSAFE = {"POST", "PUT", "PATCH", "DELETE"}


def session_token(session_cookie: str) -> str:
    return hashlib.sha256(b"csrf:" + session_cookie.encode("utf-8")).hexdigest()


def new_anonymous_token() -> str:
    return secrets.token_urlsafe(32)


def expected_token(request: Request, session_cookie_name: str) -> str | None:
    """The token this request must carry, or None if it has nothing to compare with."""
    session = request.cookies.get(session_cookie_name)
    if session:
        return session_token(session)
    return request.cookies.get(ANON_COOKIE) or None


def check(request: Request, session_cookie_name: str) -> bool:
    """True if the request is safe or carries the right token."""
    if request.method not in UNSAFE or not request.url.path.startswith("/api/v2/"):
        return True
    expected = expected_token(request, session_cookie_name)
    sent = request.headers.get(HEADER, "")
    return bool(expected and sent) and hmac.compare_digest(expected, sent)
