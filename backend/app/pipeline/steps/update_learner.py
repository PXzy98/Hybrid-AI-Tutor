from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("update_learner")
class UpdateLearnerStep(BaseStep):
    """PLACEHOLDER until Step 11 (post-response). Applies no evidence yet."""

    name = "update_learner"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        return ctx
