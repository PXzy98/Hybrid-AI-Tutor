"""The single path to the cloud (privacy invariants 2 and 3).

`build_cloud_request` decides WHAT may leave the privacy boundary; `CloudClient` is the only object that
sends anything, and it accepts nothing but a validated `CloudRequest`.
"""
from app.core.schemas import CloudRequest, LearnerContext, LLMResult, RequestContext
from app.llm.base import LLMClient, LLMUnavailable
from app.prompts import render_cloud


def build_cloud_request(ctx: RequestContext) -> CloudRequest:
    """Allow-list: sanitized question, topic, course passages, coarse labels. Nothing else."""
    if ctx.pii is None:
        raise ValueError("no privacy filter result: refusing to build a cloud request")
    learner = ctx.learner if ctx.learner and ctx.learner.personalized else LearnerContext()
    return CloudRequest(
        sanitized_question=ctx.pii.sanitized_text,
        topic=ctx.request.topic,
        passages=[c.text for c in ctx.passages],
        labels=learner.to_cloud_labels(),
        language=ctx.request.language,
    )


class CloudClient:
    """Wraps a transport (an OpenAI-compatible client). Its ONLY public method takes a CloudRequest."""

    def __init__(self, transport: LLMClient | None) -> None:
        self._transport = transport

    @property
    def available(self) -> bool:
        return self._transport is not None

    @property
    def model(self) -> str | None:
        return self._transport.model if self._transport else None

    async def complete(self, req: CloudRequest) -> LLMResult:
        if not isinstance(req, CloudRequest):
            raise TypeError("CloudClient accepts only a CloudRequest")
        # re-validate, even if it was built with model_construct
        req = CloudRequest.model_validate(req.model_dump())
        if self._transport is None:
            raise LLMUnavailable("cloud model not configured (CLOUD_API_KEY / CLOUD_MODEL)")
        result = await self._transport.complete(render_cloud(req))
        return result.model_copy(update={"backend": "cloud"})
