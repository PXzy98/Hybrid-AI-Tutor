"""FastAPI application. Run from backend/:  python -m uvicorn app.main:app --reload"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.admin.runtime_config import restore_latest
from app.api.v1 import api_router
from app.core.services import build_services
from app.pipeline.runner import build_runner

DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]  # Vite dev server


@asynccontextmanager
async def lifespan(app: FastAPI):
    services = build_services()
    services.accounts.bootstrap_instructor()
    app.state.services = services
    app.state.runner = build_runner(services)
    if restore_latest(app):  # the newest dashboard change survives a restart
        logging.getLogger("app").info("runtime config restored from config_history")
    logging.getLogger("app").info("pipeline: %s", " -> ".join(app.state.runner.step_names))
    yield
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
    return app


app = create_app()
