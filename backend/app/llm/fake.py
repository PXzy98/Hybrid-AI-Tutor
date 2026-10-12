"""Scripted LLM for tests: no network, records every call so tests can assert what was sent."""
from collections.abc import Callable

from app.core.schemas import LLMResult
from app.llm.base import LLMError, Message

Reply = str | Exception | Callable[[list[Message]], str]


class FakeLLMClient:
    def __init__(self, replies: list[Reply] | Reply = "Fake answer.", model: str = "fake-model",
                 backend: str = "local") -> None:
        self.replies = list(replies) if isinstance(replies, list) else [replies]
        self.model = model
        self.backend = backend
        self.calls: list[dict] = []

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult:
        self.calls.append({"messages": messages, "json_schema": json_schema, "max_tokens": max_tokens})
        reply = self.replies.pop(0) if len(self.replies) > 1 else self.replies[0]  # last reply repeats
        if isinstance(reply, Exception):
            raise reply
        text = reply(messages) if callable(reply) else reply
        if not text:
            raise LLMError("empty answer")
        return LLMResult(text=text, model=self.model, backend=self.backend, prompt_tokens=10,
                         completion_tokens=20, latency_ms=1.0)

    @property
    def last_messages(self) -> list[Message]:
        return self.calls[-1]["messages"]

    def sent_text(self) -> str:
        """Everything this client was ever sent, as one string (for leak assertions)."""
        return "\n".join(m["content"] for call in self.calls for m in call["messages"])
