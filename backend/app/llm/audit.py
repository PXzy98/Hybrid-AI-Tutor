"""E4 privacy audit: record everything that is sent to the cloud (design §11 E4).

Installed through config, never by default:
- `llm.cloud.audit_log: <path>` wraps the cloud client so that every CloudRequest, and the exact messages
  given to the provider, are appended to a JSONL file. Recording happens after the CloudClient's own checks,
  right where the request would leave the process.
- `llm.cloud.audit_echo: true` replaces the provider with a local echo transport, so an audit can run without
  a cloud account. Nothing leaves the machine in that mode.
"""
import json
import threading
from pathlib import Path

from app.core.schemas import CloudRequest, LLMResult
from app.llm.base import Message
from app.llm.cloud_guard import CloudClient
from app.prompts import render_cloud

ECHO_ANSWER = "Recorded by the privacy audit. <PERSON_1> is a placeholder and stays as written."


class EchoTransport:
    """Stands in for the provider during an audit: answers with a fixed text, sends nothing anywhere."""

    model = "audit-echo"

    async def complete(self, messages: list[Message], *, json_schema: dict | None = None,
                       max_tokens: int | None = None) -> LLMResult:
        return LLMResult(text=ECHO_ANSWER, model=self.model, backend="cloud", latency_ms=0.0)


class RecordingCloudClient(CloudClient):
    def __init__(self, transport, path: str | Path) -> None:
        super().__init__(transport)
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._lock = threading.Lock()

    async def complete(self, req: CloudRequest, *, safety_retry: bool = False) -> LLMResult:
        if isinstance(req, CloudRequest) and self.available:
            checked = CloudRequest.model_validate(req.model_dump())  # what CloudClient.complete will send
            record = {"cloud_request": checked.model_dump(mode="json"), "safety_retry": safety_retry,
                      "messages": render_cloud(checked, safety_retry=safety_retry)}
            with self._lock, self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(record, ensure_ascii=False) + "\n")
        return await super().complete(req, safety_retry=safety_retry)
