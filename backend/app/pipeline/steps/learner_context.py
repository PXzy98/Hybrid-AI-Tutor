from app.core.registry import steps
from app.core.schemas import RequestContext
from app.pipeline.base import BaseStep


@steps.register("learner_context")
class LearnerContextStep(BaseStep):
    """PLACEHOLDER until Step 6. Leaves ctx.learner unset (unpersonalized)."""

    name = "learner_context"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        return ctx
