"""Settings layers (task Z5, course-structure.md section 6).

Three layers, merged per course: `course_settings` → `system_settings` → `config.yaml`. Every stored field
is nullable (null = next layer), so a new config default applies wherever nothing was set, and nothing a
user saved is ever overwritten by a deploy.

- **Read** (`effective_settings(course_id)`): one query returns both rows with their versions; the merged,
  frozen `EffectiveSettings` is cached per process by `(course_id, course_version, system_version)`, so a
  change is seen by every process on its next request. No time-based expiry.
- **Write** (`save_system`, `save_course`): validates the whole object, then in one transaction updates the
  row only if the client's `version` still matches (else `SettingsConflict`, HTTP 409), increments
  `version`, writes `config_history` and `audit_log`. A row that is applying a component change refuses
  writes (`SettingsLocked`, HTTP 423).
- **Components** (system fields that need new objects: knowledge model, checkers, routing method, local
  model server) are switched live in every process by `app.platform.components`; saving one sets
  `apply_state = applying` until all live processes run the new version.
- **Restore** writes an earlier `config_history` entry back as a new change.

Before `configure()` is called (scripts, unit tests without the app), `effective_settings` returns the
config defaults, as the Z1 stand-in did.
"""
import logging
from dataclasses import dataclass, field
from datetime import timedelta
from threading import Lock

from sqlalchemy import Engine, select, text
from sqlmodel import Session

from app.core.config import Settings, get_settings
from app.core.schemas import EffectiveSettings
from app.storage.models import AuditLog, ConfigHistory, Course, CourseSettings, SystemSettings, utcnow

log = logging.getLogger("app.settings")

REQUIRED_CHECKERS = ("medical_safety", "pii_leak", "profile_leak")  # never switched off (privacy rule 4)
# fields that need a new component set (the learner model is built from the learner fields)
COMPONENT_FIELDS = ("checkers", "knowledge_model", "default_routing_method", "local_llm_url",
                    "local_llm_model", "weak_evidence", "level_basic_below", "level_advanced_above",
                    "level_hysteresis")
SYSTEM_FIELDS = ("checkers", "weak_evidence", "level_basic_below", "level_advanced_above", "level_hysteresis",
                 "knowledge_model", "default_routing_method", "local_llm_url", "local_llm_model",
                 "enabled_course_types")
COURSE_FIELDS = ("course_type", "visibility_mode", "local_only", "routing_preference", "routing_threshold",
                 "show_routing_progress", "usage_questions_per_minute", "usage_questions_per_day",
                 "usage_cloud_calls_per_day")
def course_types() -> list[str]:
    """The course types are the privacy profiles (app/privacy/profiles/*.yaml, task Z7)."""
    from app.privacy.profiles import profile_names

    return profile_names()


class SettingsError(ValueError):
    """Invalid settings values (HTTP 422)."""


class SettingsConflict(RuntimeError):
    """The row changed since the client read it (HTTP 409)."""


class SettingsLocked(RuntimeError):
    """A component change of this row is still being applied (HTTP 423, code settings_applying)."""


def from_config(course_id: int, settings: Settings) -> EffectiveSettings:
    """The config-file defaults, as used for a course that has no settings of its own."""
    levels = settings.learner.levels
    return EffectiveSettings(
        course_id=course_id,
        routing_threshold=settings.routing.threshold,
        show_routing_progress=settings.routing.show_progress,
        weak_evidence=settings.learner.weak_evidence,
        level_basic_below=levels.basic_below,
        level_advanced_above=levels.advanced_above,
        level_hysteresis=levels.hysteresis,
        knowledge_model=settings.learner.knowledge,
        default_routing_method=settings.routing.default_method,
        checkers=tuple(settings.verify.checkers),
    )


# ------------------------------------------------------------------------------------------- validation
def _known_checkers() -> list[str]:
    from app.core.registry import checkers, import_submodules

    import_submodules("app.verify.checkers")
    return checkers.names()


def _known_knowledge_models() -> list[str]:
    from app.core.registry import import_submodules, knowledge_models

    import_submodules("app.learner.knowledge")
    return knowledge_models.names()


def _between(name: str, value, low: float, high: float) -> None:
    if value is not None and not (isinstance(value, int | float) and low <= value <= high):
        raise SettingsError(f"{name} must be between {low} and {high}")


def validate_system(values: dict) -> dict:
    unknown = set(values) - set(SYSTEM_FIELDS)
    if unknown:
        raise SettingsError(f"unknown system setting(s): {', '.join(sorted(unknown))}")
    out = dict(values)
    if out.get("checkers") is not None:
        names = list(out["checkers"])
        bad = [c for c in names if c not in _known_checkers()]
        if bad:
            raise SettingsError(f"unknown checker(s): {', '.join(bad)}")
        if len(set(names)) != len(names):
            raise SettingsError("a checker is listed twice")
        missing = [c for c in REQUIRED_CHECKERS if c not in names]
        if missing:
            raise SettingsError(f"these checkers cannot be switched off: {', '.join(missing)}")
        out["checkers"] = names
    if out.get("knowledge_model") is not None and out["knowledge_model"] not in _known_knowledge_models():
        raise SettingsError(f"unknown knowledge model: {out['knowledge_model']}")
    if out.get("default_routing_method") not in (None, "lr", "svm"):
        raise SettingsError("default_routing_method must be lr or svm")
    for name in ("level_basic_below", "level_advanced_above"):
        _between(name, out.get(name), 0, 1)
    _between("level_hysteresis", out.get("level_hysteresis"), 0, 0.2)
    if out.get("weak_evidence") is not None and not isinstance(out["weak_evidence"], bool):
        raise SettingsError("weak_evidence must be true or false")
    if out.get("local_llm_url") is not None:
        from urllib.parse import urlparse

        url = urlparse(str(out["local_llm_url"]).strip())
        if url.scheme not in ("http", "https") or not url.hostname:
            raise SettingsError("the local model server must be an http(s) address, e.g. http://10.0.0.5:11434")
        out["local_llm_url"] = str(out["local_llm_url"]).strip().rstrip("/")
    if out.get("local_llm_model") is not None:
        model = str(out["local_llm_model"]).strip()
        if not model or " " in model:
            raise SettingsError("the local model name must be one word, e.g. qwen3.5:9b")
        out["local_llm_model"] = model
    if out.get("enabled_course_types") is not None and \
            not set(out["enabled_course_types"]) <= set(course_types()):
        raise SettingsError("unknown course type")
    return out


def validate_course(values: dict) -> dict:
    unknown = set(values) - set(COURSE_FIELDS)
    if unknown:
        raise SettingsError(f"unknown course setting(s): {', '.join(sorted(unknown))}")
    out = dict(values)
    if out.get("course_type") is not None and out["course_type"] not in course_types():
        raise SettingsError("unknown course type")
    if out.get("visibility_mode") not in (None, "A", "B"):
        raise SettingsError("visibility_mode must be A or B")
    if out.get("routing_preference") not in (None, "default", "prefer_local", "prefer_cloud"):
        raise SettingsError("unknown routing preference")
    _between("routing_threshold", out.get("routing_threshold"), 0, 1)
    for name in ("local_only", "show_routing_progress"):
        if out.get(name) is not None and not isinstance(out[name], bool):
            raise SettingsError(f"{name} must be true or false")
    for name in ("usage_questions_per_minute", "usage_questions_per_day", "usage_cloud_calls_per_day"):
        if out.get(name) is not None and (not isinstance(out[name], int) or out[name] < 0):
            raise SettingsError(f"{name} must be a non-negative integer")
    return out


# ------------------------------------------------------------------------------------------- the service
_VERSIONS = text(
    "SELECT (SELECT version FROM system_settings WHERE id = 1),"
    " (SELECT version FROM course_settings WHERE course_id = :c),"
    " (SELECT course_type FROM course WHERE id = :c), (SELECT visibility_mode FROM course WHERE id = :c)")

def _values(row, fields) -> dict:
    return {f: getattr(row, f) for f in fields} if row is not None else dict.fromkeys(fields)


@dataclass
class SettingsService:
    engine: Engine
    base: Settings
    _cache: dict = field(default_factory=dict)
    _lock: Lock = field(default_factory=Lock)

    # ---------------------------------------------------------------------------------------- read
    def versions(self, course_id: int) -> tuple:
        """One query: both rows of the course (missing rows read as None)."""
        with Session(self.engine) as db:
            system = db.get(SystemSettings, 1)
            course = db.get(CourseSettings, course_id)
            course_row = db.get(Course, course_id)
            db.expunge_all()
        return system, course, course_row

    def effective(self, course_id: int) -> EffectiveSettings:
        """One round trip for the versions; the rows are read only when the cache has no entry for them."""
        with self.engine.connect() as conn:
            key = (course_id, *conn.execute(_VERSIONS, {"c": course_id}).one())
        with self._lock:
            hit = self._cache.get(key)
        if hit is not None:
            return hit
        merged = self.merge(course_id, *self.versions(course_id))
        with self._lock:
            if len(self._cache) > 1000:
                self._cache.clear()
            self._cache[key] = merged
        return merged

    def merge(self, course_id: int, system, course, course_row=None) -> EffectiveSettings:
        """course → system → config.yaml; invalid stored values are ignored with a warning (design §6.3)."""
        base = from_config(course_id, self.base).model_dump()
        if course_row is not None:  # set when the course was created
            base["course_type"], base["visibility_mode"] = course_row.course_type, course_row.visibility_mode
        layers = []
        if system is not None:
            layers.append(("system", validate_system, _values(system, SYSTEM_FIELDS)))
        if course is not None:
            layers.append(("course", validate_course, _values(course, COURSE_FIELDS)))
        for scope, check, values in layers:
            for name, value in values.items():
                if value is None or name not in base:
                    continue
                try:
                    check({name: value})
                except SettingsError as e:
                    log.warning("ignoring invalid %s setting %s: %s", scope, name, e)
                    continue
                base[name] = tuple(value) if name == "checkers" else value
        base["course_version"] = course.version if course else 0
        base["system_version"] = system.version if system else 0
        return EffectiveSettings(**base)

    def system_values(self) -> tuple[dict, int, str]:
        with Session(self.engine) as db:
            row = db.get(SystemSettings, 1)
            state = row.apply_state if row else "applied"
            return _values(row, SYSTEM_FIELDS), (row.version if row else 0), state

    def course_values(self, course_id: int) -> tuple[dict, int]:
        with Session(self.engine) as db:
            row = db.get(CourseSettings, course_id)
            return _values(row, COURSE_FIELDS), (row.version if row else 0)

    # --------------------------------------------------------------------------------------- write
    def check_levels(self, values: dict) -> None:
        """The level thresholds as they will apply (null = config default) must still be ordered."""
        from app.core.config import LevelsConfig

        base = self.base.learner.levels
        try:
            LevelsConfig(basic_below=base.basic_below if values.get("level_basic_below") is None
                         else values["level_basic_below"],
                         advanced_above=base.advanced_above if values.get("level_advanced_above") is None
                         else values["level_advanced_above"],
                         hysteresis=base.hysteresis if values.get("level_hysteresis") is None
                         else values["level_hysteresis"])
        except ValueError as e:
            raise SettingsError("need 0 < level_basic_below < level_advanced_above < 1") from e

    def save_system(self, values: dict, *, expected_version: int, account_id: int | None,
                    action: str = "settings.system.update") -> int:
        """Store the system settings (all fields; null = config default). Returns the new version."""
        values = validate_system({**dict.fromkeys(SYSTEM_FIELDS), **values})
        self.check_levels(values)
        with Session(self.engine) as db:
            db.exec(text("SELECT pg_advisory_xact_lock(590203)"))
            row = db.get(SystemSettings, 1, with_for_update=True) or SystemSettings(id=1, version=0)
            if row.apply_state == "applying":
                raise SettingsLocked("a change is still being applied")
            if row.version != expected_version:
                raise SettingsConflict(f"the settings changed (version {row.version}); reload and try again")
            before = _values(row, SYSTEM_FIELDS)
            if before == values:
                return row.version
            for name, value in values.items():
                setattr(row, name, value)
            row.version += 1
            row.updated_at, row.updated_by = utcnow(), account_id
            if any(before[f] != values[f] for f in COMPONENT_FIELDS):
                row.apply_state, row.apply_target_version = "applying", row.version
                row.apply_started_at, row.apply_error = utcnow(), None
                row.previous_values = before
            else:
                row.apply_state = "applied"
            db.add(row)
            db.add(ConfigHistory(account_id=account_id, scope="system", version=row.version, values=values,
                                 previous=before))
            db.add(AuditLog(account_id=account_id, action=action, target="system",
                            details={"version": row.version, "changed": sorted(k for k in values
                                                                               if values[k] != before[k])}))
            db.commit()
            return row.version

    def save_course(self, course_id: int, values: dict, *, expected_version: int, account_id: int | None,
                    action: str = "settings.course.update") -> int:
        values = validate_course({**dict.fromkeys(COURSE_FIELDS), **values})
        with Session(self.engine) as db:
            # a per-course lock: FOR UPDATE cannot lock the row before it exists (first save)
            db.exec(text("SELECT pg_advisory_xact_lock(590204, :c)").bindparams(c=course_id))
            if db.get(Course, course_id) is None:
                raise SettingsError(f"no course {course_id}")
            row = db.get(CourseSettings, course_id, with_for_update=True)
            row = row or CourseSettings(course_id=course_id, version=0)
            if row.apply_state == "applying":
                raise SettingsLocked("a change is still being applied")
            if row.version != expected_version:
                raise SettingsConflict(f"the settings changed (version {row.version}); reload and try again")
            before = _values(row, COURSE_FIELDS)
            if before == values:
                return row.version
            for name, value in values.items():
                setattr(row, name, value)
            row.version += 1
            row.updated_at, row.updated_by, row.apply_state = utcnow(), account_id, "applied"
            db.add(row)
            db.add(ConfigHistory(account_id=account_id, scope="course", course_id=course_id,
                                 version=row.version, values=values, previous=before))
            db.add(AuditLog(account_id=account_id, action=action, target=f"course:{course_id}",
                            details={"version": row.version, "changed": sorted(k for k in values
                                                                               if values[k] != before[k])}))
            db.commit()
            return row.version

    def history(self, *, scope: str, course_id: int | None = None, limit: int = 20) -> list[ConfigHistory]:
        with Session(self.engine) as db:
            q = select(ConfigHistory).where(ConfigHistory.scope == scope, ConfigHistory.version.is_not(None))
            if scope == "course":
                q = q.where(ConfigHistory.course_id == course_id)
            return list(db.exec(q.order_by(ConfigHistory.id.desc()).limit(limit)).scalars())

    def restore(self, history_id: int, *, account_id: int | None) -> int:
        """Write an earlier change's values back as a new change (also audited)."""
        with Session(self.engine) as db:
            entry = db.get(ConfigHistory, history_id)
        if entry is None or entry.version is None:
            raise SettingsError("unknown settings history entry")
        if entry.scope == "system":
            _, version, _ = self.system_values()
            return self.save_system(entry.values, expected_version=version, account_id=account_id,
                                    action="settings.system.restore")
        _, version = self.course_values(entry.course_id)
        return self.save_course(entry.course_id, entry.values, expected_version=version,
                                account_id=account_id, action="settings.course.restore")

    # ------------------------------------------------------------------------- component apply (§6.5)
    def finish_apply(self, *, target: int, live: list[int], errors: list[str], timeout_s: float) -> str:
        """Called by the component loops: mark the change applied when every live process runs it, or roll it
        back on an error or timeout. Returns the row's apply_state afterwards."""
        with Session(self.engine) as db:
            db.exec(text("SELECT pg_advisory_xact_lock(590203)"))
            row = db.get(SystemSettings, 1, with_for_update=True)
            if row is None or row.apply_state != "applying" or row.apply_target_version != target:
                return row.apply_state if row else "applied"
            started = row.apply_started_at or utcnow()
            timed_out = utcnow() - started > timedelta(seconds=timeout_s)
            if not errors and live and all(v >= target for v in live):
                row.apply_state = "applied"
            elif errors or timed_out:
                reason = errors[0] if errors else f"not all processes were ready within {timeout_s:.0f} s"
                previous = row.previous_values or {}
                for name in SYSTEM_FIELDS:
                    setattr(row, name, previous.get(name))
                row.version += 1  # the rollback is a new version, so switched processes build the old set
                row.apply_state, row.apply_error, row.apply_target_version = "failed", reason, None
                db.add(ConfigHistory(scope="system", version=row.version, values=previous,
                                     previous=_values(row, SYSTEM_FIELDS)))
                db.add(AuditLog(action="settings.system.rollback", target="system",
                                details={"version": row.version, "reason": reason[:200]}))
            else:
                return "applying"
            db.add(row)
            db.commit()
            return row.apply_state


# ------------------------------------------------------------------------------------------ module API
_service: SettingsService | None = None


def configure(service: SettingsService | None) -> None:
    """Called when the app starts (build_services)."""
    global _service
    _service = service


def settings_service() -> SettingsService | None:
    return _service


def effective_settings(course_id: int, settings: Settings | None = None) -> EffectiveSettings:
    if settings is not None or _service is None:
        return from_config(course_id, settings or get_settings())
    return _service.effective(course_id)


def migrate_v1_history(service: SettingsService, demo_course_id: int) -> bool:
    """First start after Z5: the newest v1/v3 dashboard change (config_history without a version) becomes
    the system row and the demo course row, so nothing set before is lost (design §6.3)."""
    with Session(service.engine) as db:
        if db.get(SystemSettings, 1) is not None:
            return False
        legacy = db.exec(select(ConfigHistory).where(ConfigHistory.version.is_(None))
                         .order_by(ConfigHistory.id.desc()).limit(1)).scalars().first()
    if legacy is None:
        return False
    v = legacy.values or {}
    levels = v.get("levels") or {}
    system = {"checkers": v.get("checkers"), "knowledge_model": v.get("knowledge"),
              "weak_evidence": v.get("weak_evidence"), "level_basic_below": levels.get("basic_below"),
              "level_advanced_above": levels.get("advanced_above"),
              "level_hysteresis": levels.get("hysteresis"),
              "local_llm_url": v.get("local_llm_url"), "local_llm_model": v.get("local_llm_model")}
    course = {"routing_threshold": v.get("routing_threshold"),
              "show_routing_progress": v.get("show_routing_progress")}
    try:
        service.save_system(system, expected_version=0, account_id=legacy.account_id,
                            action="settings.system.migrate_v3")
        with Session(service.engine) as db:  # applied at startup: no other process runs older components
            row = db.get(SystemSettings, 1)
            row.apply_state, row.apply_target_version = "applied", None
            db.add(row)
            db.commit()
        service.save_course(demo_course_id, course, expected_version=0, account_id=legacy.account_id,
                            action="settings.course.migrate_v3")
    except SettingsError as e:
        log.warning("the stored v3 settings were not migrated: %s", e)
        return False
    return True
