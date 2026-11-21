"""The request's settings snapshot for pipeline steps (task Z5, course-structure.md section 6.2).

`ctx.settings` is built once when the request starts and never changes during it. Contexts built without it
(unit tests that call a step directly) fall back to the process's current settings.
"""
from app.core.schemas import RequestContext


def routing_threshold(ctx: RequestContext, services) -> float:
    return ctx.settings.routing_threshold if ctx.settings else services.settings.routing.threshold


def default_routing_method(ctx: RequestContext, services) -> str:
    return ctx.settings.default_routing_method if ctx.settings else services.settings.routing.default_method


def health_detail_policy(ctx: RequestContext, services) -> str:
    """The stricter of the course's privacy profile and config.yaml: local_only wins (task Z7)."""
    configured = services.settings.privacy.health_detail_policy
    profile = ctx.profile.health_detail_policy if ctx.profile else configured
    return "local_only" if "local_only" in (configured, profile) else "generalize"


def local_only(ctx: RequestContext) -> bool:
    """The course uses the local model only (course setting `local_only`)."""
    return bool(ctx.settings and ctx.settings.local_only)


def weak_evidence(ctx: RequestContext, services) -> bool:
    return ctx.settings.weak_evidence if ctx.settings else services.settings.learner.weak_evidence


def course_type(ctx: RequestContext) -> str | None:
    """The course type of the request (V19); None for contexts built without settings."""
    return ctx.settings.course_type if ctx.settings else None


def router_of(ctx: RequestContext, services) -> tuple[str, object]:
    """The router name and router for this request's course type: `routing.by_course_type` when it names one
    (V19), otherwise `routing.impl` and the shared router. Routing only proposes a target; the cloud gate in
    the generate step still decides what may leave the machine."""
    cfg = services.settings.routing
    kind = course_type(ctx)
    impl = cfg.by_course_type.get(kind) if kind else None
    routers = getattr(services, "type_routers", None) or {}
    if impl and impl != cfg.impl and kind in routers:
        return impl, routers[kind]
    return cfg.impl, services.router
