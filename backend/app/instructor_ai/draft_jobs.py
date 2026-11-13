"""Instructor AI tiers 1 and 2 as a background job (api-v2.md 3.7; guide 4.9; tasks S6, S7).

`ai_draft.generate`: the course material passages come from the course retriever, the core generators
(`drafts.py`, `structure_drafts.py`) call the **local** model through the gateway (trusted local only: the
material never leaves the course's server), and the result is stored on the `ai_draft` row as an editable
draft. Nothing is visible to students until the instructor accepts it. No student data is used.
"""
from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter, ValidationError, field_validator
from sqlmodel import Session, select

from app.core.schemas import Chunk
from app.instructor_ai import structure_drafts as tier2
from app.instructor_ai.drafts import DraftError, generate_tier1_draft
from app.instructor_ai.eval import passages as fallback_passages
from app.platform import jobs
from app.storage.models import AiDraft, Course, Kc, Module, utcnow

GENERATE = "ai_draft.generate"
TIER1 = ("project_ideas", "sample_proposal", "faq")
TIER2 = ("kcs", "check_items", "misconceptions")
KINDS = (*TIER1, *TIER2)
PASSAGES, PASSAGE_CHARS = 8, 1200

_QUERY = {
    "project_ideas": "project topic deliverable assignment proposal",
    "sample_proposal": "project proposal writing requirements deliverable",
    "faq": "deadline grading policy assignment submission schedule",
}


# ------------------------------------------------------------------------- stored (editable) content
class Tier1Content(BaseModel):
    model_config = ConfigDict(extra="forbid")
    title: str = Field(min_length=1, max_length=180)
    body: str = Field(min_length=1, max_length=14000)

    @field_validator("title", "body")
    @classmethod
    def meaningful(cls, value: str) -> str:
        if not value.strip():
            raise ValueError("blank text")
        return value.strip()


class KcContent(tier2.KCDraft):
    citations: list[StrictInt] = Field(default_factory=list, max_length=24)  # not stored


class CheckItemContent(tier2.CheckItemDraft):
    citations: list[StrictInt] = Field(default_factory=list, max_length=24)


class MisconceptionContent(tier2.MisconceptionDraft):
    citations: list[StrictInt] = Field(default_factory=list, max_length=24)


ITEM_TYPES = {"kcs": KcContent, "check_items": CheckItemContent, "misconceptions": MisconceptionContent}
_LISTS = {kind: TypeAdapter(list[model]) for kind, model in ITEM_TYPES.items()}


def parse_content(kind: str, content: dict) -> dict:
    """The content of an edited draft in its stored shape; raises ValueError (no text echoed)."""
    try:
        if kind in TIER1:
            return Tier1Content.model_validate(content).model_dump()
        if not isinstance(content, dict) or set(content) != {"items"}:
            raise ValueError("a structure draft has exactly one field, items")
        items = _LISTS[kind].validate_python(content["items"])
        if not 1 <= len(items) <= 12:
            raise ValueError("a draft has 1 to 12 items")
        return {"items": [i.model_dump(exclude={"citations"}) for i in items]}
    except ValidationError as e:
        error = e.errors()[0]
        where = ".".join(str(p) for p in error["loc"])
        raise ValueError(f"invalid content: {where}: {error['msg']}") from None


# ------------------------------------------------------------------------------------------ the job
def _passages(services, course_id: int, module: Module | None, query: str) -> list[Chunk]:
    """Material of the module (and the course-level files), or of the whole course; scanned at upload."""
    retriever = getattr(services, "course_retriever", None)
    found: list[Chunk] = []
    if retriever is not None:
        try:
            found = list(retriever.retrieve(course_id, module.id if module else None, query, PASSAGES))
        except Exception:  # noqa: BLE001 - no index yet: fall back below
            found = []
    if not found and module is not None:  # the demo course without a course index
        texts = fallback_passages(services, course_id, module, query, k=PASSAGES)
        found = [Chunk(text=t, source="course material", topic=module.code, score=0.0) for t in texts]
    # the retriever is scoped to the course: stamp the scope the core checks, and cap the size
    return [c.model_copy(update={"text": c.text[:PASSAGE_CHARS],
                                 "metadata": {**c.metadata, "course_id": course_id}}) for c in found]


def _save(engine, draft_id: int, **changes) -> None:
    with Session(engine) as db:
        row = db.get(AiDraft, draft_id)
        if row is None or row.status != "generating":  # discarded while the model was working
            return
        for name, value in changes.items():
            setattr(row, name, value)
        row.updated_at = utcnow()
        db.add(row)
        db.commit()


@jobs.handler(GENERATE)
async def generate(services, job) -> None:
    with Session(services.engine) as db:
        draft = db.get(AiDraft, job.ref_id)
        course = db.get(Course, draft.course_id)
        module = db.get(Module, draft.module_id) if draft.module_id else None
        kcs = db.exec(select(Kc).where(Kc.course_id == draft.course_id, Kc.status == "active")
                      .order_by(Kc.id)).all()
        kind, course_id, focus, title = draft.kind, draft.course_id, draft.focus, course.title
    scope_kcs = [k for k in kcs if module is None or k.module_id == module.id]
    query = " ".join([focus or (module.title if module else title), _QUERY.get(kind, ""),
                      *(f"{k.name} {k.definition}" for k in scope_kcs[:6])]).strip()
    settings = services.effective(course_id)
    try:
        chunks = _passages(services, course_id, module, query)
        if not chunks:
            raise DraftError("no indexed course material to draft from")
        if kind in TIER1:
            result = await generate_tier1_draft(course_id=course_id, kind=kind, passages=chunks,
                                                gateway=services.gateway, settings=settings)
            content = {"title": result.title, "body": result.body}
        else:
            if kind != "kcs" and not kcs:
                raise DraftError("the course has no KCs yet: draft and accept the KCs first")
            result = await tier2.generate_structure_draft(
                course_id=course_id, kind=kind, passages=chunks, gateway=services.gateway, settings=settings,
                known_kc_names=[k.name for k in kcs])
            content = {"items": [i.model_dump(exclude={"citations"}) for i in result.items]}
    except Exception as e:
        _save(services.engine, job.ref_id, status="failed", error=jobs._message(e))
        raise
    _save(services.engine, job.ref_id, status="draft", content=content,
          cited_sources=list(dict.fromkeys(result.cited_sources)))
