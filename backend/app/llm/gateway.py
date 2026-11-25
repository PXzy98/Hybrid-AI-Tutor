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
from collections.abc import AsyncIterator, Awaitable, Callable
from contextlib import asynccontextmanager
from contextvars import ContextVar
from typing import Literal, Protocol

from app.core.schemas import EffectiveSettings, LLMResult
from app.llm.base import LLMClient, LLMUnavailable, Message, ModelBusy

EndpointRole = Literal["local", "cloud", "judge"]
TrustRequired = Literal["trusted_local", "external_ok"]


# Set by the code that serves one student's question (the answer stream); called once per wait, without
# any argument or text, when a model call of that question has to wait for a free slot.
wait_notice: ContextVar[Callable[[], Awaitable[None]] | None] = ContextVar("wait_notice", default=None)


class TrustViolation(Exception):
    """Content that may only go to a trusted local model was about to go to an external one."""


class ModelGateway(Protocol):
    async def complete(self, role: EndpointRole, messages: list[Message], *, settings: EffectiveSettings,
                       trust_required: TrustRequired, json_schema: dict | None = None,
                       stream: bool = False, max_tokens: int | None = None) -> LLMResult | AsyncIterator[str]:
        """`max_tokens` overrides the connection's output limit for this call (long structured drafts)."""


class FakeGateway:
    def __init__(self, clients: dict[EndpointRole, LLMClient],
                 trusted: frozenset[EndpointRole] = frozenset({"local"})) -> None:
        self.clients = clients
        self.trusted = trusted

    def cloud_client(self, settings: EffectiveSettings | None):
        """As `Gateway.cloud_client`: the cloud client behind the gate (none in a local-only course)."""
        from app.llm.cloud_guard import CloudClient

        client = self.clients.get("cloud")
        if client is None or "cloud" in self.trusted or (settings is not None and settings.local_only):
            return CloudClient(None)
        return CloudClient(client)

    async def complete(self, role: EndpointRole, messages: list[Message], *, settings: EffectiveSettings,
                       trust_required: TrustRequired, json_schema: dict | None = None,
                       stream: bool = False, max_tokens: int | None = None) -> LLMResult | AsyncIterator[str]:
        external = role not in self.trusted  # decided by the connection's trust level, never by the role name
        if trust_required == "trusted_local" and external:
            raise TrustViolation(f"'{role}' is not a trusted local connection")
        if external and settings.local_only:
            raise LLMUnavailable("this course uses the local model only")
        client = self.clients.get(role)
        if client is None:
            raise LLMUnavailable(f"no model connection for '{role}'")
        result = await client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)
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
        if sem.locked():  # no slot is free right now: this call has to wait in line
            notice = wait_notice.get()
            if notice is not None:
                try:
                    await notice()
                except Exception:  # noqa: BLE001 - the notice is a courtesy; the call still waits for its slot
                    pass
        try:
            await asyncio.wait_for(sem.acquire(), timeout=limits.queue_timeout_seconds)
        except TimeoutError:
            raise ModelBusy("the model is busy; try again in a moment") from None
        try:
            yield
        finally:
            sem.release()

    # ------------------------------------------------------------------------------------- calling
    async def complete(self, role: EndpointRole, messages: list[Message], *,
                       settings: EffectiveSettings | None, trust_required: TrustRequired,
                       json_schema: dict | None = None, stream: bool = False,
                       max_tokens: int | None = None) -> LLMResult | AsyncIterator[str]:
        client, trust, key = self.resolve(role, settings)
        external = trust != "trusted_local"
        if trust_required == "trusted_local" and external:
            raise TrustViolation(f"the {role} connection is not a trusted local connection")
        if external and settings is not None and settings.local_only:
            raise LLMUnavailable("this course uses the local model only")
        if client is None:
            raise LLMUnavailable(f"no model connection for '{role}'")
        backend = "local" if trust == "trusted_local" else "cloud"  # by trust, not by wire protocol
        if not stream:
            async with self._slot(key):
                result = await client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)
            return result.model_copy(update={"backend": backend})

        async def tokens() -> AsyncIterator[str]:
            options = {"json_schema": json_schema, "max_tokens": max_tokens}
            async with self._slot(key):
                if hasattr(client, "stream"):
                    async for piece in client.stream(messages, **options):
                        yield piece
                else:
                    yield (await client.complete(messages, **options)).text

        return tokens()

    def trusted_local_client(self, settings: EffectiveSettings | None, default):
        """The client for the small local calls that read the original text (understand, the generalize
        rewrite, llm_check; task Z17): the request's trusted local connection when one is stored (course or
        system default), queued with the answers; otherwise `default`, the deployment's own client for that
        call. A stored connection that is not trusted local is never used for them."""
        if self._endpoint_id("local", settings) is None:
            return default
        try:
            client, trust, key = self.resolve("local", settings)
        except Exception as e:  # noqa: BLE001  e.g. the name no longer resolves (SSRF check): fail closed
            return _Refused(f"the local connection cannot be used ({type(e).__name__})")
        if client is None:
            return _Refused("no local connection")
        if trust != "trusted_local":
            return _Refused("the local connection is not a trusted local connection")
        return _Queued(self, client, key)

    def cloud_client(self, settings: EffectiveSettings | None):
        """The CloudClient for this request: only a validated CloudRequest can pass it (privacy rule 3)."""
        from app.llm.cloud_guard import CloudClient

        if settings is not None and settings.local_only:
            return CloudClient(None)
        if self._endpoint_id("cloud", settings) is None:
            # the deployment's cloud connection (.env): the same queue, around the existing CloudClient
            return _QueuedCloud(self, self.services.cloud_llm, "cloud")
        client, _, key = self.resolve("cloud", settings)
        return CloudClient(_Queued(self, client, key))


class _Refused:
    """Stands in for a connection that may not receive the call: every call fails like an unreachable model,
    so each caller's own failure rule applies (understand is skipped, generalize and llm_check keep the
    question local)."""

    def __init__(self, reason: str) -> None:
        self.reason, self.model = reason, None

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        raise LLMUnavailable(self.reason)


class _Queued:
    """A client whose calls wait for a slot of its connection."""

    def __init__(self, gateway: Gateway, client, key: str) -> None:
        self.gateway, self.client, self.key = gateway, client, key
        self.model = client.model

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        async with self.gateway._slot(self.key):
            return await self.client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)


class _QueuedCloud:
    """The deployment's CloudClient behind the queue of its connection (still accepts only a CloudRequest)."""

    def __init__(self, gateway: Gateway, cloud, key: str) -> None:
        self.gateway, self.cloud, self.key = gateway, cloud, key

    @property
    def available(self) -> bool:
        return self.cloud.available

    @property
    def model(self):
        return self.cloud.model

    async def complete(self, req, *, safety_retry: bool = False):
        async with self.gateway._slot(self.key):
            return await self.cloud.complete(req, safety_retry=safety_retry)

    async def complete_draft(self, req):
        async with self.gateway._slot(self.key):
            return await self.cloud.complete_draft(req)
