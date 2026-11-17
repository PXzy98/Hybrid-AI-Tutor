import httpx
from fastapi import APIRouter
from pydantic import BaseModel
from sqlalchemy import text
from sqlmodel import Session

from app.api.deps import ServicesDep

router = APIRouter()


# the local model server (vLLM since Z22); the v1 names `ollama` and `OllamaStatus` stay (v1 is frozen)
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
    if s.vllm_base_url:
        headers = {"Authorization": f"Bearer {s.vllm_key.get_secret_value()}"} if s.vllm_key else {}
        try:  # reported, not fatal: the API still starts without the GPU server
            async with httpx.AsyncClient(timeout=1.5) as client:
                r = await client.get(f"{s.vllm_base_url.rstrip('/')}/models", headers=headers)
            r.raise_for_status()
            names = {m.get("id") for m in r.json().get("data", [])}
            ollama = OllamaStatus(reachable=True, model=s.llm.local.model,
                                  model_available=s.llm.local.model in names)
        except (httpx.HTTPError, ValueError, AttributeError):
            pass

    return Health(status="ok" if db_ok else "degraded", config=True, db=db_ok, ollama=ollama,
                  cloud_enabled=s.cloud_enabled, routing_impl=s.routing.impl, rag_impl=s.rag.impl)
