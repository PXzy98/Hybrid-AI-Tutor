from app.core.registry import steps
from app.core.schemas import LLMResult, RequestContext
from app.pipeline.base import BaseStep


@steps.register("generate")
class GenerateStep(BaseStep):
    """PLACEHOLDER until Step 3 (LLM clients). Echoes the sanitized question, never the raw one."""

    name = "generate"
    on_error = "stop"

    async def run(self, ctx: RequestContext) -> RequestContext:
        sanitized = ctx.pii.sanitized_text if ctx.pii else ""
        text = f"[placeholder answer: the generate step is not implemented yet] You asked: {sanitized}"
        ctx.llm = LLMResult(text=text, model="placeholder", backend=ctx.target or "local", latency_ms=0.0)
        ctx.answer = text
        return ctx
