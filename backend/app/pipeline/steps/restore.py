from app.core.registry import steps
from app.core.schemas import RequestContext
from app.learner.misconceptions import append_corrections
from app.pipeline.base import BaseStep
from app.privacy.anonymizer import restore


@steps.register("restore")
class RestoreStep(BaseStep):
    """Step 7: put the original values back into placeholders of the answer.

    Mostly matters for cloud answers; a local answer normally has no placeholders, and is left unchanged.
    The mapping is kept until `record` (the last step), because `verify` may regenerate a cloud answer that
    needs restoring again; the API also clears it after the pipeline.

    Cloud route: the reviewed correction of a relevant open misconception is appended here, locally, when
    the answer does not already address it (design §6). The cloud request itself never carries it.
    """

    name = "restore"
    on_error = "stop"

    async def run(self, ctx: RequestContext) -> RequestContext:
        if ctx.answer:
            ctx.answer = restore(ctx.answer, ctx.pii_mapping)
            append_corrections(ctx)
        return ctx
