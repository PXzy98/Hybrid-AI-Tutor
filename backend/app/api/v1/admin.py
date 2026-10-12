"""Instructor dashboard API (design §3, §8.3, §9). Every route requires the instructor.

Aggregates and system data only: no route returns one student's learning data
(learner.instructor_individual_view stays false). Student accounts: admin_students.py.
"""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, UploadFile, status
from pydantic import BaseModel

from app.admin import runtime_config
from app.admin.logs import LogPage, log_page
from app.admin.materials import (
    MAX_BYTES,
    ContentStatus,
    MaterialError,
    UploadResult,
    content_status,
    store_upload,
)
from app.admin.runtime_config import InvalidConfig, RuntimeConfig
from app.admin.summary import ClassSummary, class_summary
from app.api.deps import ServicesDep
from app.auth.deps import Instructor

router = APIRouter(prefix="/admin", tags=["admin: dashboard"])


class ConfigChange(BaseModel):
    changed_at: datetime
    changed: list[str]  # names of the fields that changed


class ConfigOptions(BaseModel):
    checkers: list[str]
    required_checkers: list[str]
    knowledge_models: list[str]


class AdminConfig(BaseModel):
    values: RuntimeConfig
    options: ConfigOptions
    history: list[ConfigChange]


def _admin_config(services) -> AdminConfig:
    changes = [ConfigChange(changed_at=h.changed_at,
                            changed=sorted(k for k in h.values if h.values.get(k) != h.previous.get(k)))
               for h in runtime_config.history(services.engine)]
    return AdminConfig(values=runtime_config.current(services.settings),
                       options=ConfigOptions(checkers=runtime_config.available_checkers(),
                                             required_checkers=list(runtime_config.REQUIRED_CHECKERS),
                                             knowledge_models=runtime_config.available_knowledge_models()),
                       history=changes)


def _known_topic(services, topic: str) -> None:
    if services.content.topic(topic) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown topic")


@router.get("/config", response_model=AdminConfig)
def get_config(_: Instructor, services: ServicesDep):
    return _admin_config(services)


@router.put("/config", response_model=AdminConfig)
def put_config(body: RuntimeConfig, user: Instructor, request: Request):
    """Applied at once (the next /ask uses it) and stored in config_history."""
    try:
        runtime_config.change(request.app, body, user.account_id)
    except InvalidConfig as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    return _admin_config(request.app.state.services)


@router.get("/class-summary", response_model=ClassSummary)
def get_class_summary(topic: str, _: Instructor, services: ServicesDep):
    _known_topic(services, topic)
    return class_summary(services.engine, services.learner, services.content, topic,
                         services.settings.learner.class_summary_min_group)


@router.get("/logs", response_model=LogPage)
def get_logs(_: Instructor, services: ServicesDep, page: int = 1, page_size: int = 20,
             topic: str | None = None):
    return log_page(services.engine, page, page_size, topic)


@router.get("/content", response_model=ContentStatus)
def get_content(_: Instructor, services: ServicesDep):
    topics = list(dict.fromkeys(services.settings.topics() + services.content.topics()))
    return content_status(services.content, topics, services.settings.materials_dir)


@router.post("/topics/{topic}/materials", response_model=UploadResult, status_code=status.HTTP_201_CREATED)
async def upload_material(topic: str, _: Instructor, services: ServicesDep,
                          file: UploadFile, replace: bool = False):
    _known_topic(services, topic)
    data = await file.read(MAX_BYTES + 1)
    try:
        return await store_upload(services.settings.materials_dir(topic), file.filename or "", data,
                                  services.retriever, topic, replace)
    except MaterialError as e:
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_CONTENT, str(e)) from None
    except FileExistsError:
        raise HTTPException(status.HTTP_409_CONFLICT,
                            "a file with this name exists (use replace=true)") from None
