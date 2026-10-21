import logging

from app.core.registry import steps
from app.core.schemas import CloudRequest, LLMResult, RequestContext
from app.llm.base import LLMError
from app.llm.cloud_guard import build_cloud_request
from app.pipeline.base import BaseStep
from app.privacy.analyzer import PIIAnalyzer
from app.privacy.generalize import generalize
from app.prompts import render_local
from app.verify.leaks import CloudLeakGuard

log = logging.getLogger("app.pipeline")

CLOUD_FALLBACK_WARNING = "The cloud model was unavailable, so the local model answered."
CLOUD_MISSING_WARNING = "No cloud model is connected, so the local model answered this question."
PRIVACY_BLOCK_WARNING = "A privacy check kept this question on the local model."
GENERALIZED_NOTE = ("For privacy, the cloud model received a general version of your question, without your "
                    "personal health details.")
LOCAL_CAPABILITY_NOTE = ("This question may be beyond what the local model does well; "
                         "please check the answer against the sources below.")


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
        if ctx.generalized_question and result.backend == "cloud" and GENERALIZED_NOTE not in ctx.warnings:
            ctx.warnings.append(GENERALIZED_NOTE)  # tell the student what the cloud actually saw
        return ctx

    async def produce(self, ctx: RequestContext, *, safety_retry: bool = False) -> LLMResult:
        """One answer on the chosen route. Also used by `verify` to regenerate after a safety failure."""
        if ctx.target == "cloud":
            return await self._cloud(ctx, safety_retry)
        return await self._local(ctx, safety_retry)

    async def _local(self, ctx: RequestContext, safety_retry: bool = False) -> LLMResult:
        return await self.services.local_llm.complete(render_local(ctx, safety_retry=safety_retry))

    async def _cloud(self, ctx: RequestContext, safety_retry: bool) -> LLMResult:
        """The cloud gate. The same privacy rules apply whichever router chose the cloud route:

        1. a personal health detail (not cloud_safe): `local_only` answers locally; `generalize` sends only a
           checked hypothetical rewrite of the question, or answers locally if the rewrite fails its checks;
        2. the leak guard re-checks the CloudRequest; a finding blocks it;
        3. a missing or failing cloud model falls back to the local model (llm.cloud.fallback_to_local).
        Every fallback tells the student why, and that the router expected the cloud model to do better.
        """
        req = await self._cloud_request(ctx)
        if req is None:
            return await self._fallback(ctx, safety_retry, PRIVACY_BLOCK_WARNING)
        found = self.leaks.problems(req, ctx)
        if found:  # never send; kinds only in the log, never the text
            log.error("cloud request blocked by the leak guard (%s), request=%s",
                      ", ".join(found), ctx.request_id)
            return await self._fallback(ctx, safety_retry, PRIVACY_BLOCK_WARNING)
        cloud = self.services.cloud_llm
        if not cloud.available:
            if not self.services.settings.llm.cloud.fallback_to_local:
                raise LLMError("cloud route chosen but no cloud model is configured")
            return await self._fallback(ctx, safety_retry, CLOUD_MISSING_WARNING)
        ctx.cloud_request = req  # what was actually sent: audited by the leak checkers and E4
        try:
            return await cloud.complete(req, safety_retry=safety_retry)
        except LLMError as e:
            log.warning("cloud model failed (%s), request=%s", type(e).__name__, ctx.request_id)
            if not self.services.settings.llm.cloud.fallback_to_local:
                raise
            return await self._fallback(ctx, safety_retry, CLOUD_FALLBACK_WARNING)

    async def _cloud_request(self, ctx: RequestContext) -> CloudRequest | None:
        """The CloudRequest to send, or None if the question must stay local (personal health detail)."""
        req = build_cloud_request(ctx)
        if ctx.pii.cloud_safe:
            return req
        if self.services.settings.privacy.health_detail_policy != "generalize":
            return None
        rewrite = ctx.generalized_question  # a safety retry reuses the rewrite of the first attempt
        if rewrite is None:
            names, usernames = self.services.accounts.identity_terms(ctx.request.student_id)
            local_only = set(self.services.settings.privacy.local_only_types)
            known = [e.text for e in ctx.pii.entities if e.type not in local_only]
            rewrite = await generalize(ctx.request.question, self.services.local_llm, self.leaks.analyzer,
                                       names, usernames, known)
        if rewrite is None:
            return None
        ctx.generalized_question = rewrite
        return req.model_copy(update={"sanitized_question": rewrite})

    async def _fallback(self, ctx: RequestContext, safety_retry: bool, reason: str) -> LLMResult:
        log.info("routed to cloud, answered locally (%s), request=%s", reason, ctx.request_id)
        for w in (reason, LOCAL_CAPABILITY_NOTE):
            if w not in ctx.warnings:
                ctx.warnings.append(w)
        result = await self._local(ctx, safety_retry)
        return result.model_copy(update={"fell_back": True})
