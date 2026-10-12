"""One interface for every model backend (design §3: "one LLMClient interface for Ollama and cloud APIs")."""
import re
from typing import Protocol, runtime_checkable

from app.core.schemas import LLMResult

Message = dict[str, str]  # {"role": "system" | "user" | "assistant", "content": "..."}

_THINK = re.compile(r"<think>.*?</think>", re.S | re.I)


class LLMError(Exception):
    """The model answered with an error or an unusable reply. Messages never contain prompt text."""


class LLMUnavailable(LLMError):
    """The model could not be reached (connection, timeout, not configured)."""


@runtime_checkable
class LLMClient(Protocol):
    model: str

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult: ...


def strip_think(text: str) -> str:
    """Drop reasoning blocks, in case a model emits them although thinking is off."""
    return _THINK.sub("", text or "").strip()
