from app.core.registry import steps
from app.core.schemas import PIIResult, RequestContext
from app.pipeline.base import BaseStep
from app.privacy.analyzer import PIIAnalyzer, resolve_overlaps
from app.privacy.anonymizer import anonymize
from app.privacy.session_health import follow_up_findings, had_personal_health, refers_back


@steps.register("privacy_filter")
class PrivacyFilterStep(BaseStep):
    """Step 1: find PII with Presidio + custom recognizers and replace it with numbered placeholders.

    Built at startup, so a missing spaCy model stops the app instead of letting requests through unfiltered.
    The placeholder -> value mapping lives only in the private attribute of the RequestContext.
    The student's own display name and username (from `account`, in memory only) are always redacted,
    even when the NER model misses them (found by the E4 privacy audit).
    After a personal health detail earlier in the session, condition and medicine names count as personal
    and a question that refers back to it stays local (`app/privacy/session_health.py`).
    """

    name = "privacy_filter"
    on_error = "stop"  # never skipped (privacy invariant 5)

    def __init__(self, services) -> None:
        super().__init__(services)
        self.cfg = services.settings.privacy
        self.analyzer = PIIAnalyzer(self.cfg)

    async def run(self, ctx: RequestContext) -> RequestContext:
        question = ctx.request.question
        names, usernames = self.services.accounts.identity_terms(ctx.request.student_id)
        findings = self.analyzer.analyze(question, names, usernames)
        health_session = had_personal_health(ctx.history)
        if health_session:
            findings = resolve_overlaps(findings + follow_up_findings(question),
                                        prefer=tuple(self.cfg.local_only_types))
        sanitized, entities, mapping = anonymize(question, findings)
        local_only = set(self.cfg.local_only_types)
        cloud_safe = not any(e.type in local_only for e in entities)
        if health_session and cloud_safe and refers_back(question):
            cloud_safe = False  # "is it dangerous?" right after a personal health detail
        ctx.pii = PIIResult(
            entities=entities,
            is_sensitive=bool(entities) or not cloud_safe,
            cloud_safe=cloud_safe,
            sanitized_text=sanitized,
        )
        ctx.set_pii_mapping(mapping)
        return ctx
