from app.core.registry import steps
from app.core.schemas import RequestContext
from app.learner.checks import choose_item
from app.pipeline.base import BaseStep


@steps.register("attach_check")
class AttachCheckStep(BaseStep):
    """Step 9: one check MCQ for the main KC (design §6).

    KC: the first KC of the question (understand step, Step 11), else the recommended next KC, else the
    topic's KC with the lowest mastery (the first KC when unpersonalized).
    Item: see learner.checks.choose_item.
    Only items the content store may serve are used (content.serve_unreviewed).
    """

    name = "attach_check"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        content = self.services.content
        learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
        kc_id = None
        if ctx.understanding and ctx.understanding.kc_ids:
            kc_id = next((k for k in ctx.understanding.kc_ids if content.kc(k)), None)
        if kc_id is None and learner and learner.next_kc \
                and content.topic_of(learner.next_kc.kc_id) == ctx.request.topic:
            kc_id = learner.next_kc.kc_id
        if kc_id is None:
            kcs = content.kcs(ctx.request.topic)
            if learner and learner.kc_states:
                kcs = sorted(kcs, key=lambda k: learner.kc_states[k.id].p_mastery if k.id in learner.kc_states
                             else 1.0)
            kc_id = kcs[0].id if kcs else None
        if kc_id is None:
            return ctx
        state = learner.kc_states.get(kc_id) if learner else None
        item = choose_item(content, self.services.learner.repo, ctx.request.student_id if learner else None,
                           kc_id, state.level if state else None)
        ctx.check_item = item.public() if item else None
        return ctx
