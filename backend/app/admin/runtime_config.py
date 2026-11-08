"""API v1 dashboard config, kept as it was (rule 15) on top of the settings layers of task Z5.

The v1 dashboard edits one flat object. Since Z5 it is stored as layered settings: the routing threshold and
progress display belong to the demo course (`course_settings`), the checkers, knowledge model, weak evidence,
level thresholds and local model server to `system_settings`. A component change is applied live in every
process (`app.platform.components`); the v1 PUT keeps its "applied at once" behaviour in this process.
"""

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, col, select

from app.core.config import LevelsConfig
from app.platform.settings import REQUIRED_CHECKERS, SettingsError, _known_checkers, _known_knowledge_models
from app.storage.models import ConfigHistory

__all__ = ["REQUIRED_CHECKERS", "RuntimeConfig", "InvalidConfig", "available_checkers",
           "available_knowledge_models", "current", "change", "history"]


class RuntimeConfig(BaseModel):
    model_config = ConfigDict(extra="forbid")

    routing_threshold: float = Field(ge=0, le=1)
    show_routing_progress: bool = True
    checkers: list[str]
    knowledge: str
    weak_evidence: bool
    levels: LevelsConfig
    # None keeps the value from .env / config.yaml (history rows written before G1-94 have no such fields)
    local_llm_url: str | None = Field(None, max_length=300)
    local_llm_model: str | None = Field(None, max_length=100)


class InvalidConfig(ValueError):
    pass


def available_checkers() -> list[str]:
    return _known_checkers()


def available_knowledge_models() -> list[str]:
    return _known_knowledge_models()


def current(services) -> RuntimeConfig:
    eff, s = services.effective(), services.settings
    return RuntimeConfig(
        routing_threshold=eff.routing_threshold,
        show_routing_progress=eff.show_routing_progress,
        checkers=list(eff.checkers),
        knowledge=eff.knowledge_model,
        weak_evidence=eff.weak_evidence,
        levels=LevelsConfig(basic_below=eff.level_basic_below, advanced_above=eff.level_advanced_above,
                            hysteresis=eff.level_hysteresis),
        local_llm_url=s.ollama_url,
        local_llm_model=s.llm.local.model,
    )


def change(app: FastAPI, rc: RuntimeConfig, account_id: int | None) -> bool:
    """Validate and store a v1 change in the settings layers. Returns False when nothing changed."""
    services = app.state.services
    before = current(services)
    if before == rc:
        return False
    service, course_id = services.settings_service, services.content.course_id
    system, system_version, _ = service.system_values()
    course, course_version = service.course_values(course_id)
    # only the fields that changed are stored, so untouched ones keep following config.yaml
    mapping = {"checkers": ("system", "checkers"), "knowledge": ("system", "knowledge_model"),
               "weak_evidence": ("system", "weak_evidence"), "local_llm_url": ("system", "local_llm_url"),
               "local_llm_model": ("system", "local_llm_model"),
               "routing_threshold": ("course", "routing_threshold"),
               "show_routing_progress": ("course", "show_routing_progress")}
    for v1_name, (scope, name) in mapping.items():
        new = getattr(rc, v1_name)
        if new is not None and new != getattr(before, v1_name):
            (system if scope == "system" else course)[name] = new
    for v1_name, name in (("basic_below", "level_basic_below"), ("advanced_above", "level_advanced_above"),
                          ("hysteresis", "level_hysteresis")):
        if getattr(rc.levels, v1_name) != getattr(before.levels, v1_name):
            system[name] = getattr(rc.levels, v1_name)
    try:
        service.save_system(system, expected_version=system_version, account_id=account_id)
        service.save_course(course_id, course, expected_version=course_version, account_id=account_id)
    except SettingsError as e:
        raise InvalidConfig(str(e)) from None
    services.component_manager.sync()  # this process switches before the response (v1: "applied at once")
    return True


def history(engine, limit: int = 10) -> list[ConfigHistory]:
    """The dashboard's change list: system and course changes, newest first."""
    with Session(engine) as db:
        return list(db.exec(select(ConfigHistory).order_by(col(ConfigHistory.id).desc()).limit(limit)).all())
