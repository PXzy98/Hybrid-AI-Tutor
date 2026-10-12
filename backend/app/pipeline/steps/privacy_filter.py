from app.core.registry import steps
from app.core.schemas import PIIResult, RequestContext
from app.pipeline.base import BaseStep

WITHHELD = "[question withheld: privacy filter not installed]"


@steps.register("privacy_filter")
class PrivacyFilterStep(BaseStep):
    """PLACEHOLDER until Step 4 (Presidio). Fails closed.

    The question is treated as fully sensitive: the sanitized text withholds it completely and
    cloud_safe is False, so nothing is routed to the cloud and nothing raw is stored.
    """

    name = "privacy_filter"
    on_error = "stop"

    async def run(self, ctx: RequestContext) -> RequestContext:
        ctx.pii = PIIResult(entities=[], is_sensitive=True, cloud_safe=False, sanitized_text=WITHHELD)
        return ctx
