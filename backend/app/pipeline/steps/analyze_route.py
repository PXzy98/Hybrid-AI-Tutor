"""Semantic pre-screen; runs before RAG, with no answering-LLM judge."""

import asyncio
from time import perf_counter

from app.core.registry import steps
from app.core.schemas import RequestContext, RouteInput, SemanticAnalysis
from app.pipeline.base import BaseStep


def route_input(ctx: RequestContext) -> RouteInput:
    return RouteInput(
        sanitized_question=ctx.pii.sanitized_text if ctx.pii else ctx.request.question,
        topic=ctx.request.topic,
        pii=ctx.pii,
        passage_count=len(ctx.passages),
        passages=ctx.passages,
        method=ctx.request.routing_method,
        retrieval_status=ctx.retrieval_status,
        conversation_context="\n".join(t.text for t in ctx.history[-4:] if t.role == "student"),
        level=ctx.learner.focus_level if ctx.learner and ctx.learner.personalized else None,
        kc_ids=ctx.understanding.kc_ids if ctx.understanding else [],
    )


@steps.register("analyze_route")
class AnalyzeRouteStep(BaseStep):
    name = "analyze_route"
    on_error = "stop"

    async def run(self, ctx):
        if self.services.settings.routing.impl != "semantic":
            return ctx
        router = self.services.router
        method = ctx.request.routing_method or self.services.settings.routing.default_method
        t0 = perf_counter()
        await ctx.report("embedding", "running", "Encoding the question locally.")
        try:
            vector = await asyncio.to_thread(router.embed, route_input(ctx).contextual_question)
            await ctx.report(
                "embedding", "completed", "Local semantic vector ready.", (perf_counter() - t0) * 1000
            )
        except Exception:
            ctx.semantic_analysis = SemanticAnalysis(
                method=method, reason="Semantic encoder unavailable or input too long."
            )
            await ctx.report(
                "embedding", "failed", "Encoder unavailable; selecting Cloud.", (perf_counter() - t0) * 1000
            )
            await ctx.report("classification", "skipped", "No usable semantic vector.")
            return ctx
        t0 = perf_counter()
        await ctx.report(
            "classification", "running", f"Applying {method.upper()} capability and evidence heads."
        )
        try:
            ctx.semantic_analysis = await asyncio.to_thread(router.classify, vector, method)
            a = ctx.semantic_analysis
            await ctx.report(
                "classification",
                "completed",
                f"Cloud need {a.cloud_probability:.1%}; evidence required: {a.requires_evidence}.",
                (perf_counter() - t0) * 1000,
            )
        except Exception:
            ctx.semantic_analysis = SemanticAnalysis(
                method=method, reason="Classifier weights unavailable or incompatible."
            )
            await ctx.report(
                "classification",
                "failed",
                "Classifier unavailable; selecting Cloud.",
                (perf_counter() - t0) * 1000,
            )
        return ctx
