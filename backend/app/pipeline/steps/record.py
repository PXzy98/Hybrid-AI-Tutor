from sqlmodel import Session

from app.core.registry import steps
from app.core.schemas import RequestContext, StoredTurn, Turn
from app.pipeline.base import BaseStep
from app.pipeline.steps.generate import ANSWER_CUT_OFF_NOTE
from app.privacy.redact import redact_known
from app.rag.sources import answer_sources
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
                course_id=self.services.content.course_id,
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
                kc_ids=self._asked_kcs(ctx),
            ))
            s.commit()
        self.services.sessions.append(req.session_id, req.student_id, Turn(role="student", text=question))
        self.services.sessions.append(req.session_id, req.student_id, StoredTurn(
            role="tutor", text=answer, sources=answer_sources(ctx.passages) if ctx.answer else [],
            target=ctx.llm.backend if ctx.llm else None, cut_off=ANSWER_CUT_OFF_NOTE in ctx.warnings))
        ctx.clear_pii_mapping()  # nothing after this step needs the original values
        return ctx

    def _asked_kcs(self, ctx: RequestContext) -> list[str]:
        """The KC codes of the question (understand step) for the class insights; only with consent."""
        kcs = ctx.understanding.kc_ids if ctx.understanding else []
        if not kcs:
            return []
        try:
            consented = self.services.learner.has_consent(ctx.request.student_id)
        except Exception:  # noqa: BLE001 - unknown consent: record nothing
            return []
        return list(dict.fromkeys(kcs)) if consented else []
