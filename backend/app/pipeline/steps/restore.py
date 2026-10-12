from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep
from app.privacy.anonymizer import restore


@steps.register("restore")
class RestoreStep(BaseStep):
    """Step 7: put the original values back into placeholders of the answer, then discard the mapping.

    Mostly matters for cloud answers; a local answer normally has no placeholders, and is left unchanged.
    The misconception note for cloud answers is added here in Step 12.
    """

    name = "restore"
    on_error = "stop"

    async def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.answer:
            ctx.answer = restore(ctx.answer, ctx.pii_mapping)
        ctx.clear_pii_mapping()
        return ctx
