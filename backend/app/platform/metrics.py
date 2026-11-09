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
# every live api and worker process from process_status (their heartbeats): the worker serves no /metrics of
# its own, so this is how an alert sees a process left on another settings version (course-structure.md 6.5)
PROCESS_VERSION = Gauge("tutor_process_component_version", "Settings version each live process runs",
                        ["process", "kind"], registry=REGISTRY)


def _route(scope) -> str:
    """The route template of the request, e.g. /api/v2/courses/{course_id}; "unmatched" for unknown paths.

    By position, not by value (/courses/1/modules/1 has two parameters with the same value): the matched
    route's own path is the end of the request path (a route of an included router knows only its own part),
    so its segments replace the last segments of the request path."""
    own = getattr(scope.get("route"), "path", None)
    if not own:
        return "unmatched"
    full, tail = scope["path"].strip("/").split("/"), own.strip("/").split("/")
    if len(tail) > len(full):
        return own
    return "/" + "/".join(full[:len(full) - len(tail)] + tail)


class MetricsMiddleware:
    """ASGI middleware: counts every request and times it until the last byte of the response is sent (a
    streamed answer is timed to its end, not to its first event)."""

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send):
        if scope["type"] != "http" or scope["path"] == "/metrics":
            await self.app(scope, receive, send)
            return
        start, state = time.perf_counter(), {"status": 500, "recorded": False}

        def record() -> None:
            if state["recorded"]:
                return
            state["recorded"] = True
            route, method = _route(scope), scope["method"]
            REQUESTS.labels(method, route, str(state["status"])).inc()
            LATENCY.labels(method, route).observe(time.perf_counter() - start)

        async def send_and_watch(message) -> None:
            if message["type"] == "http.response.start":
                state["status"] = message["status"]
            await send(message)
            if message["type"] == "http.response.body" and not message.get("more_body", False):
                record()

        try:
            await self.app(scope, receive, send_and_watch)
        finally:
            record()  # an error, or a client that went away before the end


def metrics(request: Request) -> Response:
    services = getattr(request.app.state, "services", None)
    if services is not None and services.components is not None:
        COMPONENT_VERSION.set(services.components.version)
        manager = services.component_manager
        if manager is not None and manager.content_version is not None:
            CONTENT_VERSION.set(manager.content_version)
        _process_versions(services)
    return Response(generate_latest(REGISTRY), media_type=CONTENT_TYPE_LATEST)


def _process_versions(services) -> None:
    """The settings version of every process with a recent heartbeat (3 x poll, as the apply check uses)."""
    from datetime import timedelta

    from sqlmodel import Session, select

    from app.storage.models import ProcessStatus, utcnow

    since = utcnow() - timedelta(seconds=3 * services.settings.limits.settings.poll_seconds)
    try:
        with Session(services.engine) as db:
            rows = db.exec(select(ProcessStatus).where(ProcessStatus.last_seen >= since)).all()
    except Exception:  # noqa: BLE001 - the metrics page must answer even when the database does not
        return
    PROCESS_VERSION.clear()  # processes that stopped drop out
    for row in rows:
        PROCESS_VERSION.labels(row.process_id, row.kind).set(row.component_version)
