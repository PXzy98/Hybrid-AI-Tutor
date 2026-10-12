import uuid
from pathlib import PurePosixPath

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel

from app.api.deps import RunnerDep, ServicesDep
from app.core.schemas import AskRequest, AskResponse, RequestContext, Source
from app.pipeline.runner import PipelineError

router = APIRouter()

# Safe, generic messages: an error response never contains the question.
FAILURE_MESSAGES = {
    "privacy_filter": "The privacy filter is unavailable, so the question was not processed.",
}
DEFAULT_FAILURE = "The tutor could not answer right now. Please try again."


class ErrorBody(BaseModel):
    detail: str
    step: str
    request_id: str


def _sources(ctx: RequestContext) -> list[Source]:
    seen: dict[str, Source] = {}
    for c in ctx.passages:
        if c.source not in seen:
            seen[c.source] = Source(title=PurePosixPath(c.source).stem.replace("_", " "), source=c.source,
                                    kc_ids=c.kc_ids)
    return list(seen.values())


@router.post("/ask", response_model=AskResponse, responses={503: {"model": ErrorBody}})
async def ask(req: AskRequest, background: BackgroundTasks, services: ServicesDep, runner: RunnerDep):
    settings = services.settings
    if req.topic not in settings.topics(req.course_id):
        raise HTTPException(422, f"unknown topic for course '{req.course_id}'")
    session_id = req.session_id or str(uuid.uuid4())
    ctx = RequestContext(
        request_id=str(uuid.uuid4()),
        request=req.model_copy(update={"session_id": session_id}),
        history=services.sessions.history(session_id, last=settings.sessions.history_turns),
    )
    try:
        ctx = await runner.run(ctx)
    except PipelineError as e:
        return JSONResponse(status_code=503, content=ErrorBody(
            detail=FAILURE_MESSAGES.get(e.step, DEFAULT_FAILURE), step=e.step, request_id=ctx.request_id,
        ).model_dump())
    background.add_task(runner.run_post, ctx)

    learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
    return AskResponse(
        session_id=session_id,
        answer=ctx.answer or "",
        sources=_sources(ctx),
        model_used=ctx.llm.model if ctx.llm else "none",
        route_target=ctx.target or "local",
        route_score=ctx.route.score if ctx.route else None,
        check_item=ctx.check_item,
        kc_level=learner.focus_level if learner else None,
        next_kc=learner.next_kc if learner else None,
        checks=ctx.checks,
        warnings=ctx.warnings,
        timings_ms=ctx.timings_ms,
    )
