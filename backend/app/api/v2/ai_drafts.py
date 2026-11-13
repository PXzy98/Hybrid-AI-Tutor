"""Instructor AI tiers 1 to 3 endpoints (api-v2.md 3.6 and 3.7; guide 4.9; tasks S6, S7, S10).

Tiers 1 and 2: `POST .../ai/drafts` starts a background job (`GET .../jobs/{id}`) in which the **local** model
drafts project ideas, a sample proposal, an FAQ, KCs, check items or misconceptions from the course material.
The draft is visible to the course's instructors only. The instructor edits it (`PATCH`, while `draft`) and
accepts it: tier 2 drafts become KCs, check items and misconceptions in the normal content tables (active,
through the content editor and its checks); tier 1 drafts become a course-level Markdown material (scanned
and indexed like an upload). `DELETE` discards a draft.

Tier 3: `GET .../insights` returns KC and misconception counts only, suppressed for small groups.
"""
import json
import re
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.api.v2.content import _editor
from app.api.v2.errors import ApiError, ErrorCode
from app.instructor_ai import draft_jobs
from app.instructor_ai.insights_source import course_insights
from app.platform import jobs
from app.platform.access import CourseAccess, require_course_role
from app.privacy.profiles import privacy_profile, scan_document
from app.rag import index_jobs
from app.storage.models import AiDraft, AuditLog, CatalogMisconception, Kc, Module, utcnow

router = APIRouter(tags=["instructor-ai"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
DraftKind = Literal["project_ideas", "sample_proposal", "faq", "kcs", "check_items", "misconceptions"]
DraftStatus = Literal["generating", "draft", "accepted", "discarded", "failed"]


class AiDraftIn(BaseModel):
    kind: DraftKind
    module_id: int | None = None  # the material of this module (and the course-level files); None: all
    focus: str = Field("", max_length=300)  # what to look for in the material (instructor's words)


class AiDraftPatch(BaseModel):
    # tier 1: {"title", "body"}; tier 2: {"items": [...]} (the shapes the draft was returned in)
    content: dict


class AiDraftAcceptIn(BaseModel):
    module_id: int | None = None  # kcs: the module of the new KCs, when the draft has none


class AiDraftOut(BaseModel):
    id: int
    kind: DraftKind
    module_id: int | None
    status: DraftStatus
    content: dict
    cited_sources: list[str]
    error: str | None
    created_by: int | None
    created_at: datetime
    updated_at: datetime
    job_id: int | None = None  # the generation job started by this request


class AiDraftSummary(BaseModel):
    id: int
    kind: DraftKind
    module_id: int | None
    status: DraftStatus
    created_at: datetime
    updated_at: datetime


class AiDraftAcceptOut(BaseModel):
    draft: AiDraftOut
    created: dict[str, list[int]]  # ids by table: kcs, check_items, misconceptions, materials
    rebuild_job_id: int | None = None  # tier 1: the index rebuild that makes the material searchable


class LabelCountOut(BaseModel):
    label: str  # KC code or misconception code
    name: str | None  # the course's name for it
    count: int


class InsightsOut(BaseModel):
    min_group: int
    suppressed: bool  # fewer than `min_group` students contributed: nothing is shown
    kc_question_counts: list[LabelCountOut]
    misconception_counts: list[LabelCountOut]


def _engine(request: Request):
    return request.app.state.services.engine


def _out(row: AiDraft, job_id: int | None = None) -> AiDraftOut:
    return AiDraftOut(id=row.id, kind=row.kind, module_id=row.module_id, status=row.status,
                      content=row.content,
                    cited_sources=row.cited_sources, error=row.error, created_by=row.created_by,
                    created_at=row.created_at, updated_at=row.updated_at, job_id=job_id)


def _get(db: Session, course_id: int, draft_id: int) -> AiDraft:
    row = db.get(AiDraft, draft_id)
    if row is None or row.course_id != course_id:
        raise ApiError(404, ErrorCode.not_found, "draft not found")
    return row


def _module(db: Session, course_id: int, module_id: int | None) -> None:
    if module_id is None:
        return
    module = db.get(Module, module_id)
    if module is None or module.course_id != course_id:
        raise ApiError(422, ErrorCode.invalid, "the module is not part of this course")


# ------------------------------------------------------------------------------------------ drafts
@router.post("/courses/{course_id}/ai/drafts", response_model=AiDraftOut, status_code=202,
             operation_id="ai_drafts_create")
def create(request: Request, body: AiDraftIn, access: CourseInstructor):
    """Start drafting from the course material with the local model (a job; the draft is `generating`)."""
    engine = _engine(request)
    with Session(engine, expire_on_commit=False) as db:
        _module(db, access.course.id, body.module_id)
        row = AiDraft(course_id=access.course.id, module_id=body.module_id, kind=body.kind,
                      focus=body.focus.strip(), created_by=access.account_id)
        db.add(row)
        db.commit()
    job = jobs.enqueue(engine, draft_jobs.GENERATE, course_id=access.course.id, ref_id=row.id,
                       created_by=access.account_id)
    return _out(row, job.id)


@router.get("/courses/{course_id}/ai/drafts", response_model=list[AiDraftSummary],
            operation_id="ai_drafts_list")
def list_drafts(request: Request, access: CourseInstructor, status: DraftStatus | None = None,
                kind: DraftKind | None = None):
    with Session(_engine(request)) as db:
        q = select(AiDraft).where(AiDraft.course_id == access.course.id)
        if status:
            q = q.where(AiDraft.status == status)
        if kind:
            q = q.where(AiDraft.kind == kind)
        rows = db.exec(q.order_by(col(AiDraft.id).desc())).all()
        return [AiDraftSummary(id=r.id, kind=r.kind, module_id=r.module_id, status=r.status,
                             created_at=r.created_at, updated_at=r.updated_at) for r in rows]


@router.get("/courses/{course_id}/ai/drafts/{draft_id}", response_model=AiDraftOut,
            operation_id="ai_drafts_get")
def get_draft(request: Request, draft_id: int, access: CourseInstructor):
    with Session(_engine(request)) as db:
        return _out(_get(db, access.course.id, draft_id))


@router.patch("/courses/{course_id}/ai/drafts/{draft_id}", response_model=AiDraftOut,
              operation_id="ai_drafts_update",
              responses={409: {"description": "the draft is not in `draft` status"}})
def update_draft(request: Request, draft_id: int, body: AiDraftPatch, access: CourseInstructor):
    """Replace the content of a draft (the whole content, in the shape it was returned in)."""
    with Session(_engine(request), expire_on_commit=False) as db:
        _get(db, access.course.id, draft_id)
        row = db.exec(select(AiDraft).where(AiDraft.id == draft_id).with_for_update()).one()
        if row.status != "draft":
            raise ApiError(409, ErrorCode.conflict, "only a draft can be edited")
        try:
            content = draft_jobs.parse_content(row.kind, body.content)
        except ValueError as e:
            raise ApiError(422, ErrorCode.invalid, str(e)) from None
        # the instructor's text is scanned before it is stored: student data never reaches the table
        found = scan_document(json.dumps(content, ensure_ascii=False),
                              privacy_profile(access.course.course_type)).blocking
        if found:
            raise ApiError(422, ErrorCode.invalid,
                           "the privacy scan found student data: " + ", ".join(found))
        row.content = content
        row.updated_at = utcnow()
        db.add(row)
        db.commit()
        return _out(row)


@router.delete("/courses/{course_id}/ai/drafts/{draft_id}", status_code=204, operation_id="ai_drafts_discard")
def discard(request: Request, draft_id: int, access: CourseInstructor):
    """Discard a draft that was not accepted (accepted content is edited as normal content)."""
    with Session(_engine(request)) as db:
        _get(db, access.course.id, draft_id)
        # locked like accept: a discard waiting on an accept then sees `accepted` and refuses
        row = db.exec(select(AiDraft).where(AiDraft.id == draft_id).with_for_update()).one()
        if row.status == "accepted":
            raise ApiError(409, ErrorCode.conflict, "an accepted draft is already course content")
        row.status, row.updated_at = "discarded", utcnow()
        db.add(row)
        db.commit()
    return Response(status_code=204)


@router.post("/courses/{course_id}/ai/drafts/{draft_id}/accept", response_model=AiDraftAcceptOut,
             operation_id="ai_drafts_accept",
             responses={409: {"description": "the draft is not in `draft` status"},
                        422: {"description": "the content checks or the material scan refused it"}})
def accept(request: Request, draft_id: int, body: AiDraftAcceptIn, access: CourseInstructor):
    """Publish the draft: tier 2 into the content tables (KCs, check items and misconceptions become
    `active`, all or none), tier 1 as a Markdown course material. Students see it only from here on."""
    services = request.app.state.services
    course_id = access.course.id
    with Session(services.engine, expire_on_commit=False) as db:
        _get(db, course_id, draft_id)
        # locked while checked, so two requests cannot both accept it (one set of rows)
        row = db.exec(select(AiDraft).where(AiDraft.id == draft_id).with_for_update()).one()
        if row.status != "draft":
            raise ApiError(409, ErrorCode.conflict, "only a draft can be accepted")
        _module(db, course_id, body.module_id)
        created: dict[str, list[int]] = {}
        rebuild = None
        if row.kind in draft_jobs.TIER1:
            material = _store_material(services, access, row, body.module_id)
            created["materials"] = [material.id]
            rebuild = index_jobs.request_rebuild(services.engine, course_id, access.account_id)
        else:
            created = _create_content(request, row, body.module_id)
        row.status, row.updated_at = "accepted", utcnow()
        db.add(row)
        db.add(AuditLog(account_id=access.account_id, action="ai_draft.accept",
                        target=f"course:{course_id}", details={"draft_id": row.id, "kind": row.kind}))
        db.commit()
    return AiDraftAcceptOut(draft=_out(row), created=created, rebuild_job_id=rebuild.id if rebuild else None)


def _create_content(request: Request, row: AiDraft, module_id: int | None) -> dict[str, list[int]]:
    editor, items = _editor(request), row.content.get("items") or []
    if row.kind == "kcs":
        module = row.module_id or module_id
        if module is None:
            raise ApiError(422, ErrorCode.invalid, "module_id is required: the module of the new KCs")
        return {"kcs": [k.id for k in editor.create_drafted_kcs(row.course_id, module, items)]}
    # a KC name that is not (or no longer) an active KC of the course is a 422 from the editor
    if row.kind == "check_items":
        return {"check_items": [i.id for i in editor.create_drafted_items(row.course_id, items)]}
    return {"misconceptions": [m.id for m in editor.create_drafted_misconceptions(row.course_id, items)]}


def _slug(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "-", text.lower()).strip("-")[:60] or "draft"


def _store_material(services, access: CourseAccess, row: AiDraft, module_id: int | None):
    """The tier 1 draft as `<kind>-<title>-<id>.md`, scanned like an upload before it is stored."""
    title, body = row.content["title"], row.content["body"]
    sources = "".join(f"\n- {s}" for s in row.cited_sources)
    text = f"# {title}\n\n{body}\n" + (f"\n## Sources\n{sources}\n" if sources else "")
    data = text.encode("utf-8")
    place = row.module_id if row.module_id is not None else module_id
    try:
        filename = f"{row.kind}-{_slug(title)}-{row.id}.md"
        name = index_jobs.check_upload(filename, data, access.course.course_type)
        return index_jobs.store(services.engine, services.settings.data_path(), row.course_id, place, name,
                                data)
    except index_jobs.MaterialRefused as e:
        raise ApiError(422, ErrorCode.invalid, str(e)) from None
    except FileExistsError:
        raise ApiError(409, ErrorCode.conflict, "a material with this name exists; edit the title") from None


# ----------------------------------------------------------------------------------------- insights
@router.get("/courses/{course_id}/insights", response_model=InsightsOut, operation_id="insights_get")
def insights(request: Request, access: CourseInstructor):
    """Tier 3: which KCs the students asked about most and the most common misconceptions. Counts of KC and
    misconception codes only, never question text; a label is shown only when at least
    `learner.class_summary_min_group` different students contributed to it (and to the whole result)."""
    services = request.app.state.services
    group = max(5, services.settings.learner.class_summary_min_group)
    result, learners = course_insights(services.engine, access.course.id, group)
    with Session(services.engine) as db:
        kcs = {k.code: k.name for k in db.exec(select(Kc).where(Kc.course_id == access.course.id))}
        mcs = {m.code: m.statement for m in db.exec(
            select(CatalogMisconception).where(CatalogMisconception.course_id == access.course.id))}
    return InsightsOut(
        min_group=group, suppressed=learners < group,
        kc_question_counts=[LabelCountOut(label=c.label, name=kcs.get(c.label), count=c.count)
                            for c in result.kc_question_counts],
        misconception_counts=[LabelCountOut(label=c.label, name=mcs.get(c.label), count=c.count)
                              for c in result.misconception_counts])
