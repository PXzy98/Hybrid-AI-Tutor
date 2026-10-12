from app.core.config import Settings
from app.llm.base import LLMClient, LLMError, LLMUnavailable
from app.llm.cloud_guard import CloudClient
from app.llm.ollama_client import OllamaClient
from app.llm.openai_compat import OpenAICompatClient

__all__ = ["CloudClient", "LLMClient", "LLMError", "LLMUnavailable", "build_llm_clients"]


def build_llm_clients(settings: Settings) -> tuple[LLMClient, CloudClient]:
    """The local client (Ollama) and the cloud client (unavailable when no key/model is configured)."""
    loc = settings.llm.local
    local = OllamaClient(settings.ollama_url, loc.model, temperature=loc.temperature, num_ctx=loc.num_ctx,
                         timeout_s=loc.timeout_s, max_tokens=loc.max_tokens)
    transport = None
    if settings.cloud_enabled:
        cloud = settings.llm.cloud
        transport = OpenAICompatClient(settings.cloud_base_url, settings.cloud_api_key.get_secret_value(),
                                       settings.cloud_model, timeout_s=cloud.timeout_s,
                                       max_tokens=cloud.max_tokens)
    return local, CloudClient(transport)
