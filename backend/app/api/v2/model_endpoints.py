"""Model connections (task Z6; api-v2.md 3.2 and 3.3).

System connections: `/api/v2/admin/model-endpoints` (admin). Course connections:
`/api/v2/courses/{course_id}/model-endpoints` (instructors of the course; others get 404). Responses never
contain an API key, only its last four characters. Creating or changing a connection runs a connection test
first; a `trusted_local` connection needs `confirm_controlled` (it receives original student text).
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.deps import CurrentUser
from app.llm import endpoints as registry
from app.platform.access import CourseAccess, require_course_role, require_system_role

router = APIRouter(tags=["model-endpoints"])
Admin = Annotated[CurrentUser, Depends(require_system_role("admin"))]
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]


class EndpointOut(BaseModel):
    id: int
    course_id: int | None
    name: str
    kind: Literal["ollama", "openai_compat"]
    base_url: str
    model: str
    trust: Literal["trusted_local", "external"]
    api_key_last4: str | None = None
    last_test_ok_at: datetime | None = None


class EndpointIn(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    kind: Literal["ollama", "openai_compat"]
    base_url: str = Field(max_length=300)
    model: str = Field(min_length=1, max_length=100)
    trust: Literal["trusted_local", "external"] = "external"
    api_key: str | None = Field(None, max_length=500)
    confirm_controlled: bool = False  # "I control this service": required for trusted_local


class EndpointPatch(BaseModel):
    name: str | None = Field(None, min_length=1, max_length=100)
    kind: Literal["ollama", "openai_compat"] | None = None
    base_url: str | None = Field(None, max_length=300)
    model: str | None = Field(None, min_length=1, max_length=100)
    trust: Literal["trusted_local", "external"] | None = None
    api_key: str | None = Field(None, max_length=500)
    confirm_controlled: bool = False


def _key(request: Request) -> str | None:
    s = request.app.state.services.settings
    return s.settings_encryption_key.get_secret_value() if s.settings_encryption_key else None


def _out(v: registry.EndpointView) -> EndpointOut:
    return EndpointOut(**v.__dict__)


def _unprocessable(e: Exception) -> HTTPException:
    return HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e))


async def _create(request: Request, body: EndpointIn, course_id: int | None, account_id: int) -> EndpointOut:
    try:
        return _out(await registry.create_endpoint(
            request.app.state.services.engine, course_id=course_id, account_id=account_id,
            encryption_key=_key(request), **body.model_dump()))
    except (registry.EndpointError, registry.secrets.MissingEncryptionKey) as e:
        raise _unprocessable(e) from None


async def _update(request: Request, endpoint_id: int, body: EndpointPatch, course_id: int | None,
                  account_id: int) -> EndpointOut:
    changes = body.model_dump(exclude_none=True, exclude={"confirm_controlled"})
    try:
        return _out(await registry.update_endpoint(
            request.app.state.services.engine, endpoint_id, course_id=course_id, changes=changes,
            confirm_controlled=body.confirm_controlled, account_id=account_id, encryption_key=_key(request)))
    except registry.EndpointError as e:
        if "unknown" in str(e):
            raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found") from None
        raise _unprocessable(e) from None
    except registry.secrets.MissingEncryptionKey as e:
        raise _unprocessable(e) from None


def _delete(request: Request, endpoint_id: int, course_id: int | None, account_id: int) -> None:
    try:
        registry.delete_endpoint(request.app.state.services.engine, endpoint_id, course_id=course_id,
                                 account_id=account_id)
    except registry.EndpointError:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "connection not found") from None


# ------------------------------------------------------------------------------------------ system (admin)
@router.get("/admin/model-endpoints", response_model=list[EndpointOut], operation_id="model_endpoints_list")
def list_system(request: Request, _: Admin):
    return [_out(v) for v in registry.list_endpoints(request.app.state.services.engine, course_id=None)]


@router.post("/admin/model-endpoints", response_model=EndpointOut, status_code=201,
             operation_id="model_endpoints_create")
async def create_system(request: Request, body: EndpointIn, user: Admin):
    return await _create(request, body, None, user.account_id)


@router.patch("/admin/model-endpoints/{endpoint_id}", response_model=EndpointOut,
              operation_id="model_endpoints_update")
async def update_system(request: Request, endpoint_id: int, body: EndpointPatch, user: Admin):
    return await _update(request, endpoint_id, body, None, user.account_id)


@router.delete("/admin/model-endpoints/{endpoint_id}", status_code=204, operation_id="model_endpoints_delete")
def delete_system(request: Request, endpoint_id: int, user: Admin):
    _delete(request, endpoint_id, None, user.account_id)


# --------------------------------------------------------------------------------- course (instructors)
@router.get("/courses/{course_id}/model-endpoints", response_model=list[EndpointOut],
            operation_id="course_model_endpoints_list")
def list_course(request: Request, access: CourseInstructor):
    return [_out(v) for v in registry.list_endpoints(request.app.state.services.engine,
                                                     course_id=access.course.id)]


@router.post("/courses/{course_id}/model-endpoints", response_model=EndpointOut, status_code=201,
             operation_id="course_model_endpoints_create")
async def create_course_endpoint(request: Request, body: EndpointIn, access: CourseInstructor):
    return await _create(request, body, access.course.id, access.account_id)


@router.patch("/courses/{course_id}/model-endpoints/{endpoint_id}", response_model=EndpointOut,
              operation_id="course_model_endpoints_update")
async def update_course_endpoint(request: Request, endpoint_id: int, body: EndpointPatch,
                                 access: CourseInstructor):
    return await _update(request, endpoint_id, body, access.course.id, access.account_id)


@router.delete("/courses/{course_id}/model-endpoints/{endpoint_id}", status_code=204,
               operation_id="course_model_endpoints_delete")
def delete_course_endpoint(request: Request, endpoint_id: int, access: CourseInstructor):
    _delete(request, endpoint_id, access.course.id, access.account_id)
