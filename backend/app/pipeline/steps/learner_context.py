from app.core.registry import steps
from app.core.schemas import LearnerContext, RequestContext
from app.pipeline.base import BaseStep


@steps.register("learner_context")
class LearnerContextStep(BaseStep):
    """Step 2: load the learner's knowledge state and preferences into ctx.learner.

    On error the step is skipped and the answer is simply unpersonalized (design §2: degrade, don't fail).
    KC IDs come from the understand step once it exists (Step 11); until then the topic level is used.
    """

    name = "learner_context"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        if not self.services.settings.learner.personalize:  # E3 "off" condition
            ctx.learner = LearnerContext(personalized=False)
            return ctx
        kc_ids = ctx.understanding.kc_ids if ctx.understanding else None
        ctx.learner = self.services.learner.context(ctx.request.student_id, ctx.request.topic, kc_ids)
        return ctx
