"""Settings (api-v2.md 3.2 and 3.3; course-structure.md 6; task Z9): system settings (admin) and course
settings (the course's instructors), their history and undo, and the state of a system change being applied.

Every `PUT` sends the `version` it read: 409 if the settings changed since, 423 (`settings_applying`) while a
component change is still being applied. A `null` value means "use the next layer" (course → system →
config.yaml). The `usage_*` course fields are not exposed: usage limits are config only for now (guide 4.4).
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlmodel import Session, select

from app.api.v2.errors import settings_error
from app.auth.deps import CurrentUser
from app.platform.access import CourseAccess, require_course_role, require_system_role
from app.platform.settings import SettingsConflict, SettingsError, SettingsLocked
from app.storage.models import ConfigHistory, ProcessStatus, SystemSettings, utcnow

router = APIRouter(tags=["settings"])
Admin = Annotated[CurrentUser, Depends(require_system_role("admin"))]
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
CourseType = Literal["medical_science", "life_science", "ece", "general"]


class SystemValues(BaseModel):
    checkers: list[str] | None = None  # the required checkers cannot be switched off
    weak_evidence: bool | None = None
    level_basic_below: float | None = Field(None, ge=0, le=1)
    level_advanced_above: float | None = Field(None, ge=0, le=1)
    level_hysteresis: float | None = Field(None, ge=0, le=0.2)
    knowledge_model: str | None = None
    default_routing_method: Literal["lr", "svm"] | None = None
    local_llm_url: str | None = Field(None, max_length=300)
    local_llm_model: str | None = Field(None, max_length=100)
    enabled_course_types: list[CourseType] | None = None
    default_local_endpoint_id: int | None = None
    default_cloud_endpoint_id: int | None = None


class CourseValues(BaseModel):
    course_type: CourseType | None = None
    visibility_mode: Literal["A", "B"] | None = None
    local_only: bool | None = None
    routing_preference: Literal["default", "prefer_local", "prefer_cloud"] | None = None
    routing_threshold: float | None = Field(None, ge=0, le=1)
    show_routing_progress: bool | None = None
    local_endpoint_id: int | None = None
    cloud_endpoint_id: int | None = None


class SystemSettingsOut(BaseModel):
    values: SystemValues
    version: int
    apply_state: Literal["applied", "applying", "failed"]


class SystemSettingsIn(BaseModel):
    values: SystemValues
    version: int


class CourseSettingsOut(BaseModel):
    values: CourseValues
    version: int


class CourseSettingsIn(BaseModel):
    values: CourseValues
    version: int


class HistoryEntryOut(BaseModel):
    id: int
    changed_at: datetime
    account_id: int | None
    version: int | None
    changed: list[str]  # field names whose value changed
    values: dict  # the full editable subset after the change
    previous: dict


class ProcessOut(BaseModel):
    kind: str
    last_seen: datetime
    component_version: int
    error: str | None


class ApplyStatusOut(BaseModel):
    apply_state: Literal["applied", "applying", "failed"]
    version: int
    target_version: int | None
    started_at: datetime | None
    error: str | None
    processes: list[ProcessOut]  # live api/worker processes and the component version each runs


def _service(request: Request):
    return request.app.state.services.settings_service


def _history_out(e: ConfigHistory) -> HistoryEntryOut:
    changed = sorted(k for k in set(e.values) | set(e.previous) if e.values.get(k) != e.previous.get(k))
    return HistoryEntryOut(id=e.id, changed_at=e.changed_at, account_id=e.account_id, version=e.version,
                           changed=changed, values=e.values, previous=e.previous)


def _system_out(request: Request) -> SystemSettingsOut:
    values, version, state = _service(request).system_values()
    return SystemSettingsOut(values=SystemValues(**values), version=version, apply_state=state)


def _course_out(request: Request, course_id: int) -> CourseSettingsOut:
    values, version = _service(request).course_values(course_id)
    return CourseSettingsOut(values=CourseValues(**values), version=version)


# ------------------------------------------------------------------------------------- system (admin)
@router.get("/admin/settings", response_model=SystemSettingsOut, operation_id="admin_settings_get")
def get_system(request: Request, _: Admin):
    return _system_out(request)


@router.put("/admin/settings", response_model=SystemSettingsOut, operation_id="admin_settings_update",
            responses={409: {"description": "changed since it was read"},
                       423: {"description": "a change is still being applied"}})
def put_system(request: Request, body: SystemSettingsIn, user: Admin):
    try:
        _service(request).save_system(body.values.model_dump(), expected_version=body.version,
                                      account_id=user.account_id)
    except (SettingsError, SettingsConflict, SettingsLocked) as e:
        raise settings_error(e) from None
    return _system_out(request)


@router.get("/admin/settings/history", response_model=list[HistoryEntryOut],
            operation_id="admin_settings_history")
def system_history(request: Request, _: Admin, limit: int = 20):
    return [_history_out(e) for e in _service(request).history(scope="system", limit=min(max(limit, 1), 100))]


@router.post("/admin/settings/restore/{history_id}", response_model=SystemSettingsOut,
             operation_id="admin_settings_restore")
def restore_system(request: Request, history_id: int, user: Admin):
    _restorable(request, history_id, scope="system")
    try:
        _service(request).restore(history_id, account_id=user.account_id)
    except (SettingsError, SettingsConflict, SettingsLocked) as e:
        raise settings_error(e) from None
    return _system_out(request)


@router.get("/admin/settings/apply-status", response_model=ApplyStatusOut,
            operation_id="admin_settings_apply_status")
def apply_status(request: Request, _: Admin):
    """Polled by the settings page while `apply_state` is `applying` (course-structure.md 6.5)."""
    services = request.app.state.services
    stale = services.settings.limits.settings.poll_seconds * 3
    with Session(services.engine) as db:
        row = db.get(SystemSettings, 1)
        processes = db.exec(select(ProcessStatus).order_by(ProcessStatus.kind, ProcessStatus.last_seen)).all()
    now = utcnow()
    live = [ProcessOut(kind=p.kind, last_seen=p.last_seen, component_version=p.component_version,
                       error=p.error) for p in processes if (now - p.last_seen).total_seconds() <= stale]
    if row is None:
        return ApplyStatusOut(apply_state="applied", version=0, target_version=None, started_at=None,
                              error=None, processes=live)
    return ApplyStatusOut(apply_state=row.apply_state, version=row.version,
                          target_version=row.apply_target_version, started_at=row.apply_started_at,
                          error=row.apply_error, processes=live)


# --------------------------------------------------------------------------------- course (instructors)
@router.get("/courses/{course_id}/settings", response_model=CourseSettingsOut,
            operation_id="course_settings_get")
def get_course(request: Request, access: CourseInstructor):
    return _course_out(request, access.course.id)


@router.put("/courses/{course_id}/settings", response_model=CourseSettingsOut,
            operation_id="course_settings_update",
            responses={409: {"description": "changed since it was read"}})
def put_course(request: Request, body: CourseSettingsIn, access: CourseInstructor):
    try:
        _service(request).save_course(access.course.id, body.values.model_dump(),
                                      expected_version=body.version, account_id=access.account_id)
    except (SettingsError, SettingsConflict, SettingsLocked) as e:
        raise settings_error(e) from None
    return _course_out(request, access.course.id)


@router.get("/courses/{course_id}/settings/history", response_model=list[HistoryEntryOut],
            operation_id="course_settings_history")
def course_history(request: Request, access: CourseInstructor, limit: int = 20):
    return [_history_out(e) for e in _service(request).history(scope="course", course_id=access.course.id,
                                                               limit=min(max(limit, 1), 100))]


@router.post("/courses/{course_id}/settings/restore/{history_id}", response_model=CourseSettingsOut,
             operation_id="course_settings_restore")
def restore_course(request: Request, history_id: int, access: CourseInstructor):
    _restorable(request, history_id, scope="course", course_id=access.course.id)
    try:
        _service(request).restore(history_id, account_id=access.account_id)
    except (SettingsError, SettingsConflict, SettingsLocked) as e:
        raise settings_error(e) from None
    return _course_out(request, access.course.id)


def _restorable(request: Request, history_id: int, *, scope: str, course_id: int | None = None) -> None:
    """Only an entry of this scope (and of this course) can be restored here; others look unknown."""
    with Session(request.app.state.services.engine) as db:
        entry = db.get(ConfigHistory, history_id)
    if entry is None or entry.version is None or entry.scope != scope or \
            (scope == "course" and entry.course_id != course_id):
        raise HTTPException(status.HTTP_404_NOT_FOUND, "settings history entry not found")
