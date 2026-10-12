from sqlmodel import Session

from app.core.registry import steps
from app.core.schemas import RequestContext, Turn
from app.pipeline.base import BaseStep
from app.privacy.redact import redact_known
from app.storage.models import RequestLog

WITHHELD = "[withheld: not sanitized]"


@steps.register("record")
class RecordStep(BaseStep):
    """Writes the request log and the session turns. SANITIZED text only (privacy invariant 1)."""

    name = "record"
    on_error = "skip"

    async def run(self, ctx: RequestContext) -> RequestContext:
        question = ctx.pii.sanitized_text if ctx.pii else WITHHELD
        # the answer may repeat PII that the local model saw: replace known values with placeholders
        answer = redact_known(ctx.answer or "", ctx.pii.entities) if ctx.pii else WITHHELD
        req = ctx.request
        with Session(self.services.engine) as s:
            s.add(RequestLog(
                request_id=ctx.request_id,
                session_id=req.session_id,
                student_id=req.student_id,
                topic=req.topic,
                sanitized_question=question,
                target=ctx.target,
                route_score=ctx.route.score if ctx.route else None,
                model=ctx.llm.model if ctx.llm else None,
                prompt_tokens=ctx.llm.prompt_tokens if ctx.llm else None,
                completion_tokens=ctx.llm.completion_tokens if ctx.llm else None,
                timings=dict(ctx.timings_ms),
                checks=[c.model_dump() for c in ctx.checks],
                warnings=list(ctx.warnings),
            ))
            s.commit()
        self.services.sessions.append(req.session_id, req.student_id, Turn(role="student", text=question))
        self.services.sessions.append(req.session_id, req.student_id, Turn(role="tutor", text=answer))
        return ctx
