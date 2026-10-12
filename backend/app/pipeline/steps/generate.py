import logging

from app.core.registry import steps
from app.core.schemas import LLMResult, RequestContext
from app.llm.base import LLMError
from app.llm.cloud_guard import build_cloud_request
from app.pipeline.base import BaseStep
from app.privacy.analyzer import PIIAnalyzer
from app.prompts import render_local
from app.verify.leaks import CloudLeakGuard

log = logging.getLogger("app.pipeline")

CLOUD_FALLBACK_WARNING = "The cloud model was unavailable, so the local model answered."
PRIVACY_BLOCK_WARNING = "A privacy check kept this question on the local model."


@steps.register("generate")
class GenerateStep(BaseStep):
    """Local route: full context to the local model. Cloud route: only a CloudRequest, built by the guard.

    Before anything is sent, the leak guard re-checks the CloudRequest (PII, student_id, item IDs,
    misconception text); a finding blocks the request and the local model answers instead. If the cloud
    model is not configured or fails, the local model answers too (llm.cloud.fallback_to_local).
    """

    name = "generate"
    on_error = "stop"

    def __init__(self, services) -> None:
        super().__init__(services)
        self.leaks = CloudLeakGuard(PIIAnalyzer(services.settings.privacy), services.content)

    async def run(self, ctx: RequestContext) -> RequestContext:
        result = await self.produce(ctx)
        ctx.llm = result
        ctx.answer = result.text
        return ctx

    async def produce(self, ctx: RequestContext, *, safety_retry: bool = False) -> LLMResult:
        """One answer on the chosen route. Also used by `verify` to regenerate after a safety failure."""
        if ctx.target == "cloud":
            return await self._cloud(ctx, safety_retry)
        return await self._local(ctx, safety_retry)

    async def _local(self, ctx: RequestContext, safety_retry: bool = False) -> LLMResult:
        return await self.services.local_llm.complete(render_local(ctx, safety_retry=safety_retry))

    async def _cloud(self, ctx: RequestContext, safety_retry: bool) -> LLMResult:
        cloud = self.services.cloud_llm
        if cloud.available:
            req = build_cloud_request(ctx)
            found = self.leaks.problems(req, ctx)
            if found:  # never send; kinds only in the log, never the text
                log.error("cloud request blocked by the leak guard (%s), request=%s", ", ".join(found),
                          ctx.request_id)
                if PRIVACY_BLOCK_WARNING not in ctx.warnings:
                    ctx.warnings.append(PRIVACY_BLOCK_WARNING)
                return (await self._local(ctx, safety_retry)).model_copy(update={"fell_back": True})
            ctx.cloud_request = req  # what was actually sent: audited by the leak checkers and E4
            try:
                return await cloud.complete(req, safety_retry=safety_retry)
            except LLMError as e:
                log.warning("cloud model failed (%s), request=%s", type(e).__name__, ctx.request_id)
                if not self.services.settings.llm.cloud.fallback_to_local:
                    raise
        elif not self.services.settings.llm.cloud.fallback_to_local:
            raise LLMError("cloud route chosen but no cloud model is configured")
        if CLOUD_FALLBACK_WARNING not in ctx.warnings:
            ctx.warnings.append(CLOUD_FALLBACK_WARNING)
        result = await self._local(ctx, safety_retry)
        return result.model_copy(update={"fell_back": True})
