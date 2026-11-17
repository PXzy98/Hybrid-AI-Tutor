"""The deployment's local model (vLLM, VLLM_BASE_URL / VLLM_KEY) for the evaluation scripts.

The same server and request shape as the app's trusted local client (`app/llm/factory.py`): the
OpenAI-compatible chat API, thinking off, structured answers constrained to their JSON schema.
"""
import time

import httpx


def chat(http: httpx.Client, settings, messages: list[dict], *, model: str | None = None,
         schema: dict | None = None, temperature: float = 0.0, max_tokens: int = 1024,
         seed: int | None = None, tries: int = 3) -> str | None:
    """The answer text, or None if the server keeps failing (callers decide how to fail)."""
    if not settings.vllm_base_url:
        raise SystemExit("set VLLM_BASE_URL (and VLLM_KEY) in .env: the local model server")
    key = settings.vllm_key.get_secret_value() if settings.vllm_key else None
    body = {"model": model or settings.llm.local.model, "messages": messages, "temperature": temperature,
            "max_tokens": max_tokens, "chat_template_kwargs": {"enable_thinking": False}}
    if schema is not None:
        body["response_format"] = {"type": "json_schema", "json_schema": {"name": "answer", "schema": schema}}
    if seed is not None:
        body["seed"] = seed
    url = f"{settings.vllm_base_url.rstrip('/')}/chat/completions"
    for _ in range(tries):
        try:
            r = http.post(url, json=body, headers={"Authorization": f"Bearer {key}"} if key else {})
            r.raise_for_status()
            return r.json()["choices"][0]["message"]["content"] or ""
        except (httpx.HTTPError, KeyError, IndexError, ValueError):
            time.sleep(5)
    return None
