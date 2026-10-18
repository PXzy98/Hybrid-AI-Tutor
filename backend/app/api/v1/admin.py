"""Instructor settings added on the RAG branch; account routes stay unchanged."""
from datetime import datetime

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel

from app.admin import runtime_config
from app.admin.runtime_config import InvalidConfig, RuntimeConfig
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
