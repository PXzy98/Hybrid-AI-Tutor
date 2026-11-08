"""Model connection registry (task Z6, guide 4.11; API: design/api-v2.md 3.2 and 3.3).

A connection belongs to the system (`course_id` None, admin) or to one course (its instructors). Rules:
- the URL passes `check_endpoint_url` for its trust level when it is saved and before every call;
- `trusted_local` (may receive original student text) requires the creator to confirm that he controls the
  service (guide 4.11 privacy notice); otherwise a connection is `external`;
- an API key is stored encrypted and never returned; only its last four characters are;
- saving requires a successful connection test (the caller passes the tester);
- every create, update and delete is audited; deleting sets the settings that referred to it to null.
"""
from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from sqlmodel import Session, select

from app.llm import secrets
from app.llm.ssrf import check_endpoint_url
from app.storage.models import AuditLog, ModelEndpoint, utcnow

KINDS = ("ollama", "openai_compat")
TRUST = ("trusted_local", "external")


class EndpointError(ValueError):
    """Invalid connection (the message is safe to show)."""


@dataclass(frozen=True)
class EndpointView:
    """What an API returns about a connection: never the key itself."""

    id: int
    course_id: int | None
    name: str
    kind: str
    base_url: str
    model: str
    trust: str
    api_key_last4: str | None
    last_test_ok_at: object


def view(row: ModelEndpoint) -> EndpointView:
    return EndpointView(row.id, row.course_id, row.name, row.kind, row.base_url, row.model, row.trust,
                        row.api_key_last4, row.last_test_ok_at)


def build_client(row: ModelEndpoint, encryption_key: str | None, *, timeout_s: float = 60,
                 max_tokens: int = 1024):
    """An LLMClient for the connection (the URL is checked again by the gateway before each call)."""
    from app.llm.ollama_client import OllamaClient
    from app.llm.openai_compat import OpenAICompatClient

    if row.kind == "ollama":
        return OllamaClient(row.base_url, row.model, timeout_s=timeout_s, max_tokens=max_tokens)
    key = secrets.decrypt(row.api_key_encrypted, encryption_key) if row.api_key_encrypted else "none"
    return OpenAICompatClient(row.base_url, key, row.model, timeout_s=timeout_s, max_tokens=max_tokens)


Tester = Callable[[ModelEndpoint, str | None], Awaitable[None]]  # raises when the connection does not work


async def default_tester(row: ModelEndpoint, encryption_key: str | None) -> None:
    from app.llm.base import LLMError

    client = build_client(row, encryption_key, timeout_s=20, max_tokens=5)
    try:
        await client.complete([{"role": "user", "content": "Reply with the word OK."}], max_tokens=5)
    except LLMError as e:
        raise EndpointError(f"the connection test failed ({type(e).__name__})") from e


def _validated(*, name: str, kind: str, base_url: str, model: str, trust: str,
               confirm_controlled: bool) -> dict:
    if kind not in KINDS:
        raise EndpointError("kind must be ollama or openai_compat")
    if trust not in TRUST:
        raise EndpointError("trust must be trusted_local or external")
    if trust == "trusted_local" and not confirm_controlled:
        raise EndpointError("confirm that you control this service: it will receive original student text")
    if not name.strip() or not model.strip() or " " in model.strip():
        raise EndpointError("give the connection a name and a one-word model name")
    try:
        url = check_endpoint_url(base_url, trust=trust)
    except ValueError as e:
        raise EndpointError(str(e)) from e
    return {"name": name.strip(), "kind": kind, "base_url": url, "model": model.strip(), "trust": trust}


async def create_endpoint(engine, *, course_id: int | None, name: str, kind: str, base_url: str, model: str,
                          trust: str, api_key: str | None, confirm_controlled: bool, account_id: int | None,
                          encryption_key: str | None, tester: Tester = default_tester) -> EndpointView:
    fields = _validated(name=name, kind=kind, base_url=base_url, model=model, trust=trust,
                        confirm_controlled=confirm_controlled)
    row = ModelEndpoint(course_id=course_id, updated_by=account_id, **fields)
    if api_key:
        row.api_key_encrypted = secrets.encrypt(api_key, encryption_key)
        row.api_key_last4 = secrets.last4(api_key)
    await tester(row, encryption_key)
    row.last_test_ok_at = utcnow()
    with Session(engine) as db:
        db.add(row)
        db.flush()
        db.add(AuditLog(account_id=account_id, action="model_endpoint.create",
                        target=f"model_endpoint:{row.id}", details={"course_id": course_id, "trust": trust}))
        db.commit()
        db.refresh(row)
        return view(row)


async def update_endpoint(engine, endpoint_id: int, *, course_id: int | None, changes: dict,
                          confirm_controlled: bool, account_id: int | None, encryption_key: str | None,
                          tester: Tester = default_tester) -> EndpointView:
    with Session(engine) as db:
        row = db.get(ModelEndpoint, endpoint_id)
        if row is None or row.course_id != course_id:
            raise EndpointError("unknown connection")
        merged = {k: changes.get(k, getattr(row, k)) for k in ("name", "kind", "base_url", "model", "trust")}
        fields = _validated(confirm_controlled=confirm_controlled or (row.trust == merged["trust"] ==
                                                                      "trusted_local"), **merged)
        for k, v in fields.items():
            setattr(row, k, v)
        if changes.get("api_key"):
            row.api_key_encrypted = secrets.encrypt(changes["api_key"], encryption_key)
            row.api_key_last4 = secrets.last4(changes["api_key"])
        await tester(row, encryption_key)
        row.last_test_ok_at = row.updated_at = utcnow()
        row.updated_by = account_id
        db.add(row)
        db.add(AuditLog(account_id=account_id, action="model_endpoint.update",
                        target=f"model_endpoint:{row.id}", details={"changed": sorted(changes)}))
        db.commit()
        db.refresh(row)
        return view(row)


def delete_endpoint(engine, endpoint_id: int, *, course_id: int | None, account_id: int | None) -> None:
    """Settings that referred to it fall back to the next layer (foreign keys ON DELETE SET NULL)."""
    with Session(engine) as db:
        row = db.get(ModelEndpoint, endpoint_id)
        if row is None or row.course_id != course_id:
            raise EndpointError("unknown connection")
        db.delete(row)
        db.add(AuditLog(account_id=account_id, action="model_endpoint.delete",
                        target=f"model_endpoint:{endpoint_id}", details={"course_id": course_id}))
        db.commit()


def list_endpoints(engine, *, course_id: int | None) -> list[EndpointView]:
    with Session(engine) as db:
        rows = db.exec(select(ModelEndpoint).where(ModelEndpoint.course_id == course_id)
                       .order_by(ModelEndpoint.id)).all() if course_id is not None else \
            db.exec(select(ModelEndpoint).where(ModelEndpoint.course_id.is_(None)).order_by(ModelEndpoint.id)).all()
        return [view(r) for r in rows]


def check_keys_readable(engine, encryption_key: str | None) -> None:
    """At startup: refuse to run when stored API keys cannot be decrypted (design 6.3)."""
    with Session(engine) as db:
        row = db.exec(select(ModelEndpoint).where(ModelEndpoint.api_key_encrypted.is_not(None))
                      .limit(1)).first()
    if row is not None:
        secrets.decrypt(row.api_key_encrypted, encryption_key)
