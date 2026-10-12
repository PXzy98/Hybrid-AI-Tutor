import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.api.deps import ServicesDep

router = APIRouter()


class OllamaStatus(BaseModel):
    reachable: bool
    model: str
    model_available: bool = False


class Health(BaseModel):
    status: str  # ok | degraded
    config: bool
    db: bool
    ollama: OllamaStatus
    cloud_enabled: bool
    routing_impl: str
    rag_impl: str


@router.get("/health", response_model=Health)
async def health(services: ServicesDep):
    s = services.settings
    try:
        with Session(services.engine) as session:
            session.exec(text("SELECT 1"))
        db_ok = True
    except Exception:  # noqa: BLE001
        db_ok = False

    ollama = OllamaStatus(reachable=False, model=s.llm.local.model)
    try:  # reported, not fatal: the API still starts without the GPU server
        async with httpx.AsyncClient(timeout=1.5) as client:
            r = await client.get(f"{s.ollama_url.rstrip('/')}/api/tags")
        r.raise_for_status()
        names = {m.get("name") for m in r.json().get("models", [])}
        ollama = OllamaStatus(reachable=True, model=s.llm.local.model,
                              model_available=s.llm.local.model in names)
    except (httpx.HTTPError, ValueError):
        pass

    return Health(status="ok" if db_ok else "degraded", config=True, db=db_ok, ollama=ollama,
                  cloud_enabled=s.cloud_enabled, routing_impl=s.routing.impl, rag_impl=s.rag.impl)
