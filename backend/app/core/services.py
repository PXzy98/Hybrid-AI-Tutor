"""Long-lived services shared by pipeline steps and API routes, built once at startup."""
from dataclasses import dataclass

from sqlalchemy import Engine

from app.auth.service import AccountService
from app.core.config import Settings, get_settings
from app.learner.content import ContentStore
from app.learner.facade import LearnerModel, build_learner_model
from app.llm.base import LLMClient
from app.llm.cloud_guard import CloudClient
from app.llm.factory import build_llm_clients
from app.rag import Retriever, load_retriever
from app.routing import RouteScorer, load_router
from app.sessions import SessionStore, load_session_store
from app.storage.db import init_db, make_engine


@dataclass
class Services:
    settings: Settings
    engine: Engine
    router: RouteScorer
    retriever: Retriever
    sessions: SessionStore
    accounts: AccountService
    local_llm: LLMClient
    cloud_llm: CloudClient
    understand_llm: LLMClient
    content: ContentStore
    learner: LearnerModel

    def reconfigure(self, settings: Settings) -> None:
        """Runtime config change (admin dashboard): new settings, a learner model built from them, and new local
        LLM clients when the local model server or model changed.
        The pipeline is rebuilt by the caller (app.admin.runtime_config.apply)."""
        before = self.settings
        self.settings = settings
        self.router.cfg = settings.routing
        if (before.ollama_url, before.llm.local, before.llm.understand) != (
                settings.ollama_url, settings.llm.local, settings.llm.understand):
            # local model server or model changed (G1-94): new local clients; the cloud client is kept
            self.local_llm, _, self.understand_llm = build_llm_clients(settings)
        self.learner = build_learner_model(settings, self.engine, self.content)


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    local_llm, cloud_llm, understand_llm = build_llm_clients(settings)
    content = ContentStore(settings.content_dir(), settings.content.serve_unreviewed)  # validated here
    return Services(
        settings=settings,
        engine=engine,
        router=load_router(settings.routing.impl),
        retriever=load_retriever(settings.rag.impl),
        sessions=load_session_store(settings.sessions.store, engine),
        accounts=AccountService(engine, settings),
        local_llm=local_llm,
        cloud_llm=cloud_llm,
        understand_llm=understand_llm,
        content=content,
        learner=build_learner_model(settings, engine, content),
    )
