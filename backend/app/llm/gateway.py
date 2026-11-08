"""Model gateway: the only way v4 code calls a model (guide sections 4.3 and 4.11, task Z6).

The gateway knows which model connection serves each role and whether that connection is trusted local
(may receive original text and the learner profile) or external (only content that passed the cloud gate).
A caller states what it is sending with `trust_required`; the gateway refuses to send "trusted_local"
content to an external connection.

`Gateway` (task Z6) is the real implementation: it picks the connection for the role from the request's
settings (course connection → system default → the deployment's own model from .env/config), checks the
URL again (SSRF), enforces the trust rule and the course's local-only setting, and queues requests per
connection (`limits.models`: at most `max_concurrent` at a time, `queue_timeout_seconds` to wait).
`FakeGateway` (Z1) maps roles to clients for unit tests.
"""
import asyncio
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
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


class Gateway:
    """The model gateway of the running app (one per process, `services.gateway`)."""

    def __init__(self, services) -> None:
        self.services = services
        self._clients: dict[tuple, object] = {}
        self._slots: dict[tuple, asyncio.Semaphore] = {}

    # -------------------------------------------------------------------------------- resolution
    def _endpoint_id(self, role: EndpointRole, settings: EffectiveSettings | None) -> int | None:
        if settings is None:
            return None
        return settings.local_endpoint_id if role == "local" else (
            settings.cloud_endpoint_id if role == "cloud" else None)

    def resolve(self, role: EndpointRole, settings: EffectiveSettings | None) -> tuple[object, str, str]:
        """(client, trust, queue key) for the role. Without a stored connection: the deployment's model."""
        endpoint_id = self._endpoint_id(role, settings)
        if endpoint_id is not None:
            from sqlmodel import Session

            from app.llm.endpoints import build_client
            from app.llm.ssrf import check_endpoint_url
            from app.storage.models import ModelEndpoint

            with Session(self.services.engine) as db:
                row = db.get(ModelEndpoint, endpoint_id)
            if row is not None:
                check_endpoint_url(row.base_url, trust=row.trust)  # again: the name may resolve elsewhere now
                key = (row.id, row.updated_at)
                if key not in self._clients:
                    s = self.services.settings
                    cfg = s.llm.local if row.trust == "trusted_local" else s.llm.cloud
                    secret = (s.settings_encryption_key.get_secret_value()
                              if s.settings_encryption_key else None)
                    self._clients = {k: v for k, v in self._clients.items() if k[0] != row.id}
                    self._clients[key] = build_client(row, secret, timeout_s=cfg.timeout_s,
                                                      max_tokens=cfg.max_tokens)
                return self._clients[key], row.trust, f"endpoint:{row.id}"
        if role == "cloud":
            return getattr(self.services.cloud_llm, "_transport", None), "external", "cloud"
        return self.services.local_llm, "trusted_local", "local"

    # ------------------------------------------------------------------------------------ queueing
    @asynccontextmanager
    async def _slot(self, key: str):
        limits = self.services.settings.limits.models
        loop_key = (key, id(asyncio.get_running_loop()))  # asyncio primitives belong to one event loop
        sem = self._slots.get(loop_key)
        if sem is None:
            sem = self._slots[loop_key] = asyncio.Semaphore(limits.max_concurrent)
        try:
            await asyncio.wait_for(sem.acquire(), timeout=limits.queue_timeout_seconds)
        except TimeoutError:
            raise LLMUnavailable("the model is busy; try again in a moment") from None
        try:
            yield
        finally:
            sem.release()

    # ------------------------------------------------------------------------------------- calling
    async def complete(self, role: EndpointRole, messages: list[Message], *,
                       settings: EffectiveSettings | None, trust_required: TrustRequired,
                       json_schema: dict | None = None,
                       stream: bool = False) -> LLMResult | AsyncIterator[str]:
        client, trust, key = self.resolve(role, settings)
        external = trust != "trusted_local"
        if trust_required == "trusted_local" and external:
            raise TrustViolation(f"the {role} connection is not a trusted local connection")
        if external and settings is not None and settings.local_only:
            raise LLMUnavailable("this course uses the local model only")
        if client is None:
            raise LLMUnavailable(f"no model connection for '{role}'")
        if not stream:
            async with self._slot(key):
                return await client.complete(messages, json_schema=json_schema)

        async def tokens() -> AsyncIterator[str]:
            async with self._slot(key):
                if hasattr(client, "stream"):
                    async for piece in client.stream(messages, json_schema=json_schema):
                        yield piece
                else:
                    yield (await client.complete(messages, json_schema=json_schema)).text

        return tokens()

    def cloud_client(self, settings: EffectiveSettings | None):
        """The CloudClient for this request: only a validated CloudRequest can pass it (privacy rule 3)."""
        from app.llm.cloud_guard import CloudClient

        if settings is not None and settings.local_only:
            return CloudClient(None)
        if self._endpoint_id("cloud", settings) is None:
            return self.services.cloud_llm  # the deployment's cloud connection (.env)
        client, _, key = self.resolve("cloud", settings)
        return CloudClient(_Queued(self, client, key))


class _Queued:
    """A client whose calls wait for a slot of its connection."""

    def __init__(self, gateway: Gateway, client, key: str) -> None:
        self.gateway, self.client, self.key = gateway, client, key
        self.model = client.model

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        async with self.gateway._slot(self.key):
            return await self.client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)
