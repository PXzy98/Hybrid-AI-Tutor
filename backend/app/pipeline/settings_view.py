"""The request's settings snapshot for pipeline steps (task Z5, course-structure.md section 6.2).

`ctx.settings` is built once when the request starts and never changes during it. Contexts built without it
(unit tests that call a step directly) fall back to the process's current settings.
"""
from app.core.schemas import RequestContext


def routing_threshold(ctx: RequestContext, services) -> float:
    return ctx.settings.routing_threshold if ctx.settings else services.settings.routing.threshold


def default_routing_method(ctx: RequestContext, services) -> str:
    return ctx.settings.default_routing_method if ctx.settings else services.settings.routing.default_method


def local_only(ctx: RequestContext) -> bool:
    """The course uses the local model only (course setting `local_only`)."""
    return bool(ctx.settings and ctx.settings.local_only)


def weak_evidence(ctx: RequestContext, services) -> bool:
    return ctx.settings.weak_evidence if ctx.settings else services.settings.learner.weak_evidence
