"""Long-lived services shared by pipeline steps and API routes, built once at startup."""
from dataclasses import dataclass

from sqlalchemy import Engine

from app.auth.service import AccountService
from app.core.config import Settings, get_settings
from app.llm import CloudClient, LLMClient, build_llm_clients
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


def build_services(settings: Settings | None = None) -> Services:
    settings = settings or get_settings()
    engine = make_engine(settings.database_url)
    init_db(engine)
    local_llm, cloud_llm = build_llm_clients(settings)
    return Services(
        settings=settings,
        engine=engine,
        router=load_router(settings.routing.impl),
        retriever=load_retriever(settings.rag.impl),
        sessions=load_session_store(settings.sessions.store, engine),
        accounts=AccountService(engine, settings),
        local_llm=local_llm,
        cloud_llm=cloud_llm,
    )
