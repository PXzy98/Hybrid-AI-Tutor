"""Asking the tutor in a course (api-v2.md 3.5; guide 4.5; tasks Z9 and Z10).

`POST /courses/{course_id}/ask` and `/ask/stream` run the same pipeline as API v1 inside the course's scope:
the course's content, learner data, material, settings and privacy profile. Before the pipeline: the role
check (students of the course) and the usage limits. Conversations belong to one student in one course;
the history sent to the models never comes from another course.
"""
import asyncio
import contextlib
import json
import uuid
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, BackgroundTasks, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlmodel import Session, col, func, select

from app.api.v1.ask import _error, _response
from app.api.v2.errors import ApiError, ErrorCode
from app.catalog import CatalogError
from app.core.schemas import AskRequest, AskResponse, RequestContext, Turn
from app.learner.content import ContentError
from app.pipeline.runner import PipelineError
from app.pipeline.steps.generate import CLOUD_LIMIT_NOTE
from app.platform import course_scope, usage
from app.platform.access import CourseAccess, require_course_role
from app.platform.course_scope import GENERAL_TOPIC, CourseScope
from app.privacy.profiles import privacy_profile
from app.storage.models import SessionTurn

router = APIRouter(tags=["ask"])
CourseStudent = Annotated[CourseAccess, Depends(require_course_role("student"))]


class AskIn(BaseModel):
    question: str = Field(min_length=1, max_length=4000)
    module_id: int | None = None  # None: a question about the course as a whole
    conversation_id: str = Field("", max_length=64)  # empty: start a new conversation
    routing_method: Literal["lr", "svm"] | None = None
    language: str = Field("en", max_length=8)


class AskOut(AskResponse):
    conversation_id: str


class AskErrorOut(BaseModel):
    detail: str
    step: str
    request_id: str


class ConversationOut(BaseModel):
    conversation_id: str
    started_at: datetime
    last_at: datetime
    turns: int


class ConversationDetailOut(BaseModel):
    conversation_id: str
    turns: list[Turn]


def _services(request: Request):
    return request.app.state.services


def _scope(services, course_id: int) -> CourseScope:
    try:
        return services.course_scopes.get(course_id)
    except (CatalogError, ContentError) as exc:
        raise ApiError(409, ErrorCode.conflict, "The course content cannot be used yet.") from exc


def _owned(services, access: CourseAccess, conversation_id: str) -> bool:
    """True when the conversation is the caller's in this course; a new ID is fine (False). An ID that
    belongs to someone else or to another course is refused as not found."""
    with Session(services.engine) as db:
        rows = db.exec(select(SessionTurn.student_id, SessionTurn.course_id)
                       .where(SessionTurn.session_id == conversation_id).distinct()).all()
    if not rows:
        return False
    if any((student, course) != (access.student_id, access.course.id) for student, course in rows):
        raise ApiError(404, ErrorCode.not_found, "conversation not found")
    return True


def _prepare(body: AskIn, access: CourseAccess, services) -> tuple[RequestContext, CourseScope]:
    course_id = access.course.id
    scope = _scope(services, course_id)
    topic = GENERAL_TOPIC
    if body.module_id is not None:
        topic = next((code for code, mid in scope.modules.items() if mid == body.module_id), None)
        if topic is None:
            raise ApiError(404, ErrorCode.not_found, "module not found")
    eff = services.settings_service.effective(course_id)  # the request's settings snapshot
    method = body.routing_method or eff.default_routing_method
    if method not in services.settings.routing.enabled_methods:
        raise ApiError(422, ErrorCode.invalid, "This routing method is disabled.")
    conversation_id = body.conversation_id or str(uuid.uuid4())
    known = bool(body.conversation_id) and _owned(services, access, conversation_id)
    warnings = []
    try:  # a first look; each cloud call reserves its own use (_CloudMeter)
        usage.check_usage(access.student_id, course_id, "cloud_call")
    except usage.UsageLimitExceeded:  # still answered, by the local model only
        eff = eff.model_copy(update={"local_only": True})
        warnings.append(CLOUD_LIMIT_NOTE)
    usage.reserve_usage(access.student_id, course_id, "question")  # last: 429 with retry_after_seconds
    request = AskRequest(session_id=conversation_id, course_id=str(course_id), student_id=access.student_id,
                         topic=topic, question=body.question, language=body.language, routing_method=method)
    turns = services.settings.sessions.history_turns
    ctx = RequestContext(
        request_id=str(uuid.uuid4()), request=request, course=access.course, module_id=body.module_id,
        settings=eff, profile=privacy_profile(eff.course_type), warnings=warnings,
        show_routing_progress=eff.show_routing_progress,
        history=scope.sessions.history(conversation_id, last=turns) if known else [])
    ctx.set_cloud_meter(_CloudMeter(access.student_id, course_id))
    return ctx, scope


class _CloudMeter:
    """Reserves one cloud call per actual invocation, so safety retries count too."""

    def __init__(self, student_id: str, course_id: int) -> None:
        self.student_id, self.course_id = student_id, course_id

    def reserve(self) -> bool:
        try:
            usage.reserve_usage(self.student_id, self.course_id, "cloud_call")
        except usage.UsageLimitExceeded:
            return False
        return True

    def used(self, tokens: int) -> None:
        usage.add_tokens(self.student_id, self.course_id, "cloud_call", tokens)


def _record_usage(ctx: RequestContext) -> None:
    """The question was reserved in _prepare; add its tokens."""
    tokens = ((ctx.llm.prompt_tokens or 0) + (ctx.llm.completion_tokens or 0)) if ctx.llm else 0
    usage.add_tokens(ctx.request.student_id, ctx.course.id, "question", tokens)


def _release(ctx: RequestContext) -> None:
    """No answer: the question does not count (cloud calls already made still do)."""
    usage.release_usage(ctx.request.student_id, ctx.course.id, "question")


def _out(ctx: RequestContext) -> AskOut:
    return AskOut(**_response(ctx).model_dump(), conversation_id=ctx.request.session_id)


async def _post(runner, ctx: RequestContext, scope: CourseScope) -> None:
    with course_scope.use(scope):
        await runner.run_post(ctx)


@router.post("/courses/{course_id}/ask", response_model=AskOut, responses={503: {"model": AskErrorOut}})
async def ask(body: AskIn, access: CourseStudent, request: Request, background: BackgroundTasks):
    services = _services(request)
    ctx, scope = _prepare(body, access, services)
    runner = services.components.runner
    try:
        with course_scope.use(scope):
            ctx = await runner.run(ctx)
    except PipelineError as e:
        _release(ctx)
        return JSONResponse(status_code=503, content=_error(ctx, e.step).model_dump())
    except BaseException:
        _release(ctx)
        raise
    finally:
        ctx.clear_pii_mapping()
    _record_usage(ctx)
    background.add_task(_post, runner, ctx, scope)
    return _out(ctx)


@router.post("/courses/{course_id}/ask/stream", responses={200: {"content": {"text/event-stream": {}}}})
async def ask_stream(body: AskIn, access: CourseStudent, request: Request):
    """Server-sent events: `meta`, `progress` (fixed status text and scores, never question or passage
    text), then `result` or `error`, then `done`."""
    services = _services(request)
    ctx, scope = _prepare(body, access, services)  # access, validation and limits fail before HTTP 200
    runner = services.components.runner
    queue: asyncio.Queue = asyncio.Queue()

    async def progress(event):
        await queue.put(("progress", event.model_dump()))

    ctx.set_progress_sink(progress)

    async def produce():
        answered = False
        try:
            with course_scope.use(scope):
                await runner.run(ctx)
                ctx.clear_pii_mapping()
                _record_usage(ctx)
                answered = True
                await queue.put(("result", _out(ctx).model_dump(mode="json")))
                await runner.run_post(ctx)
        except PipelineError as e:
            await queue.put(("error", _error(ctx, e.step).model_dump()))
        except asyncio.CancelledError:
            raise
        except Exception:  # noqa: BLE001 - the stream ends with an error event, never with a broken body
            await queue.put(("error", _error(ctx, "pipeline").model_dump()))
        finally:
            if not answered:
                _release(ctx)
            ctx.clear_pii_mapping()
            ctx.set_progress_sink(None)
            await queue.put(None)

    async def events():
        task = asyncio.create_task(produce())
        try:
            meta = {"request_id": ctx.request_id, "conversation_id": ctx.request.session_id,
                    "show_progress": ctx.show_routing_progress, "method": ctx.request.routing_method}
            yield "event: meta\ndata: " + json.dumps(meta) + "\n\n"
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

    return StreamingResponse(events(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache, no-transform", "X-Accel-Buffering": "no"})


@router.get("/courses/{course_id}/conversations", response_model=list[ConversationOut])
def conversations(access: CourseStudent, request: Request):
    """The caller's own conversations in this course, newest first."""
    stmt = (select(SessionTurn.session_id, func.min(SessionTurn.created_at),
                   func.max(SessionTurn.created_at), func.count())
            .where(SessionTurn.student_id == access.student_id, SessionTurn.course_id == access.course.id)
            .group_by(col(SessionTurn.session_id)).order_by(func.max(SessionTurn.created_at).desc()))
    with Session(_services(request).engine) as db:
        rows = db.exec(stmt.limit(200)).all()
    return [ConversationOut(conversation_id=sid, started_at=first, last_at=last, turns=n)
            for sid, first, last, n in rows]


@router.get("/courses/{course_id}/conversations/{conversation_id}", response_model=ConversationDetailOut)
def conversation(conversation_id: str, access: CourseStudent, request: Request, last: int = 50):
    """Sanitized turns of one of the caller's conversations in this course (oldest first)."""
    services = _services(request)
    if not _owned(services, access, conversation_id):
        raise ApiError(404, ErrorCode.not_found, "conversation not found")
    scope = _scope(services, access.course.id)
    return ConversationDetailOut(conversation_id=conversation_id,
                                 turns=scope.sessions.history(conversation_id, last=max(1, min(last, 200))))
