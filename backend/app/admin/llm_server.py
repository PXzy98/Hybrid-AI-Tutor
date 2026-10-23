"""Connection test for a local model server (G1-94): the professor's own Ollama server.

The dashboard calls this before saving a new address, so a typo does not break every answer. Only the
server's model list is read (GET /api/tags); no question or student data is sent.
"""
from time import perf_counter

import httpx
from pydantic import BaseModel, Field

TIMEOUT_S = 5.0


class ServerTest(BaseModel):
    url: str = Field(min_length=1, max_length=300)
    model: str = Field(min_length=1, max_length=100)


class ServerStatus(BaseModel):
    reachable: bool
    model_available: bool
    models: list[str] = []  # the first 50 models the server offers
    latency_ms: int | None = None
    error: str | None = None


async def check_server(url: str, model: str,
                       transport: httpx.AsyncBaseTransport | None = None) -> ServerStatus:
    base = url.strip().rstrip("/")
    t0 = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport) as client:
            r = await client.get(f"{base}/api/tags")
    except httpx.HTTPError as e:
        return ServerStatus(reachable=False, model_available=False,
                            error=f"not reachable: {type(e).__name__}")
    latency = round((perf_counter() - t0) * 1000)
    if r.status_code != 200:
        return ServerStatus(reachable=False, model_available=False, latency_ms=latency,
                            error=f"HTTP {r.status_code}: not an Ollama server?")
    try:
        names = [m["name"] for m in r.json().get("models", []) if isinstance(m, dict) and "name" in m]
    except ValueError:
        return ServerStatus(reachable=False, model_available=False, latency_ms=latency,
                            error="unexpected answer: not an Ollama server?")
    wanted = model.strip()
    # Ollama lists "qwen3.5:9b"; a name without a tag means ":latest"
    available = wanted in names or (":" not in wanted and f"{wanted}:latest" in names)
    return ServerStatus(reachable=True, model_available=available, models=names[:50], latency_ms=latency,
                        error=None if available else f"the server does not have the model {wanted}")
