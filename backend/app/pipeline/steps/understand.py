from app.core.registry import steps
from app.core.schemas import RequestContext
from app.learner import understand
from app.pipeline.base import BaseStep


@steps.register("understand")
class UnderstandStep(BaseStep):
    """Tag the question with KC IDs, question type, confusion and misconception IDs (local model, JSON).

    Runs right after the privacy filter, before learner_context, so the level can come from the question's
    own KCs. The local model may see the original question (privacy boundary); only IDs are kept. Any failure
    (timeout, bad JSON, unknown ID) skips the step: retrieval then uses the topic, and no weak evidence is
    recorded.
    """

    name = "understand"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        content, topic = self.services.content, ctx.request.topic
        if not content.kcs(topic):
            return ctx
        result = await self.services.understand_llm.complete(
            understand.messages(content, topic, ctx.request.question),
            json_schema=understand.schema(content, topic), max_tokens=200)
        ctx.understanding = understand.parse(result.text, content, topic, ctx.request.question)
        return ctx
