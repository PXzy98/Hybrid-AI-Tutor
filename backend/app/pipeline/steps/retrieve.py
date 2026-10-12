import asyncio

from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("retrieve")
class RetrieveStep(BaseStep):
    """Calls the configured retriever (Siyun's black box) with the SANITIZED question."""

    name = "retrieve"
    on_error = "skip"  # no passages; the answer says so

    async def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.pii is None:
            raise RuntimeError("retrieve needs the privacy filter result")
        learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
        ctx.passages = await asyncio.to_thread(
            self.services.retriever.retrieve,
            ctx.pii.sanitized_text,
            ctx.request.topic,
            self.services.settings.rag.k,
            ctx.understanding.kc_ids if ctx.understanding and ctx.understanding.kc_ids else None,
            learner.focus_level if learner else None,
        )
        return ctx
