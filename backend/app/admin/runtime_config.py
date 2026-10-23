"""Runtime-editable config subset (design §9: admin config).

The dashboard may change: the routing threshold, the enabled checkers, the knowledge model, weak evidence,
the level thresholds, and the local model server (address and model name: the professor's own Ollama server,
G1-94). A change is validated, stored in `config_history`, and applied without a restart:
the settings object is replaced, and the learner model and the pipeline are rebuilt. The newest history row
is applied again at startup, so a change survives a restart.

The medical-safety and privacy checkers cannot be switched off from the dashboard (design §2: safety and
privacy rules never depend on configuration).
"""

from urllib.parse import urlparse

from fastapi import FastAPI
from pydantic import BaseModel, ConfigDict, Field
from sqlmodel import Session, col, select

from app.core.config import LevelsConfig, Settings
from app.core.registry import checkers, import_submodules, knowledge_models
from app.storage.models import ConfigHistory

REQUIRED_CHECKERS = ("medical_safety", "pii_leak", "profile_leak")


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
    import_submodules("app.verify.checkers")
    return checkers.names()


def available_knowledge_models() -> list[str]:
    import_submodules("app.learner.knowledge")
    return knowledge_models.names()


def current(settings: Settings) -> RuntimeConfig:
    return RuntimeConfig(
        routing_threshold=settings.routing.threshold,
        show_routing_progress=settings.routing.show_progress,
        checkers=list(settings.verify.checkers),
        knowledge=settings.learner.knowledge,
        weak_evidence=settings.learner.weak_evidence,
        levels=settings.learner.levels,
        local_llm_url=settings.ollama_url,
        local_llm_model=settings.llm.local.model,
    )


def validate(rc: RuntimeConfig) -> None:
    known = available_checkers()
    unknown = [c for c in rc.checkers if c not in known]
    if unknown:
        raise InvalidConfig(f"unknown checker(s): {', '.join(unknown)}")
    if len(set(rc.checkers)) != len(rc.checkers):
        raise InvalidConfig("a checker is listed twice")
    missing = [c for c in REQUIRED_CHECKERS if c not in rc.checkers]
    if missing:
        raise InvalidConfig(f"these checkers cannot be switched off: {', '.join(missing)}")
    if rc.knowledge not in available_knowledge_models():
        raise InvalidConfig(f"unknown knowledge model: {rc.knowledge}")
    if rc.local_llm_url is not None:
        url = urlparse(rc.local_llm_url.strip())
        if url.scheme not in ("http", "https") or not url.hostname:
            raise InvalidConfig("the local model server must be an http(s) address, e.g. http://10.0.0.5:11434")
    if rc.local_llm_model is not None and (not rc.local_llm_model.strip() or " " in rc.local_llm_model.strip()):
        raise InvalidConfig("the local model name must be one word, e.g. qwen3.5:9b")


def with_runtime(settings: Settings, rc: RuntimeConfig) -> Settings:
    """A copy of the settings with the runtime subset replaced (sections re-validated)."""
    routing = settings.routing.model_validate(
        {
            **settings.routing.model_dump(),
            "threshold": rc.routing_threshold,
            "show_progress": rc.show_routing_progress,
        }
    )
    verify = settings.verify.model_validate({**settings.verify.model_dump(), "checkers": rc.checkers})
    learner = settings.learner.model_validate(
        {
            **settings.learner.model_dump(),
            "knowledge": rc.knowledge,
            "weak_evidence": rc.weak_evidence,
            "levels": rc.levels.model_dump(),
        }
    )
    update = {"routing": routing, "verify": verify, "learner": learner}
    if rc.local_llm_url is not None:
        update["ollama_url"] = rc.local_llm_url.strip().rstrip("/")
    if rc.local_llm_model is not None and rc.local_llm_model.strip() != settings.llm.local.model:
        model = rc.local_llm_model.strip()
        llm = settings.llm.model_dump()
        if llm["understand"]["model"] == llm["local"]["model"]:  # the understand step follows the answer model
            llm["understand"]["model"] = model
        llm["local"]["model"] = model
        update["llm"] = settings.llm.model_validate(llm)
    return settings.model_copy(update=update)


def apply(app: FastAPI, rc: RuntimeConfig) -> None:
    """Swap in the new settings, then rebuild what was built from them (learner model, pipeline).

    Requests already running keep the objects they started with; the next request uses the new ones.
    """
    from app.pipeline.runner import build_runner

    services = app.state.services
    services.reconfigure(with_runtime(services.settings, rc))
    app.state.runner = build_runner(services)


def change(app: FastAPI, rc: RuntimeConfig, account_id: int | None) -> bool:
    """Validate, apply and record a change. Returns False when nothing changed (no history row)."""
    validate(rc)
    services = app.state.services
    before = current(services.settings)
    if before == rc:
        return False
    apply(app, rc)
    with Session(services.engine) as db:
        db.add(ConfigHistory(account_id=account_id, values=rc.model_dump(), previous=before.model_dump()))
        db.commit()
    return True


def history(engine, limit: int = 10) -> list[ConfigHistory]:
    with Session(engine) as db:
        return list(db.exec(select(ConfigHistory).order_by(col(ConfigHistory.id).desc()).limit(limit)).all())


def restore_latest(app: FastAPI) -> RuntimeConfig | None:
    """At startup: apply the newest stored change, if it is still valid (else keep config.yaml)."""
    rows = history(app.state.services.engine, limit=1)
    if not rows:
        return None
    try:
        rc = RuntimeConfig.model_validate(rows[0].values)
        validate(rc)
    except (ValueError, InvalidConfig):
        return None
    apply(app, rc)
    return rc
