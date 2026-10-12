"""Any OpenAI-compatible chat API (OpenAI, Groq, Kimi, ...). Only used behind CloudClient."""
from time import perf_counter

import openai

from app.core.schemas import LLMResult
from app.llm.base import LLMError, LLMUnavailable, Message, strip_think


class OpenAICompatClient:
    def __init__(self, base_url: str, api_key: str, model: str, *, timeout_s: float = 30,
                 max_tokens: int = 800, temperature: float = 0.2,
                 client: openai.AsyncOpenAI | None = None) -> None:
        self.model = model
        self.max_tokens = max_tokens
        self.temperature = temperature
        self._client = client or openai.AsyncOpenAI(base_url=base_url, api_key=api_key, timeout=timeout_s,
                                                    max_retries=1)

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult:
        kwargs: dict = {}
        if json_schema is not None:
            kwargs["response_format"] = {"type": "json_object"}
        t0 = perf_counter()
        try:
            resp = await self._client.chat.completions.create(
                model=self.model, messages=messages, temperature=self.temperature,
                max_tokens=max_tokens or self.max_tokens, **kwargs,
            )
        except (openai.APIConnectionError, openai.APITimeoutError, openai.RateLimitError,
                openai.AuthenticationError) as e:
            raise LLMUnavailable(f"cloud API unavailable ({type(e).__name__})") from e
        except openai.APIError as e:
            raise LLMError(f"cloud API error ({type(e).__name__})") from e
        text = strip_think(resp.choices[0].message.content if resp.choices else "")
        if not text:
            raise LLMError("cloud API returned an empty answer")
        usage = resp.usage
        return LLMResult(
            text=text,
            model=self.model,
            backend="cloud",
            prompt_tokens=usage.prompt_tokens if usage else None,
            completion_tokens=usage.completion_tokens if usage else None,
            latency_ms=round((perf_counter() - t0) * 1000, 1),
        )
