"""Builds the configured LLM clients (kept out of app/llm/__init__.py to avoid import cycles)."""
from app.core.config import Settings
from app.llm.base import LLMClient
from app.llm.cloud_guard import CloudClient
from app.llm.ollama_client import OllamaClient
from app.llm.openai_compat import OpenAICompatClient


def build_llm_clients(settings: Settings) -> tuple[LLMClient, CloudClient, LLMClient]:
    """The local answer client (Ollama), the cloud client (unavailable without key/model) and the local client
    for the understand step (JSON, deterministic, short timeout)."""
    loc = settings.llm.local
    local = OllamaClient(settings.ollama_url, loc.model, temperature=loc.temperature, num_ctx=loc.num_ctx,
                         timeout_s=loc.timeout_s, max_tokens=loc.max_tokens)
    transport = None
    if settings.cloud_enabled:
        cloud = settings.llm.cloud
        transport = OpenAICompatClient(settings.cloud_base_url, settings.cloud_api_key.get_secret_value(),
                                       settings.cloud_model, timeout_s=cloud.timeout_s,
                                       max_tokens=cloud.max_tokens)
    und = settings.llm.understand
    # same num_ctx as the answer client: with the same model, a different context size would make Ollama
    # reload the model between the two calls of every request
    understand = OllamaClient(settings.ollama_url, und.model, temperature=0.0, num_ctx=loc.num_ctx,
                              timeout_s=und.timeout_s, max_tokens=200)
    return local, CloudClient(transport), understand
