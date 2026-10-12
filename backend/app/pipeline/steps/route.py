import asyncio

from app.core.registry import steps
from app.core.schemas import RequestContext, RouteInput
from app.pipeline.base import BaseStep


@steps.register("route")
class RouteStep(BaseStep):
    """Calls the configured router (Tongkai's black box) and compares the score with the threshold."""

    name = "route"
    on_error = "skip"  # target stays "local"

    async def run(self, ctx: RequestContext) -> RequestContext:
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
