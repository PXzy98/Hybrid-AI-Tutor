"""Application metrics for Prometheus (task Z13): `GET /metrics` on the api container.

Not under `/api`, so the web proxy (deploy/Caddyfile, which forwards only `/api/*`) never serves it, and the
api publishes no host port: only containers of the stack (Prometheus) reach it. Labels are route templates
(`/api/v2/courses/{course_id}`), methods and status codes: never IDs, names or question text (privacy
invariant 1). Values are per process; with several uvicorn workers, scrape each one or sum them.
"""
import time

from prometheus_client import (
    CONTENT_TYPE_LATEST,
    CollectorRegistry,
    Counter,
    Gauge,
    Histogram,
    generate_latest,
)
from starlette.requests import Request
from starlette.responses import Response

REGISTRY = CollectorRegistry()
REQUESTS = Counter("tutor_http_requests_total", "HTTP requests by route template and status code",
                   ["method", "route", "status"], registry=REGISTRY)
LATENCY = Histogram("tutor_http_request_duration_seconds", "HTTP request duration by route template",
                    ["method", "route"], registry=REGISTRY,
                    buckets=(0.01, 0.05, 0.1, 0.25, 0.5, 1, 2.5, 5, 10, 30, 60, 120))
COMPONENT_VERSION = Gauge("tutor_component_version", "System settings version the component set runs",
                          registry=REGISTRY)
CONTENT_VERSION = Gauge("tutor_content_version", "Content version of the served course", registry=REGISTRY)


def _route(request: Request) -> str:
    """The route template of the request, e.g. /api/v2/courses/{course_id}; "unmatched" for unknown paths.

    Built from the full path and the path parameters (an included router's route knows only its own part of
    the path)."""
    if request.scope.get("route") is None:
        return "unmatched"
    by_value = {str(v): k for k, v in (request.scope.get("path_params") or {}).items()}
    return "/".join(f"{{{by_value[s]}}}" if s in by_value else s for s in request.url.path.split("/"))


async def middleware(request: Request, call_next):
    if request.url.path == "/metrics":
        return await call_next(request)
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        route = _route(request)
        REQUESTS.labels(request.method, route, str(status)).inc()
        LATENCY.labels(request.method, route).observe(time.perf_counter() - start)


def metrics(request: Request) -> Response:
    services = getattr(request.app.state, "services", None)
    if services is not None and services.components is not None:
        COMPONENT_VERSION.set(services.components.version)
        manager = services.component_manager
        if manager is not None and manager.content_version is not None:
            CONTENT_VERSION.set(manager.content_version)
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)
