"""FastAPI application. Run from backend/:  python -m uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.v1 import api_router
from app.api.v2 import api_router_v2
from app.api.v2.errors import usage_limit_handler
from app.core.services import build_services
from app.platform.access import DbCourseDirectory
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


def create_app() -> FastAPI:
    app = FastAPI(
        title="Privacy-Aware Hybrid AI Tutor",
        version="0.1.0",
        description="Health-education tutor with a local learner model. Design: docs/System_Design_v3.md",
        lifespan=lifespan,
    )
    app.add_middleware(CORSMiddleware, allow_origins=DEV_ORIGINS, allow_credentials=True,  # session cookie
                       allow_methods=["*"], allow_headers=["*"])
    app.include_router(api_router)
    app.include_router(api_router_v2)  # docs/design/api-v2.md; /api/v1 is frozen
    app.add_exception_handler(UsageLimitExceeded, usage_limit_handler)
    return app


app = create_app()
