from app.core.registry import steps
from app.core.schemas import PIIResult, RequestContext
from app.pipeline.base import BaseStep
from app.privacy.analyzer import PIIAnalyzer
from app.privacy.anonymizer import anonymize


@steps.register("privacy_filter")
class PrivacyFilterStep(BaseStep):
    """Step 1: find PII with Presidio + custom recognizers and replace it with numbered placeholders.

    Built at startup, so a missing spaCy model stops the app instead of letting requests through unfiltered.
    The placeholder -> value mapping lives only in the private attribute of the RequestContext.
    """

    name = "privacy_filter"
    on_error = "stop"  # never skipped (privacy invariant 5)

    def __init__(self, services) -> None:
        super().__init__(services)
        self.cfg = services.settings.privacy
        self.analyzer = PIIAnalyzer(self.cfg)

    async def run(self, ctx: RequestContext) -> RequestContext:
        question = ctx.request.question
        findings = self.analyzer.analyze(question)
        sanitized, entities, mapping = anonymize(question, findings)
        local_only = set(self.cfg.local_only_types)
        ctx.pii = PIIResult(
            entities=entities,
            is_sensitive=bool(entities),
            cloud_safe=not any(e.type in local_only for e in entities),
            sanitized_text=sanitized,
        )
        ctx.set_pii_mapping(mapping)
        return ctx
