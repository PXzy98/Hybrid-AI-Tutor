"""FastAPI application. Run from backend/:  python -m uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v2 import api_router_v2
from app.api.v2.errors import (
    ApiError,
    ErrorCode,
    api_error_handler,
    catalog_error_handler,
    course_error_handler,
    error,
    usage_limit_handler,
)
from app.auth import csrf
from app.catalog import CatalogError
from app.core.services import build_services
from app.platform import metrics
from app.platform.access import DbCourseDirectory
from app.platform.courses import CourseError
from app.platform.usage import UsageLimitExceeded

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # Vite dev server


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = build_services()
    services.accounts.bootstrap_instructor()
    app.state.services = services
    app.state.course_directory = DbCourseDirectory(services.engine)  # require_course_role (Z9)
    services.component_manager.sync()  # heartbeat; finishes a change that was applying when it started
    services.component_manager.start()  # live component switch (course-structure.md section 6.5)
    logging.getLogger("app").info("pipeline: %s", " -> ".join(services.components.runner.step_names))
    yield
    services.component_manager.stop()
    services.engine.dispose()


async def _csrf(request: Request, call_next):
    services = getattr(request.app.state, "services", None)
    cookie_name = services.settings.auth.cookie_name if services else "tutor_session"
    if not csrf.check(request, cookie_name):
        return error(403, ErrorCode.csrf_failed,
                     "Missing or invalid CSRF token. Get one from /api/v2/auth/csrf.")
    return await call_next(request)


async def _no_store(request: Request, call_next):
    """API responses carry personal data: shared computers must not keep them in the HTTP cache (audit S3).
    A response that sets its own Cache-Control (the answer streams, the export) keeps it."""
    response = await call_next(request)
    if request.url.path.startswith("/api/") and "cache-control" not in response.headers:
        response.headers["Cache-Control"] = "no-store"
    return response


def create_app() -> FastAPI:
    app = FastAPI(
        title="PACT: Privacy-Aware Course Tutor",
        version="0.1.0",
        description="Health-education tutor with a local learner model. Design: docs/System_Design_v3.md",
        lifespan=lifespan,
    )
    # innermost first: CSRF (API v2 only, app.auth.csrf), then Cache-Control (S3), then the metrics (Z13;
    # requests refused by CSRF are counted too, streamed answers until their last byte), then CORS around all
    app.middleware("http")(_csrf)
    app.middleware("http")(_no_store)
    app.add_middleware(metrics.MetricsMiddleware)
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_credentials=True,  # session cookie
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(api_router)
    app.include_router(api_router_v2)  # docs/design/api-v2.md; /api/v1 is frozen
    # Prometheus (task Z13): not under /api, so the web proxy never serves it (only the stack reaches it)
    app.add_api_route("/metrics", metrics.metrics, methods=["GET"], include_in_schema=False)
    app.add_exception_handler(UsageLimitExceeded, usage_limit_handler)
    app.add_exception_handler(CourseError, course_error_handler)
    app.add_exception_handler(CatalogError, catalog_error_handler)
    app.add_exception_handler(ApiError, api_error_handler)
    return app


app = create_app()
