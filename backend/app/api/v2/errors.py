"""API v2 errors (api-v2.md section 2): {"detail": "<English sentence>", "code": "<machine code>"}."""
from enum import StrEnum

from fastapi import Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.catalog import CatalogError
from app.catalog.editor import CatalogConflict, CatalogNotFound
from app.platform.courses import CourseConflict, CourseError, CourseNotFound, JoinRefused
from app.platform.settings import SettingsConflict, SettingsLocked
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


async def catalog_error_handler(request: Request, exc: CatalogError) -> JSONResponse:
    """Course content (task Z9): 404 / 409, or 422 listing the content problems."""
    if isinstance(exc, CatalogNotFound):
        return error(404, ErrorCode.not_found, str(exc))
    if isinstance(exc, CatalogConflict):
        return error(409, ErrorCode.conflict, str(exc))
    return error(422, ErrorCode.invalid, str(exc))


class ApiError(Exception):
    """Raised by v2 endpoints for an error body with a code (handled for /api/v2 only)."""

    def __init__(self, status_code: int, code: ErrorCode, detail: str) -> None:
        super().__init__(detail)
        self.status_code, self.code, self.detail = status_code, code, detail


async def api_error_handler(request: Request, exc: ApiError) -> JSONResponse:
    return error(exc.status_code, exc.code, exc.detail)


def settings_error(exc: Exception) -> ApiError:
    """SettingsError -> 422, SettingsConflict -> 409, SettingsLocked -> 423 settings_applying."""
    if isinstance(exc, SettingsLocked):
        return ApiError(423, ErrorCode.settings_applying, str(exc))
    if isinstance(exc, SettingsConflict):
        return ApiError(409, ErrorCode.conflict, str(exc))
    return ApiError(422, ErrorCode.invalid, str(exc))
