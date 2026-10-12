from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("attach_check")
class AttachCheckStep(BaseStep):
    """PLACEHOLDER until Step 7. Attaches no check question yet."""

    name = "attach_check"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        return ctx
