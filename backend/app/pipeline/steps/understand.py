from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("understand")
class UnderstandStep(BaseStep):
    """PLACEHOLDER until Step 11. No KC tagging yet."""

    name = "understand"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        return ctx
