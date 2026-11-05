"""Model gateway: the only way v4 code calls a model (guide sections 4.3 and 4.11, task Z6).

The gateway knows which model connection serves each role and whether that connection is trusted local
(may receive original text and the learner profile) or external (only content that passed the cloud gate).
A caller states what it is sending with `trust_required`; the gateway refuses to send "trusted_local"
content to an external connection.

Z1 stand-in: `FakeGateway` maps roles to `LLMClient`s (for example `FakeLLMClient`) and enforces the trust
rule; Z6 adds the connection registry, queueing, timeouts, metering and SSRF checks behind the same call.
"""
from collections.abc import AsyncIterator
from typing import Literal, Protocol

from app.core.schemas import EffectiveSettings, LLMResult
from app.llm.base import LLMClient, LLMUnavailable, Message

EndpointRole = Literal["local", "cloud", "judge"]
TrustRequired = Literal["trusted_local", "external_ok"]


class TrustViolation(Exception):
    """Content that may only go to a trusted local model was about to go to an external one."""


class ModelGateway(Protocol):
    async def complete(self, role: EndpointRole, messages: list[Message], *, settings: EffectiveSettings,
                       trust_required: TrustRequired, json_schema: dict | None = None,
                       stream: bool = False) -> LLMResult | AsyncIterator[str]: ...


class FakeGateway:
    def __init__(self, clients: dict[EndpointRole, LLMClient],
                 trusted: frozenset[EndpointRole] = frozenset({"local"})) -> None:
        self.clients = clients
        self.trusted = trusted

    async def complete(self, role: EndpointRole, messages: list[Message], *, settings: EffectiveSettings,
                       trust_required: TrustRequired, json_schema: dict | None = None,
                       stream: bool = False) -> LLMResult | AsyncIterator[str]:
        external = role not in self.trusted  # decided by the connection's trust level, never by the role name
        if trust_required == "trusted_local" and external:
            raise TrustViolation(f"'{role}' is not a trusted local connection")
        if external and settings.local_only:
            raise LLMUnavailable("this course uses the local model only")
        client = self.clients.get(role)
        if client is None:
            raise LLMUnavailable(f"no model connection for '{role}'")
        result = await client.complete(messages, json_schema=json_schema)
        if not stream:
            return result

        async def tokens() -> AsyncIterator[str]:
            for word in result.text.split(" "):
                yield word + " "

        return tokens()
