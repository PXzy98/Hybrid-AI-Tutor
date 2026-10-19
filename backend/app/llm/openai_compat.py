"""Any OpenAI-compatible chat API (OpenAI, Groq, Kimi, DeepSeek, ...). Only used behind CloudClient."""
import asyncio
import logging
from time import perf_counter

import openai

from app.core.schemas import LLMResult
from app.llm.base import LLMError, LLMUnavailable, Message, strip_think

log = logging.getLogger("app.llm")


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout_s: float = 30,
                 max_tokens: int = 800, temperature: float = 0.2,
                 client: openai.AsyncOpenAI | None = None) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._injected = client
        self._args = {"base_url": base_url, "api_key": api_key, "timeout": timeout_s, "max_retries": 1}
        self._clients: dict[int, openai.AsyncOpenAI] = {}

    def _client(self) -> openai.AsyncOpenAI:
        """One SDK client per event loop: its connection pool belongs to the loop that opened it, and a
        test client or a worker thread may run each request on a new loop ("Event loop is closed")."""
        if self._injected is not None:
            return self._injected
        loop = id(asyncio.get_running_loop())
        if loop not in self._clients:
            self._clients = {loop: openai.AsyncOpenAI(**self._args)}  # drop clients of finished loops
        return self._clients[loop]

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult:
        kwargs: dict = {}
        if json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        t0 = perf_counter()
        try:
            resp = await self._client().chat.completions.create(
                model=self.model, messages=messages, temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens, **kwargs,
            )
        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError,
                openai.AuthenticationError) as e:
            raise LLMUnavailable(f"cloud API unavailable ({type(e).__name__})") from e
        except openai.APIError as e:
            raise LLMError(f"cloud API error ({type(e).__name__})") from e
        choice = resp.choices[0] if resp.choices else None
        text = strip_think(choice.message.content if choice else "")
        cut_off = getattr(choice, "finish_reason", None) == "length"
        if not text:
            # reasoning models (e.g. deepseek-flash) count their hidden reasoning against max_tokens
            raise LLMError("cloud answer cut off at max_tokens before any text" if cut_off
                           else "cloud API returned an empty answer")
        if cut_off:
            log.warning("cloud answer cut off at max_tokens=%s (raise llm.cloud.max_tokens)",
                        max_tokens or self.max_tokens)
        usage = resp.usage
        return LLMResult(
            text=text,
            model=self.model,
            backend="cloud",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            latency_ms=round((perf_counter() - t0) * 1000, 1),
        )
