"""Connection test for a local model server (G1-94): the deployment's own OpenAI-compatible server (vLLM).

The dashboard calls this before saving a new address, so a typo does not break every answer. Only the
server's model list is read (GET <url>/models); no question or student data is sent.
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


async def check_server(url: str, model: str, api_key: str | None = None,
                       transport: httpx.AsyncBaseTransport | None = None) -> ServerStatus:
    """`url` is the API root ending in /v1 (VLLM_BASE_URL); `api_key` the server's --api-key, if any."""
    base = url.strip().rstrip("/")
    headers = {"Authorization": f"Bearer {api_key}"} if api_key else {}
    t0 = perf_counter()
    try:
        async with httpx.AsyncClient(timeout=TIMEOUT_S, transport=transport) as client:
            r = await client.get(f"{base}/models", headers=headers)
    except httpx.HTTPError as e:
        return ServerStatus(reachable=False, model_available=False,
                            error=f"not reachable: {type(e).__name__}")
    latency = round((perf_counter() - t0) * 1000)
    if r.status_code in (401, 403):
        return ServerStatus(reachable=False, model_available=False, latency_ms=latency,
                            error=f"HTTP {r.status_code}: the server refused the key (VLLM_KEY)")
    if r.status_code != 200:
        return ServerStatus(reachable=False, model_available=False, latency_ms=latency,
                            error=f"HTTP {r.status_code}: not an OpenAI-compatible API root (ending in /v1)?")
    try:
        names = [m["id"] for m in r.json().get("data", []) if isinstance(m, dict) and "id" in m]
    except (ValueError, AttributeError):
        return ServerStatus(reachable=False, model_available=False, latency_ms=latency,
                            error="unexpected answer: not an OpenAI-compatible API root?")
    wanted = model.strip()
    available = wanted in names
    return ServerStatus(reachable=True, model_available=available, models=names[:50], latency_ms=latency,
                        error=None if available else f"the server does not have the model {wanted}")
