import asyncio
import contextlib
import json
import uuid
from pathlib import PurePosixPath
from typing import Literal

from fastapi import APIRouter, BackgroundTasks, HTTPException
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field

from app.api.deps import RunnerDep, ServicesDep
from app.auth.deps import Student
from app.core.schemas import AskRequest, AskResponse, RequestContext, Source
from app.pipeline.runner import PipelineError
from app.routing.methods import METHOD_LABELS

router = APIRouter()
FAILURE_MESSAGES = {
    "privacy_filter": "The privacy filter is unavailable, so the question was not processed.",
}
DEFAULT_FAILURE = "The tutor could not answer right now. Please try again."


class AskBody(BaseModel):
    """Identity comes from the login session. Routing method is per question, never global."""

    session_id: str = Field("", max_length=64)
    course_id: str = "default"
    topic: str = Field(min_length=1)
    question: str = Field(min_length=1, max_length=4000)
    language: str = "en"
    routing_method: Literal["lr", "svm"] | None = None


class ErrorBody(BaseModel):
    detail: str
    step: str
    request_id: str


class RoutingMethodOption(BaseModel):
    id: str
    label: str


class RoutingOptions(BaseModel):
    show_progress: bool
    default_method: str
    methods: list[RoutingMethodOption]


@router.get("/routing/options", response_model=RoutingOptions)
def routing_options(_: Student, services: ServicesDep):
    cfg = services.settings.routing
    return RoutingOptions(
        show_progress=cfg.show_progress,
        default_method=cfg.default_method,
        methods=[RoutingMethodOption(id=m, label=METHOD_LABELS[m]) for m in cfg.enabled_methods],
    )


def _prepare(body: AskBody, user, services) -> RequestContext:
    settings = services.settings
    if body.topic not in settings.topics(body.course_id):
        raise HTTPException(422, f"unknown topic for course '{body.course_id}'")
    method = body.routing_method or settings.routing.default_method
    if method not in settings.routing.enabled_methods:
        raise HTTPException(422, "This routing method is disabled. Refresh the method options.")
    session_id = body.session_id or str(uuid.uuid4())
    owner = services.sessions.owner(session_id)
    if owner is not None and owner != user.student_id:
        raise HTTPException(404, "session not found")
    req = AskRequest(
        **body.model_dump(exclude={"session_id", "routing_method"}),
        session_id=session_id,
        student_id=user.student_id,
        routing_method=method,
    )
    return RequestContext(
        request_id=str(uuid.uuid4()),
        request=req,
        show_routing_progress=settings.routing.show_progress,
        history=services.sessions.history(session_id, last=settings.sessions.history_turns),
    )


def _sources(ctx: RequestContext) -> list[Source]:
    seen: dict[str, Source] = {}
    for c in ctx.passages:
        if c.source not in seen:
            seen[c.source] = Source(
                title=PurePosixPath(c.source).stem.replace("_", " "), source=c.source, kc_ids=c.kc_ids
            )
    return list(seen.values())


def _response(ctx: RequestContext) -> AskResponse:
    learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
    return AskResponse(
        session_id=ctx.request.session_id,
        answer=ctx.answer or "",
        sources=_sources(ctx),
        model_used=ctx.llm.model if ctx.llm else "none",
        route_target=ctx.llm.backend if ctx.llm else (ctx.target or "local"),
        route_score=ctx.route.score if ctx.route else None,
        routing_method=ctx.request.routing_method,
        routing_details=ctx.route if ctx.show_routing_progress else None,
        routing_progress=ctx.routing_progress if ctx.show_routing_progress else [],
        check_item=ctx.check_item,
        kc_level=learner.focus_level if learner else None,
        next_kc=learner.next_kc if learner else None,
        checks=ctx.checks,
        warnings=ctx.warnings,
        timings_ms=ctx.timings_ms,
    )


def _error(ctx, step):
    detail = FAILURE_MESSAGES.get(step, DEFAULT_FAILURE)
    if step == "generate" and ctx.semantic_analysis is not None:
        detail = "The selected model is unavailable. Check the local server or Cloud configuration and retry."
    return ErrorBody(detail=detail, step=step, request_id=ctx.request_id)


@router.post("/ask", response_model=AskResponse, responses={503: {"model": ErrorBody}})
async def ask(
    body: AskBody, user: Student, background: BackgroundTasks, services: ServicesDep, runner: RunnerDep
):
    ctx = _prepare(body, user, services)
    try:
        ctx = await runner.run(ctx)
    except PipelineError as e:
        return JSONResponse(status_code=503, content=_error(ctx, e.step).model_dump())
    finally:
        ctx.clear_pii_mapping()
    background.add_task(runner.run_post, ctx)
    return _response(ctx)


@router.post("/ask/stream", responses={200: {"content": {"text/event-stream": {}}}})
async def ask_stream(body: AskBody, user: Student, services: ServicesDep, runner: RunnerDep):
    """POST + fetch streaming so the cookie/session and per-question method are preserved.

    Progress events contain fixed status text/scores only, never question or passage text.
    Instructor display-off suppresses progress and routing diagnostics server-side.
    """
    ctx = _prepare(body, user, services)  # auth/validation/ownership fail before HTTP 200
    queue: asyncio.Queue = asyncio.Queue()

    async def progress(event):
        await queue.put(("progress", event.model_dump()))

    ctx.set_progress_sink(progress)

    async def produce():
        try:
            await runner.run(ctx)
            ctx.clear_pii_mapping()
            await queue.put(("result", _response(ctx).model_dump(mode="json")))
            await runner.run_post(ctx)
        except PipelineError as e:
            await queue.put(("error", _error(ctx, e.step).model_dump()))
        except asyncio.CancelledError:
            raise
        except Exception:
            await queue.put(("error", _error(ctx, "pipeline").model_dump()))
        finally:
            ctx.clear_pii_mapping()
            ctx.set_progress_sink(None)
            await queue.put(None)

    async def events():
        task = asyncio.create_task(produce())
        try:
            yield (
                "event: meta\ndata: "
                + json.dumps(
                    {
                        "request_id": ctx.request_id,
                        "session_id": ctx.request.session_id,
                        "show_progress": ctx.show_routing_progress,
                        "method": ctx.request.routing_method,
                    }
                )
                + "\n\n"
            )
            while True:
                try:
                    item = await asyncio.wait_for(queue.get(), timeout=10)
                except TimeoutError:
                    yield ": keep-alive\n\n"
                    continue
                if item is None:
                    yield "event: done\ndata: {}\n\n"
                    break
                kind, payload = item
                yield f"event: {kind}\ndata: {json.dumps(payload, ensure_ascii=False)}\n\n"
        finally:
            task.cancel()
            with contextlib.suppress(asyncio.CancelledError):
                await task
            ctx.clear_pii_mapping()

    return StreamingResponse(
        events(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"},
    )
