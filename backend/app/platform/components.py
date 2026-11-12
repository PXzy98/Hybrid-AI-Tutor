"""Live component switch (task Z5, course-structure.md section 6.5).

A *component set* is everything that has to be rebuilt when a system setting changes: the effective
`Settings` (config + system overrides), the learner model (knowledge model, weak evidence, level
thresholds), the local model clients and the pipeline runner (checkers, routing method). It sits behind
one reference, `Services.components`; switching is one assignment, so a request that already started
finishes with the set it began with.

Every process runs `ComponentManager.sync()` every `limits.settings.poll_seconds`:
1. heartbeat in `process_status` (`component_version` = the version it runs);
2. if the system settings version is newer, build the new set in the background and swap it in;
   a build that fails keeps the old set and reports the error;
3. help finish the change: when every live process (heartbeat within 3 × poll) runs the target version the
   row becomes `applied`; an error or the timeout rolls it back (a new version with the old values).
The process that saved the change syncs at once, so a single process applies it before the request returns.

The same loop reloads the served course's content when its `course.content_version` changes (a content edit
through API v2, task Z9): the new `ContentStore` and a component set built on it are swapped in.
"""
import logging
import os
import socket
import threading
import uuid
from dataclasses import dataclass
from datetime import timedelta
from typing import TYPE_CHECKING

from sqlmodel import Session, select

from app.core.config import Settings
from app.platform import course_scope
from app.storage.models import Course, ProcessStatus, utcnow

if TYPE_CHECKING:
    from app.core.services import Services

log = logging.getLogger("app.components")


@dataclass
class Components:
    version: int
    settings: Settings
    learner: object
    local_llm: object
    understand_llm: object
    runner: object | None = None


_COMPONENT_ATTRS = ("settings", "learner", "local_llm", "understand_llm")


class BoundServices:
    """What the steps of one runner see: the component attributes of *their* set, everything else (engine,
    retriever, cloud client, ...) read through to the shared Services object. Inside a course scope
    (app.platform.course_scope, API v2) the content, learner model, retriever and conversations are the
    request's course."""

    def __init__(self, services: "Services", components: Components) -> None:
        object.__setattr__(self, "_services", services)
        object.__setattr__(self, "components", components)

    def __getattr__(self, name: str):
        if name in course_scope.SCOPED:
            scope = course_scope.current()
            if scope is not None:
                return getattr(scope, name)
        if name in _COMPONENT_ATTRS:
            return getattr(self.components, name)
        return getattr(self._services, name)

    def __setattr__(self, name: str, value) -> None:
        if name in _COMPONENT_ATTRS:
            setattr(self.components, name, value)
        else:
            setattr(self._services, name, value)


def component_settings(base: Settings, values: dict) -> Settings:
    """config.yaml/.env settings with the system overrides applied (null fields keep the base value)."""
    routing, verify = base.routing.model_dump(), base.verify.model_dump()
    learner, llm = base.learner.model_dump(), base.llm.model_dump()
    if values.get("default_routing_method"):
        routing["default_method"] = values["default_routing_method"]
    if values.get("checkers") is not None:
        verify["checkers"] = list(values["checkers"])
    if values.get("knowledge_model"):
        learner["knowledge"] = values["knowledge_model"]
    if values.get("weak_evidence") is not None:
        learner["weak_evidence"] = values["weak_evidence"]
    for name, key in (("level_basic_below", "basic_below"), ("level_advanced_above", "advanced_above"),
                      ("level_hysteresis", "hysteresis")):
        if values.get(name) is not None:
            learner["levels"][key] = values[name]
    update = {}
    if values.get("local_llm_url"):
        update["ollama_url"] = values["local_llm_url"]
    if values.get("local_llm_model") and values["local_llm_model"] != llm["local"]["model"]:
        if llm["understand"]["model"] == llm["local"]["model"]:  # understand follows the answer model
            llm["understand"]["model"] = values["local_llm_model"]
        llm["local"]["model"] = values["local_llm_model"]
    update.update(routing=base.routing.model_validate(routing), verify=base.verify.model_validate(verify),
                  learner=base.learner.model_validate(learner), llm=base.llm.model_validate(llm))
    return base.model_copy(update=update)


class ComponentManager:
    def __init__(self, services: "Services", base: Settings) -> None:
        self.services = services
        self.base = base
        limits = base.limits.settings
        self.poll_s, self.timeout_s = limits.poll_seconds, limits.apply_timeout_seconds
        self.kind = "api"  # api | worker (process_status.kind; the worker sets it)
        self.process_id = f"{socket.gethostname()}-{os.getpid()}-{uuid.uuid4().hex[:6]}"
        self.error: str | None = None
        self._stop = threading.Event()
        self._thread: threading.Thread | None = None
        self._sync_lock = threading.Lock()
        self._values: dict = {}  # the system values the current component set was built from
        self.content_version: int | None = None  # of the served course, as loaded

    # ---------------------------------------------------------------------------------- building
    def build(self, version: int, values: dict) -> Components:
        from app.learner.facade import build_learner_model
        from app.llm.factory import build_llm_clients
        from app.pipeline.runner import build_runner

        settings = component_settings(self.base, values)
        current = getattr(self.services, "components", None)
        if current is not None and (current.settings.ollama_url, current.settings.llm.local,
                                    current.settings.llm.understand) == (
                settings.ollama_url, settings.llm.local, settings.llm.understand):
            local, understand = current.local_llm, current.understand_llm  # same server: keep the clients
        else:
            local, _, understand = build_llm_clients(settings)
        new = Components(version=version, settings=settings,
                         learner=build_learner_model(settings, self.services.engine, self.services.content),
                         local_llm=local, understand_llm=understand)
        new.runner = build_runner(BoundServices(self.services, new))  # steps bound to this set
        return new

    def initial(self) -> Components:
        values, version, _ = self.services.settings_service.system_values()
        self.content_version = self._content_version()
        built = self.build(version, values)
        self._values = values
        return built

    def _content_version(self) -> int | None:
        with Session(self.services.engine) as db:
            course = db.get(Course, self.services.content.course_id)
        return course.content_version if course else None

    def _sync_content(self) -> None:
        """Reload the served course's content after an edit; a failure keeps the old content (reported)."""
        from app.catalog import load_course_content

        version = self._content_version()
        if version is None or version == self.content_version:
            return
        old = self.services.content
        try:
            self.services.content = load_course_content(self.services.engine, old.course_id)
            self.services.components = self.build(self.services.components.version, self._values)
            self.content_version = version
            log.info("course content reloaded (content version %s)", version)
        except Exception as e:  # noqa: BLE001 - keep serving the old content
            self.services.content = old
            self.error = f"content reload: {type(e).__name__}: {e}"[:300]
            log.warning("could not reload the course content: %s", self.error)

    # ------------------------------------------------------------------------------------- syncing
    def sync(self) -> None:
        """One round of the loop; also called right after a save in this process."""
        with self._sync_lock:
            service = self.services.settings_service
            values, version, state = service.system_values()
            if version != self.services.components.version:
                try:
                    self.services.components = self.build(version, values)
                    self._values = values
                    self.error = None
                    log.info("components switched to settings version %s", version)
                except Exception as e:  # noqa: BLE001 - keep serving with the old set, report the reason
                    self.error = f"{type(e).__name__}: {e}"[:300]
                    log.warning("could not build components for version %s: %s", version, self.error)
            self._sync_content()
            self._heartbeat()
            if state == "applying":
                live, errors = self._live_processes()
                service.finish_apply(target=version, live=live, errors=errors, timeout_s=self.timeout_s)

    def _heartbeat(self) -> None:
        with Session(self.services.engine) as db:
            row = db.get(ProcessStatus, self.process_id) or ProcessStatus(process_id=self.process_id)
            row.last_seen, row.error, row.kind = utcnow(), self.error, self.kind
            row.component_version = self.services.components.version
            db.add(row)
            db.commit()

    def _live_processes(self) -> tuple[list[int], list[str]]:
        since = utcnow() - timedelta(seconds=3 * self.poll_s)
        with Session(self.services.engine) as db:
            rows = db.exec(select(ProcessStatus).where(ProcessStatus.last_seen >= since)).all()
        return [r.component_version for r in rows], [r.error for r in rows if r.error]

    # ------------------------------------------------------------------------------------ the loop
    def start(self) -> None:
        if self._thread is None:
            self._thread = threading.Thread(target=self._loop, name="components", daemon=True)
            self._thread.start()

    def stop(self) -> None:
        self._stop.set()
        if self._thread is not None:
            self._thread.join(timeout=5)
        with Session(self.services.engine) as db:  # leave the set of live processes at once
            row = db.get(ProcessStatus, self.process_id)
            if row is not None:
                db.delete(row)
                db.commit()

    def _loop(self) -> None:
        while not self._stop.wait(self.poll_s):
            try:
                self.sync()
            except Exception:  # noqa: BLE001 - the loop must survive a database hiccup
                log.exception("component sync failed")
