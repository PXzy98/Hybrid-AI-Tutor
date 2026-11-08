"""Task Z6: model connections, SSRF protection, encrypted keys, trust rules, queueing and streaming."""
import asyncio
import ipaddress

import pytest
from cryptography.fernet import Fernet
from sqlmodel import Session, select

from app.core.services import build_services
from app.llm import endpoints
from app.llm.base import LLMUnavailable
from app.llm.endpoints import EndpointError, create_endpoint, delete_endpoint
from app.llm.fake import FakeLLMClient
from app.llm.gateway import TrustViolation
from app.llm.ssrf import UnsafeEndpoint, check_endpoint_url
from app.storage.models import AuditLog, ModelEndpoint

KEY = Fernet.generate_key().decode()
PUBLIC = "https://93.184.216.34/v1"  # a public address literal: no DNS needed


def _resolve(mapping):
    return lambda host: [ipaddress.ip_address(mapping.get(host, host))]


def _ok(url, trust="external", **kw):
    return check_endpoint_url(url, trust=trust, system=lambda: frozenset(), **kw)


async def _passes(row, key):
    return None


# ----------------------------------------------------------------------------------------------- SSRF
@pytest.mark.parametrize("url", [
    "http://169.254.169.254/latest/meta-data", "http://[fe80::1]:11434", "http://metadata.google.internal/",
    "http://db:5432", "http://api:8000", "ftp://93.184.216.34/", "https://user:pw@93.184.216.34/v1",
    "http://0.0.0.0:11434", "http://224.0.0.1/",
])
def test_unsafe_addresses_are_rejected_for_every_trust_level(url):
    for trust in ("trusted_local", "external"):
        with pytest.raises(UnsafeEndpoint):
            _ok(url, trust=trust)


@pytest.mark.parametrize("url", ["http://10.0.0.5:11434", "http://192.168.2.25:11434", "http://127.0.0.1:11434"])
def test_private_addresses_only_for_trusted_local_connections(url):
    assert _ok(url, trust="trusted_local") == url
    with pytest.raises(UnsafeEndpoint):
        _ok(url, trust="external")


def test_names_are_checked_by_what_they_resolve_to():
    with pytest.raises(UnsafeEndpoint):  # a public-looking name that resolves to cloud metadata
        _ok("https://models.example.org/v1", resolve=_resolve({"models.example.org": "169.254.169.254"}))
    with pytest.raises(UnsafeEndpoint):  # the address of one of the system's own services
        check_endpoint_url("http://10.0.0.7:8000", trust="trusted_local",
                           system=lambda: frozenset({ipaddress.ip_address("10.0.0.7")}))
    assert _ok(PUBLIC) == PUBLIC


# ------------------------------------------------------------------------------------------- registry
@pytest.fixture
def services(use_config, monkeypatch):
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", KEY)
    return build_services(use_config())


def _create(services, **kw):
    args = dict(course_id=None, name="Cloud", kind="openai_compat", base_url=PUBLIC, model="gpt-test",
                trust="external", api_key="sk-test-0123456789", confirm_controlled=False, account_id=1,
                encryption_key=KEY, tester=_passes)
    args.update(kw)
    return asyncio.run(create_endpoint(services.engine, **args))


def test_keys_are_encrypted_and_never_returned(services):
    v = _create(services)
    assert v.api_key_last4 == "6789" and not hasattr(v, "api_key_encrypted")
    with Session(services.engine) as db:
        row = db.get(ModelEndpoint, v.id)
        assert "sk-test" not in row.api_key_encrypted
        assert db.exec(select(AuditLog).where(AuditLog.action == "model_endpoint.create")).one()
    with pytest.raises(Exception, match="SETTINGS_ENCRYPTION_KEY"):
        _create(services, encryption_key=None)


def test_trusted_local_needs_confirmation_and_a_failing_test_stores_nothing(services):
    with pytest.raises(EndpointError, match="control"):
        _create(services, trust="trusted_local", base_url="http://10.0.0.5:11434", kind="ollama",
                api_key=None)

    async def fails(row, key):
        raise EndpointError("the connection test failed (LLMUnavailable)")

    with pytest.raises(EndpointError, match="test failed"):
        _create(services, tester=fails)
    with Session(services.engine) as db:
        assert db.exec(select(ModelEndpoint)).all() == []


def test_deleting_a_connection_resets_the_settings_that_used_it(services):
    v = _create(services)
    service = services.settings_service
    service.save_system({"default_cloud_endpoint_id": v.id}, expected_version=0, account_id=1)
    assert services.effective().cloud_endpoint_id == v.id
    delete_endpoint(services.engine, v.id, course_id=None, account_id=1)
    assert service.system_values()[0]["default_cloud_endpoint_id"] is None


def test_settings_only_accept_matching_connections(services):
    from app.platform.settings import SettingsError

    external = _create(services)
    with pytest.raises(SettingsError, match="trusted local"):
        services.settings_service.save_system({"default_local_endpoint_id": external.id}, expected_version=0,
                                              account_id=1)
    with pytest.raises(SettingsError, match="unknown"):
        services.settings_service.save_course(services.content.course_id, {"cloud_endpoint_id": 999},
                                              expected_version=0, account_id=1)


def test_stored_keys_need_the_encryption_key_at_startup(services, use_config, monkeypatch):
    _create(services)
    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", Fernet.generate_key().decode())  # a different key
    with pytest.raises(Exception, match="SETTINGS_ENCRYPTION_KEY"):
        build_services(use_config())


# -------------------------------------------------------------------------------------------- gateway
def _fake_clients(monkeypatch, client):
    monkeypatch.setattr(endpoints, "build_client", lambda row, key, **kw: client)


def test_the_course_connection_is_used_and_trust_is_enforced(services, monkeypatch):
    external = FakeLLMClient("external answer", backend="cloud")
    _fake_clients(monkeypatch, external)
    v = _create(services)
    demo = services.content.course_id
    services.settings_service.save_course(demo, {"cloud_endpoint_id": v.id}, expected_version=0, account_id=1)
    eff = services.effective()
    gateway = services.gateway
    with pytest.raises(TrustViolation):
        asyncio.run(gateway.complete("cloud", [{"role": "user", "content": "x"}], settings=eff,
                                     trust_required="trusted_local"))
    assert external.calls == []
    result = asyncio.run(gateway.complete("cloud", [{"role": "user", "content": "x"}], settings=eff,
                                          trust_required="external_ok"))
    assert result.text == "external answer"
    local_only = eff.model_copy(update={"local_only": True})
    with pytest.raises(LLMUnavailable):
        asyncio.run(gateway.complete("cloud", [{"role": "user", "content": "y"}], settings=local_only,
                                     trust_required="external_ok"))
    assert len(external.calls) == 1


def test_the_url_is_checked_again_before_each_call(services, monkeypatch):
    _fake_clients(monkeypatch, FakeLLMClient("answer"))
    v = _create(services)
    services.settings_service.save_system({"default_cloud_endpoint_id": v.id}, expected_version=0,
                                          account_id=1)

    def now_unsafe(url, *, trust, **kw):
        raise UnsafeEndpoint("link-local and special addresses (e.g. cloud metadata) are not allowed")

    monkeypatch.setattr("app.llm.ssrf.check_endpoint_url", now_unsafe)
    with pytest.raises(UnsafeEndpoint):
        asyncio.run(services.gateway.complete("cloud", [{"role": "user", "content": "x"}],
                                              settings=services.effective(), trust_required="external_ok"))


def test_requests_wait_for_a_slot_and_time_out_when_busy(use_config, monkeypatch):
    services = build_services(use_config({"limits": {"models": {"max_concurrent": 1,
                                                                "queue_timeout_seconds": 0.2}}}))
    started = asyncio.Event()

    class Slow:
        model = "slow"

        async def complete(self, messages, *, json_schema=None, max_tokens=None):
            started.set()
            await asyncio.sleep(1)
            return await FakeLLMClient("done").complete(messages)

    services.local_llm = Slow()
    eff = services.effective()

    async def two():
        first = asyncio.create_task(services.gateway.complete(
            "local", [{"role": "user", "content": "a"}], settings=eff, trust_required="trusted_local"))
        await started.wait()
        with pytest.raises(LLMUnavailable, match="busy"):
            await services.gateway.complete("local", [{"role": "user", "content": "b"}], settings=eff,
                                            trust_required="trusted_local")
        return await first

    assert asyncio.run(two()).text == "done"


def test_tokens_are_streamed(services):
    services.local_llm = FakeLLMClient("one two three")

    async def collect():
        tokens = await services.gateway.complete("local", [{"role": "user", "content": "x"}],
                                                 settings=services.effective(),
                                                 trust_required="trusted_local", stream=True)
        return [t async for t in tokens]

    assert asyncio.run(collect()) == ["one ", "two ", "three"]


def test_an_external_course_connection_receives_only_the_sanitized_cloud_request(make_client, monkeypatch):
    from tests.conftest import PASSWORD

    monkeypatch.setenv("SETTINGS_ENCRYPTION_KEY", KEY)
    external = FakeLLMClient("Cloud answer.", model="course-gpt", backend="cloud")
    _fake_clients(monkeypatch, external)
    with make_client({"routing": {"stub_score": 1.0}}) as client:
        services = client.app.state.services
        services.local_llm = FakeLLMClient("Local answer.")
        v = _create(services)
        services.settings_service.save_course(services.content.course_id, {"cloud_endpoint_id": v.id},
                                              expected_version=0, account_id=None)
        account, _ = services.accounts.create_student("alice", "Alice Tremblay")
        services.accounts.set_password(account.id, PASSWORD, must_change=False)
        services.learner.set_consent(account.student_id, True)
        client.post("/api/v1/auth/login", json={"username": "alice", "password": PASSWORD})
        question = "My name is Alice Tremblay, student 300418277. Why is salt bad for blood pressure?"
        reply = client.post("/api/v1/ask", json={"topic": "high_blood_pressure", "question": question}).json()
    assert reply["route_target"] == "cloud" and reply["model_used"] == "course-gpt"
    sent = external.sent_text()
    assert "Alice" not in sent and "Tremblay" not in sent and "300418277" not in sent



def test_connections_are_pinned_to_the_checked_address():
    """DNS rebinding: the connection goes to the checked address, with the original Host and TLS name."""
    import httpx

    from app.llm.ssrf import PinnedTransport

    seen = {}

    class Inner:
        async def handle_async_request(self, request):
            seen.update(url=str(request.url), host=request.headers["Host"],
                        sni=request.extensions.get("sni_hostname"))
            return httpx.Response(200, json={"ok": True})

    answers = iter(["93.184.216.34", "169.254.169.254"])  # safe for the check, metadata afterwards
    transport = PinnedTransport(trust="external", inner=Inner(), system=lambda: frozenset(),
                                resolve=lambda host: [ipaddress.ip_address(next(answers))])

    async def call():
        async with httpx.AsyncClient(transport=transport) as client:
            return await client.get("https://models.example.org/v1/models")

    assert asyncio.run(call()).status_code == 200
    assert seen == {"url": "https://93.184.216.34/v1/models", "host": "models.example.org",
                    "sni": "models.example.org"}

    rebinding = PinnedTransport(trust="external", inner=Inner(), system=lambda: frozenset(),
                                resolve=lambda host: [ipaddress.ip_address("169.254.169.254")])

    async def blocked():
        async with httpx.AsyncClient(transport=rebinding) as client:
            await client.get("https://models.example.org/v1/models")

    with pytest.raises(UnsafeEndpoint):
        asyncio.run(blocked())


def test_deleting_a_connection_makes_cached_settings_fall_back(services):
    v = _create(services)
    service, demo = services.settings_service, services.content.course_id
    service.save_course(demo, {"cloud_endpoint_id": v.id}, expected_version=0, account_id=1)
    assert services.effective().cloud_endpoint_id == v.id  # cached now
    delete_endpoint(services.engine, v.id, course_id=None, account_id=1)
    assert services.effective().cloud_endpoint_id is None


def test_the_default_cloud_connection_is_queued_and_trusted_results_are_local(services, monkeypatch):
    from app.llm.cloud_guard import CloudClient

    services.cloud_llm = CloudClient(FakeLLMClient("cloud"))
    eff = services.effective()
    assert type(services.gateway.cloud_client(eff)).__name__ == "_QueuedCloud"
    vllm = FakeLLMClient("from vLLM", backend="cloud")  # an OpenAI-compatible client reports "cloud"
    _fake_clients(monkeypatch, vllm)
    v = _create(services, kind="openai_compat", trust="trusted_local", base_url="http://10.0.0.5:8000/v1",
                confirm_controlled=True, api_key=None)
    services.settings_service.save_course(services.content.course_id, {"local_endpoint_id": v.id},
                                          expected_version=0, account_id=1)
    result = asyncio.run(services.gateway.complete("local", [{"role": "user", "content": "x"}],
                                                   settings=services.effective(),
                                                   trust_required="trusted_local"))
    assert result.backend == "local"
