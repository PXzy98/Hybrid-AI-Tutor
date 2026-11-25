"""The single path to the cloud (privacy invariants 2 and 3).

`build_cloud_request` decides WHAT may leave the privacy boundary; `CloudClient` is the only object that
sends anything, and it accepts nothing but a validated `CloudRequest`.
"""
from collections.abc import Sequence

from app.core.schemas import (
    CloudRequest,
    DraftCloudPassage,
    DraftCloudRequest,
    LearnerContext,
    LLMResult,
    RequestContext,
)
from app.llm.base import LLMClient, LLMUnavailable
from app.prompts import passage_text, render_cloud


def build_cloud_request(ctx: RequestContext) -> CloudRequest:
    """Allow-list: sanitized question, topic, course passages, coarse labels, the subject prompt's name, the
    instructor's guidelines. Nothing else."""
    if ctx.pii is None:
        raise ValueError("no privacy filter result: refusing to build a cloud request")
    learner = ctx.learner if ctx.learner and ctx.learner.personalized else LearnerContext()
    return CloudRequest(
        sanitized_question=ctx.pii.sanitized_text,
        topic=ctx.request.topic,
        passages=[passage_text(c) for c in ctx.passages],
        labels=learner.to_cloud_labels(),
        language=ctx.request.language,
        subject=ctx.profile.prompt if ctx.profile else "general",
        guidelines=list(ctx.guidelines),
    )


def build_draft_cloud_request(*, kind: str, passages: Sequence[tuple[int, str, str]], request: str = "",
                              kc_names: Sequence[str] = ()) -> DraftCloudRequest:
    """V16 allow-list of an instructor draft: (number, source, text) of the scanned course passages, the
    instructor's request and the accepted KC names, for one draft kind. Nothing else."""
    return DraftCloudRequest(
        kind=kind, request=request, kc_names=list(kc_names),
        passages=[DraftCloudPassage(number=n, source=s, text=t) for n, s, t in passages])


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

    async def complete(self, req: CloudRequest, *, safety_retry: bool = False) -> LLMResult:
        """Send a CloudRequest.

        `safety_retry` only adds a fixed instruction; no free text can reach the cloud through it.
        """
        if not isinstance(req, CloudRequest):
            raise TypeError("CloudClient accepts only a CloudRequest")
        # re-validate, even if it was built with model_construct
        req = CloudRequest.model_validate(req.model_dump())
        if self._transport is None:
            raise LLMUnavailable("cloud model not configured (CLOUD_API_KEY / CLOUD_MODEL)")
        result = await self._transport.complete(render_cloud(req, safety_retry=safety_retry))
        return result.model_copy(update={"backend": "cloud"})

    async def complete_draft(self, req: DraftCloudRequest) -> LLMResult:
        """V16: send an instructor draft request. The messages, the answer schema and the output limit are
        built here from the validated request and fixed instructions; the caller supplies no text."""
        if not isinstance(req, DraftCloudRequest):
            raise TypeError("complete_draft accepts only a DraftCloudRequest")
        req = DraftCloudRequest.model_validate(req.model_dump())
        if self._transport is None:
            raise LLMUnavailable("cloud model not configured (CLOUD_API_KEY / CLOUD_MODEL)")
        from app.instructor_ai.draft_cloud import render_draft

        messages, schema, max_tokens = render_draft(req)
        result = await self._transport.complete(messages, json_schema=schema, max_tokens=max_tokens)
        return result.model_copy(update={"backend": "cloud"})
