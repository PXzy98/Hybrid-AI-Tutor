from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("restore")
class RestoreStep(BaseStep):
    """PLACEHOLDER until Step 4. Only discards the PII mapping."""

    name = "restore"
    on_error = "stop"

    async def run(self, ctx: RequestContext) -> RequestContext:
        ctx.clear_pii_mapping()
        return ctx
