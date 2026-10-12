"""Local model through Ollama's native /api/chat (not /v1): the only way to switch thinking off reliably."""
from time import perf_counter

import httpx

from app.core.schemas import LLMResult
from app.llm.base import LLMError, LLMUnavailable, Message, strip_think


class OllamaClient:
    def __init__(self, base_url: str, model: str, *, temperature: float = 0.2, num_ctx: int = 8192,
                 timeout_s: float = 60, max_tokens: int = 1024,
                 transport: httpx.AsyncBaseTransport | None = None) -> None:
        self.url = base_url.rstrip("/") + "/api/chat"
        self.model = model
        self.temperature = temperature
        self.num_ctx = num_ctx
        self.timeout_s = timeout_s
        self.max_tokens = max_tokens
        self._transport = transport  # tests inject httpx.MockTransport

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult:
        body: dict = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "think": False,  # always off (model boundary test: loops and 5-7x latency)
            "options": {"temperature": self.temperature, "num_ctx": self.num_ctx,
                        "num_predict": max_tokens or self.max_tokens},
        }
        if json_schema is not None:
            body["format"] = json_schema

        t0 = perf_counter()
        r = await self._post(body)
        if r.status_code != 200:
            raise LLMError(f"ollama HTTP {r.status_code}")
        try:
            data = r.json()
        except ValueError:
            raise LLMError("ollama returned invalid JSON") from None
        text = strip_think(data.get("message", {}).get("content", ""))
        if not text:
            raise LLMError("ollama returned an empty answer")
        return LLMResult(
            text=text,
            model=self.model,
            backend="local",
            prompt_tokens=data.get("prompt_eval_count"),
            completion_tokens=data.get("eval_count"),
            latency_ms=round((perf_counter() - t0) * 1000, 1),
        )

    async def _post(self, body: dict) -> httpx.Response:
        """One retry on connection errors only; a timeout is not retried (the model may still be busy)."""
        for attempt in (1, 2):
            try:
                async with httpx.AsyncClient(timeout=self.timeout_s, transport=self._transport) as client:
                    return await client.post(self.url, json=body)
            except (httpx.ConnectError, httpx.ConnectTimeout) as e:
                if attempt == 2:
                    raise LLMUnavailable(f"ollama unreachable ({type(e).__name__})") from e
            except httpx.TimeoutException as e:
                raise LLMUnavailable(f"ollama timed out after {self.timeout_s}s") from e
            except httpx.HTTPError as e:
                raise LLMUnavailable(f"ollama request failed ({type(e).__name__})") from e
        raise AssertionError("unreachable")
