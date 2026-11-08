"""API v2 errors (api-v2.md section 2): {"detail": "<English sentence>", "code": "<machine code>"}."""
from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.platform.courses import CourseConflict, CourseError, CourseNotFound, JoinRefused
from app.platform.usage import UsageLimitExceeded


class ErrorCode(StrEnum):
    not_found = "not_found"
    forbidden = "forbidden"
    invalid = "invalid"
    conflict = "conflict"  # settings or content changed since it was read (optimistic locking)
    settings_applying = "settings_applying"  # 423 while a settings change is applied
    usage_limit = "usage_limit"  # 429


class ErrorBody(BaseModel):
    detail: str
    code: ErrorCode
    retry_after_seconds: int | None = None


def error(status_code: int, code: ErrorCode, detail: str, **extra) -> JSONResponse:
    return JSONResponse(ErrorBody(detail=detail, code=code, **extra).model_dump(exclude_none=True),
                        status_code=status_code)


async def usage_limit_handler(request: Request, exc: UsageLimitExceeded) -> JSONResponse:
    return error(429, ErrorCode.usage_limit, "Usage limit reached. Try again later.",
                 retry_after_seconds=exc.retry_after_seconds)


async def course_error_handler(request: Request, exc: CourseError) -> JSONResponse:
    """Courses, members and joining (task Z9): 404 / 409 / 400 / 422 with the service's English message."""
    if isinstance(exc, CourseNotFound):
        return error(404, ErrorCode.not_found, str(exc))
    if isinstance(exc, CourseConflict):
        return error(409, ErrorCode.conflict, str(exc))
    if isinstance(exc, JoinRefused):
        return error(400, ErrorCode.invalid, str(exc))
    return error(422, ErrorCode.invalid, str(exc))
