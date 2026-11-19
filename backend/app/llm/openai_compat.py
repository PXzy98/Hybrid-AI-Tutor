"""Any OpenAI-compatible chat API: hosted ones (OpenAI, Groq, Kimi, DeepSeek, ...) behind CloudClient, and a
course's own server (vLLM) through a trusted local model connection."""
import asyncio
import logging
from collections.abc import AsyncIterator
from time import perf_counter

import openai

from app.core.schemas import LLMResult
from app.llm.base import LLMError, LLMUnavailable, Message, strip_think

log = logging.getLogger("app.llm")


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout_s: float = 30,
                 max_tokens: int = 800, temperature: float = 0.2,
                 client: openai.AsyncOpenAI | None = None, transport=None,
                 thinking_off: bool = False, schema_output: bool = False, backend: str = "cloud") -> None:
        self.model = model
        self.backend = backend  # "local" for the deployment's or a course's trusted local server (vLLM)
        # a self-hosted server (vLLM) constrains the answer to the JSON schema; with only "json_object" the
        # model makes up its own field names and every structured answer fails validation
        self.schema_output = schema_output
        # a self-hosted server (vLLM) runs Qwen3.5 with thinking on by default: hundreds of hidden tokens
        # before the answer (7x slower on the test host, and cut off at max_tokens). Hosted APIs reject it.
        off = {"chat_template_kwargs": {"enable_thinking": False}}
        self._extra = {"extra_body": off} if thinking_off else {}
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._injected = client
        self._args = {"base_url": base_url, "api_key": api_key, "timeout": timeout_s, "max_retries": 1}
        self._transport = transport  # e.g. ssrf.PinnedTransport for instructor-added connections
        self._clients: dict[int, openai.AsyncOpenAI] = {}

    def _response_format(self, json_schema: dict) -> dict:
        if self.schema_output:
            return {"type": "json_schema", "json_schema": {"name": "answer", "schema": json_schema}}
        return {"type": "json_object"}

    def _client(self) -> openai.AsyncOpenAI:
        """One SDK client per event loop: its connection pool belongs to the loop that opened it, and a
        test client or a worker thread may run each request on a new loop ("Event loop is closed")."""
        if self._injected is not None:
            return self._injected
        loop = id(asyncio.get_running_loop())
        if loop not in self._clients:
            extra = {}
            if self._transport is not None:
                import httpx

                extra["http_client"] = httpx.AsyncClient(transport=self._transport,
                                                         timeout=self._args["timeout"])
            # drop the clients of finished loops
            self._clients = {loop: openai.AsyncOpenAI(**self._args, **extra)}
        return self._clients[loop]

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult:
        kwargs: dict = dict(self._extra)
        if json_schema is not None:
            kwargs["response_format"] = self._response_format(json_schema)
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
            backend=self.backend,
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            latency_ms=round((perf_counter() - t0) * 1000, 1),
        )

    async def stream(self, messages: list[Message], *, json_schema: dict | None = None,
                     max_tokens: int | None = None) -> AsyncIterator[str]:
        """The answer as it is generated (task Z6: token streaming)."""
        kwargs: dict = dict(self._extra)
        if json_schema is not None:
            kwargs["response_format"] = self._response_format(json_schema)
        try:
            chunks = await self._client().chat.completions.create(
                model=self.model, messages=messages, temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens, stream=True, **kwargs,
            )
            async for chunk in chunks:
                piece = chunk.choices[0].delta.content if chunk.choices else None
                if piece:
                    yield piece
        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError,
                openai.AuthenticationError) as e:
            raise LLMUnavailable(f"model API unavailable ({type(e).__name__})") from e
        except openai.APIError as e:
            raise LLMError(f"model API error ({type(e).__name__})") from e
