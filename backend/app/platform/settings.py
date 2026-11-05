"""Effective settings of a course (course-structure.md section 6).

Z1 stand-in: there are no settings tables yet, so every course gets the values of config.yaml. Z5 replaces
the body of `effective_settings` with the versioned read (one query + version-keyed cache); the signature
stays.
"""
from app.core.config import Settings, get_settings
from app.core.schemas import EffectiveSettings


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


def effective_settings(course_id: int, settings: Settings | None = None) -> EffectiveSettings:
    return from_config(course_id, settings or get_settings())
