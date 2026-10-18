import asyncio

from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep
from app.pipeline.steps.analyze_route import route_input


@steps.register("retrieve")
class RetrieveStep(BaseStep):
    """Calls the configured retriever (Siyun's black box) with the SANITIZED question."""

    name = "retrieve"
    on_error = "skip"  # no passages; the answer says so

    async def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.pii is None:
            raise RuntimeError("retrieve needs the privacy filter result")
        cfg = self.services.settings
        if cfg.routing.impl == "semantic" and ctx.semantic_analysis is not None:
            if not self.services.router.capable(ctx.semantic_analysis, cfg.routing.threshold):
                ctx.retrieval_status = "skipped"
                await ctx.report("retrieval", "skipped", "Capability gate selected Cloud before retrieval.")
                return ctx
        if cfg.rag.impl == "stub":
            ctx.retrieval_status = "disabled"
            ctx.passages = []
            await ctx.report("retrieval", "skipped", "RAG is not connected; evidence is unavailable.")
            return ctx
        learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
        from time import perf_counter

        t0 = perf_counter()
        await ctx.report("retrieval", "running", "Retrieving course material.")
        try:
            ctx.passages = await asyncio.to_thread(
                self.services.retriever.retrieve,
                route_input(ctx).contextual_question,
                ctx.request.topic,
                cfg.rag.k,
                ctx.understanding.kc_ids if ctx.understanding and ctx.understanding.kc_ids else None,
                learner.focus_level if learner else None,
            )
            ctx.retrieval_status = "returned" if ctx.passages else "empty"
            await ctx.report(
                "retrieval",
                "completed",
                f"Retrieved {len(ctx.passages)} passages.",
                (perf_counter() - t0) * 1000,
            )
        except Exception:
            ctx.passages = []
            ctx.retrieval_status = "error"
            await ctx.report(
                "retrieval", "failed", "Retrieval failed; no evidence assumed.", (perf_counter() - t0) * 1000
            )
        return ctx
