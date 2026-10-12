import logging

from app.core.registry import steps
from app.core.schemas import LLMResult, RequestContext
from app.llm.base import LLMError
from app.llm.cloud_guard import build_cloud_request
from app.pipeline.base import BaseStep
from app.prompts import render_local

log = logging.getLogger("app.pipeline")

CLOUD_FALLBACK_WARNING = "The cloud model was unavailable, so the local model answered."


@steps.register("generate")
class GenerateStep(BaseStep):
    """Local route: full context to the local model. Cloud route: only a CloudRequest, built by the guard.

    If the cloud model is not configured or fails, the local model answers (llm.cloud.fallback_to_local).
    """

    name = "generate"
    on_error = "stop"

    async def run(self, ctx: RequestContext) -> RequestContext:
        result = await self._cloud(ctx) if ctx.target == "cloud" else await self._local(ctx)
        ctx.llm = result
        ctx.answer = result.text
        return ctx

    async def _local(self, ctx: RequestContext) -> LLMResult:
        return await self.services.local_llm.complete(render_local(ctx))

    async def _cloud(self, ctx: RequestContext) -> LLMResult:
        cloud = self.services.cloud_llm
        if cloud.available:
            req = build_cloud_request(ctx)
            ctx.cloud_request = req  # kept for the leak checkers (Step 8) and the E4 audit
            try:
                return await cloud.complete(req)
            except LLMError as e:
                log.warning("cloud model failed (%s), request=%s", type(e).__name__, ctx.request_id)
                if not self.services.settings.llm.cloud.fallback_to_local:
                    raise
        elif not self.services.settings.llm.cloud.fallback_to_local:
            raise LLMError("cloud route chosen but no cloud model is configured")
        ctx.warnings.append(CLOUD_FALLBACK_WARNING)
        result = await self._local(ctx)
        return result.model_copy(update={"fell_back": True})
