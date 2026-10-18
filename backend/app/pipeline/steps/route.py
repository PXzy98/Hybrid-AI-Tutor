import asyncio
from time import perf_counter

from app.core.registry import steps
from app.core.schemas import RequestContext, RouteInput
from app.pipeline.base import BaseStep
from app.pipeline.steps.analyze_route import route_input
from app.routing.evidence import assess_evidence


@steps.register("route")
class RouteStep(BaseStep):
    """Calls the configured router (Tongkai's black box) and compares the score with the threshold."""

    name = "route"
    on_error = "skip"  # target stays "local"

    async def run(self, ctx: RequestContext) -> RequestContext:
        if self.services.settings.routing.impl == "semantic":
            return await self._semantic(ctx)
        ctx.target = "local"  # safe default if anything below fails
        if ctx.pii is None:
            raise RuntimeError("route needs the privacy filter result")
        cfg = self.services.settings.routing
        learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
        x = RouteInput(
            sanitized_question=ctx.pii.sanitized_text,
            topic=ctx.request.topic,
            pii=ctx.pii,
            passage_count=len(ctx.passages),
            level=learner.focus_level if learner else None,
            kc_ids=ctx.understanding.kc_ids if ctx.understanding else [],
        )
        score = await asyncio.to_thread(self.services.router.route_score, x)
        if score.score >= cfg.threshold:
            if cfg.force_local_if_not_cloud_safe and not ctx.pii.cloud_safe:
                score = score.model_copy(update={"reasons": [*score.reasons, "forced local: not cloud_safe"]})
            else:
                ctx.target = "cloud"
        ctx.route = score
        return ctx

    async def _semantic(self, ctx):
        # TEAM INTEGRATION: no pii/cloud_safe routing condition. Privacy belongs
        # to the teammate-owned upstream filter, independently of this decision.
        ctx.target = "cloud"  # failures must never silently admit a question to Local
        router = self.services.router
        x = route_input(ctx)
        analysis = ctx.semantic_analysis or await asyncio.to_thread(router.analyze, x)
        threshold = self.services.settings.routing.threshold
        if router.capable(analysis, threshold):
            t0 = perf_counter()
            await ctx.report("evidence", "running", "Checking relevance and question support.")
            evidence = await asyncio.to_thread(assess_evidence, x, analysis, router.cfg)
            await ctx.report(
                "evidence", "completed", f"{evidence.status}: {evidence.reason}", (perf_counter() - t0) * 1000
            )
        else:
            evidence = None
            await ctx.report("evidence", "skipped", "Capability/uncertainty gate did not pass.")
        t0 = perf_counter()
        await ctx.report("decision", "running", "Applying independent capability and evidence conditions.")
        score = router.decide(x, analysis, threshold, evidence)
        ctx.route = score
        ctx.target = score.target
        # Preserve original indices in diagnostics; only verified passages reach prompts/sources.
        ctx.passages = [x.passages[i] for i in score.accepted_indices]
        await ctx.report(
            "decision",
            "completed",
            f"{ctx.target.upper()} selected using {score.method.upper()}.",
            (perf_counter() - t0) * 1000,
        )
        return ctx
