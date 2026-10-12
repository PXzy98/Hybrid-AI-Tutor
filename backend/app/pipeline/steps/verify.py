from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("verify")
class VerifyStep(BaseStep):
    """PLACEHOLDER until Step 8. Runs no checkers yet."""

    name = "verify"
    on_error = "warn"

    async def run(self, ctx: RequestContext) -> RequestContext:
        return ctx
