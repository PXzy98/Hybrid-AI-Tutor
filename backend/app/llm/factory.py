"""Builds the configured LLM clients (kept out of app/llm/__init__.py to avoid import cycles)."""
from app.core.config import Settings
from app.llm.base import LLMClient, LLMUnavailable, Message
from app.llm.cloud_guard import CloudClient
from app.llm.openai_compat import OpenAICompatClient


class NoLocalServer:
    """Stands in for the local model when VLLM_BASE_URL is not set: every call fails like an unreachable
    server, so each caller's own failure rule applies (answers report the model as unavailable, understand
    is skipped, generalize and llm_check keep the question local)."""

    def __init__(self, model: str) -> None:
        self.model = model

    async def complete(self, messages: list[Message], *, json_schema=None, max_tokens=None):
        raise LLMUnavailable("no local model server (set VLLM_BASE_URL)")

    async def stream(self, messages: list[Message], *, json_schema=None, max_tokens=None):
        raise LLMUnavailable("no local model server (set VLLM_BASE_URL)")
        yield ""  # pragma: no cover  (makes this an async generator)


def build_local_client(settings: Settings, model: str, *, temperature: float, timeout_s: float,
                       max_tokens: int) -> LLMClient:
    """A client of the deployment's own model server (vLLM, OpenAI-compatible): trusted local, so thinking is
    off and structured answers are constrained to their JSON schema."""
    if not settings.vllm_base_url:
        return NoLocalServer(model)
    key = settings.vllm_key.get_secret_value() if settings.vllm_key else "none"
    return OpenAICompatClient(settings.vllm_base_url.rstrip("/"), key, model, timeout_s=timeout_s,
                              max_tokens=max_tokens, temperature=temperature, thinking_off=True,
                              schema_output=True, backend="local")


def build_llm_clients(settings: Settings) -> tuple[LLMClient, CloudClient, LLMClient]:
    """The local answer client, the cloud client (unavailable without key/model) and the local client for the
    understand step (JSON, deterministic, short timeout); both local clients use the deployment's vLLM."""
    loc = settings.llm.local
    local = build_local_client(settings, loc.model, temperature=loc.temperature, timeout_s=loc.timeout_s,
                               max_tokens=loc.max_tokens)
    transport = None
    if settings.cloud_enabled:
        cloud = settings.llm.cloud
        transport = OpenAICompatClient(settings.cloud_base_url, settings.cloud_api_key.get_secret_value(),
                                       settings.cloud_model, timeout_s=cloud.timeout_s,
                                       max_tokens=cloud.max_tokens)
    cloud_client = CloudClient(transport)
    if settings.llm.cloud.audit_log or settings.llm.cloud.audit_echo:  # E4 privacy audit only
        from app.llm.audit import EchoTransport, RecordingCloudClient

        transport = EchoTransport() if settings.llm.cloud.audit_echo else transport
        cloud_client = (RecordingCloudClient(transport, settings.llm.cloud.audit_log)
                        if settings.llm.cloud.audit_log else CloudClient(transport))
    und = settings.llm.understand
    understand = build_local_client(settings, und.model, temperature=0.0, timeout_s=und.timeout_s,
                                    max_tokens=200)
    return local, cloud_client, understand
