import asyncio

from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep
from app.pipeline.settings_view import router_of, routing_threshold
from app.pipeline.steps.analyze_route import route_input
from app.platform import course_scope


@steps.register("retrieve")
class RetrieveStep(BaseStep):
    """Calls the configured retriever (Siyun's black box) with the SANITIZED question."""

    name = "retrieve"
    on_error = "skip"  # no passages; the answer says so

    async def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.pii is None:
            raise RuntimeError("retrieve needs the privacy filter result")
        cfg = self.services.settings
        impl, router = router_of(ctx, self.services)
        if impl == "semantic" and ctx.semantic_analysis is not None:
            threshold = routing_threshold(ctx, self.services)
            capable = router.capable(ctx.semantic_analysis, threshold)
            # The shortcut only saves the lookup for a hard concept question on the demo corpus. Inside a
            # course, and for a logistics question, the cloud answer must still see the course's own rules
            # (syllabus, policies); its passages reach the cloud only through the CloudRequest allow-list.
            if not capable and ctx.question_type != "logistics" and course_scope.current() is None:
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
            with course_scope.question_kind(ctx.question_type):  # logistics: course-level files first
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
