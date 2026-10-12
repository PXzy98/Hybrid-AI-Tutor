import logging

from app.core.registry import checkers, import_submodules, steps
from app.core.schemas import CheckResult, RequestContext
from app.pipeline.base import BaseStep
from app.pipeline.steps.generate import GenerateStep
from app.privacy.anonymizer import restore

log = logging.getLogger("app.pipeline")

REFERRAL = "For advice about your own situation, please talk to a doctor, nurse or pharmacist."
SAFE_FALLBACK = ("I can't give a safe general answer to this question here. Questions about your own health, "
                 "medicines or doses need a doctor, nurse or pharmacist, who can look at your situation.")
SAFE_FALLBACK_SOURCES = " The course material listed below explains this topic in general terms."
REPLACED_WARNING = "The first answer did not pass the safety check and was replaced with a safe message."
WARNINGS = {
    "grounding": "Parts of this answer may go beyond the course material.",
    "pii_leak": "A privacy check flagged this request; it has been logged for review.",
    "profile_leak": "A privacy check flagged this request; it has been logged for review.",
}


@steps.register("verify")
class VerifyStep(BaseStep):
    """Step 8: run the configured checkers (verify.checkers) and act on the results.

    medical_safety fail -> regenerate once with a fixed safety instruction; still failing -> a safe fallback
    message (the retrieved sources are still returned). medical_safety warn -> append a referral sentence.
    Other findings -> a user-visible warning; leak findings are also logged as errors (kinds only).
    """

    name = "verify"
    on_error = "warn"

    def __init__(self, services) -> None:
        super().__init__(services)
        import_submodules("app.verify.checkers")
        self.checkers = [checkers.get(n)(services) for n in services.settings.verify.checkers]
        self.generate = GenerateStep(services)

    def _run_all(self, ctx: RequestContext) -> list[CheckResult]:
        results = []
        for c in self.checkers:
            try:
                results.append(c.check(ctx))
            except Exception as e:  # noqa: BLE001  a broken checker must not break the answer
                log.warning("checker %s failed (%s), request=%s", c.name, type(e).__name__, ctx.request_id)
                results.append(CheckResult(name=c.name, status="warn", detail="checker error"))
        return results

    @staticmethod
    def _status(results: list[CheckResult], name: str) -> str | None:
        return next((r.status for r in results if r.name == name), None)

    async def run(self, ctx: RequestContext) -> RequestContext:
        ctx.checks = self._run_all(ctx)
        if self._status(ctx.checks, "medical_safety") == "fail":
            log.warning("medical safety check failed, regenerating once, request=%s", ctx.request_id)
            result = await self.generate.produce(ctx, safety_retry=True)
            ctx.llm, ctx.answer = result, restore(result.text, ctx.pii_mapping)
            ctx.checks = self._run_all(ctx)
            if self._status(ctx.checks, "medical_safety") == "fail":
                log.warning("medical safety check failed again, using the safe fallback, request=%s",
                            ctx.request_id)
                ctx.answer = SAFE_FALLBACK + (SAFE_FALLBACK_SOURCES if ctx.passages else "")
                ctx.warnings.append(REPLACED_WARNING)
                ctx.checks = [*ctx.checks, CheckResult(name="medical_safety", status="pass",
                                                       detail="safe fallback message")]
        if self._status(ctx.checks, "medical_safety") == "warn":
            ctx.answer = (ctx.answer or "").rstrip() + "\n\n" + REFERRAL
        for r in ctx.checks:
            if r.status == "fail" and r.name in ("pii_leak", "profile_leak"):
                log.error("%s check failed (%s), request=%s", r.name, r.detail, ctx.request_id)
            if r.status in ("fail", "warn") and r.name in WARNINGS and WARNINGS[r.name] not in ctx.warnings:
                ctx.warnings.append(WARNINGS[r.name])
        return ctx
