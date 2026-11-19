"""Instructor AI tiers 1 and 2 as a background job (api-v2.md 3.7; guide 4.9; tasks S6, S7).

`ai_draft.generate`: the course material passages come from the course retriever, the core generators
(`drafts.py`, `structure_drafts.py`) call the **local** model through the gateway (trusted local only: the
material never leaves the course's server), and the result is stored on the `ai_draft` row as an editable
draft. Nothing is visible to students until the instructor accepts it. No student data is used.
"""
import shutil
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, StrictInt, TypeAdapter, ValidationError, field_validator
from sqlmodel import Session, col, select

from app.core.schemas import Chunk
from app.instructor_ai import structure_drafts as tier2
from app.instructor_ai.drafts import DraftError, generate_tier1_draft
from app.instructor_ai.eval import passages as fallback_passages
from app.platform import jobs
from app.rag.documents import extract_text
from app.storage.models import AiDraft, Course, Kc, Material, Module, utcnow

GENERATE = "ai_draft.generate"
TIER1 = ("project_ideas", "sample_proposal", "faq", "custom")
TIER2 = ("kcs", "check_items", "misconceptions")
KINDS = (*TIER1, *TIER2)
PASSAGES, PASSAGE_CHARS = 8, 1200
# chosen files or modules (V5): every matching passage of the course is ranked, then filtered, so passages of
# other files cannot crowd the chosen ones out (the retriever scores the whole index either way)
CHOSEN_POOL = 1_000_000

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
def upload_path(data_root: Path, course_id: int, draft_id: int, name: str) -> Path:
    """A file uploaded for one draft only (V6): kept until the draft job has read it."""
    return data_root / "courses" / str(course_id) / "draft_uploads" / str(draft_id) / name


def _bounded(paragraphs):
    """Paragraphs no longer than a passage: a longer one (a file without blank lines, or text extracted from
    a PDF, DOCX or PPTX joined by single newlines) is split at line ends, and a longer line at spaces."""
    for paragraph in paragraphs:
        if len(paragraph) <= PASSAGE_CHARS:
            yield paragraph
            continue
        current = ""
        for line in paragraph.split("\n"):
            parts = line.split(" ") if len(line) > PASSAGE_CHARS else [line]
            for i, part in enumerate(parts):
                while len(part) > PASSAGE_CHARS:  # one unbroken token longer than a passage
                    if current:
                        yield current
                        current = ""
                    yield part[:PASSAGE_CHARS]
                    part = part[PASSAGE_CHARS:]
                sep = " " if i else "\n"
                if current and len(current) + len(sep) + len(part) > PASSAGE_CHARS:
                    yield current
                    current = ""
                current = f"{current}{sep}{part}" if current else part
        if current:
            yield current


def _upload_passages(path: Path, course_id: int, query: str) -> list[Chunk]:
    """Passages of a file uploaded for this draft (scanned at upload): its paragraphs, the ones sharing the
    most words with the query first, then in the file's order."""
    text = extract_text(path)
    pieces, current = [], ""
    for paragraph in _bounded(p.strip() for p in text.split("\n\n")):
        if not paragraph:
            continue
        if current and len(current) + len(paragraph) > PASSAGE_CHARS:
            pieces.append(current)
            current = ""
        current = f"{current}\n\n{paragraph}".strip()
    if current:
        pieces.append(current)
    words = {w for w in query.lower().split() if len(w) > 3}
    ranked = sorted(enumerate(pieces), key=lambda ip: (-len(words & set(ip[1].lower().split())), ip[0]))
    return [Chunk(text=piece[:PASSAGE_CHARS], source=path.name, topic=f"course:{course_id}", score=0.0,
                  metadata={"course_id": course_id, "origin": "draft_upload"})
            for _, piece in ranked[:PASSAGES]]


def _chosen(engine, course_id: int, sources: dict):
    """A filter for the chosen modules or files (V5), or None for the default scope."""
    if sources.get("material_ids"):
        with Session(engine) as db:
            rows = db.exec(select(Material).where(Material.course_id == course_id,
                                                  col(Material.id).in_(sources["material_ids"]))).all()
        files = {(r.module_id, r.filename) for r in rows}
        return lambda c: (c.metadata.get("module_id"), c.source.rsplit("/", 1)[-1]) in files
    if sources.get("module_ids"):
        modules = set(sources["module_ids"])
        return lambda c: c.metadata.get("module_id") in modules
    return None


def _passages(services, course_id: int, module: Module | None, query: str,
              sources: dict | None = None) -> list[Chunk]:
    """Material of the module (and the course-level files), or of the whole course, or only of the chosen
    modules or files (V5); scanned at upload."""
    retriever = getattr(services, "course_retriever", None)
    found: list[Chunk] = []
    where = _chosen(services.engine, course_id, sources or {})
    if retriever is not None:
        try:
            if where is None:
                found = list(retriever.retrieve(course_id, module.id if module else None, query, PASSAGES))
            else:  # the whole course, then only the chosen files or modules
                ranked = retriever.retrieve(course_id, None, query, CHOSEN_POOL)
                found = [c for c in ranked if where(c)][:PASSAGES]
        except Exception:  # noqa: BLE001 - no index yet: fall back below
            found = []
    if not found and module is not None and where is None:  # the demo course without a course index
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
        request, sources = draft.request, dict(draft.sources or {})
    scope_kcs = [k for k in kcs if module is None or k.module_id == module.id]
    query = " ".join([focus or request or (module.title if module else title), _QUERY.get(kind, ""),
                      *(f"{k.name} {k.definition}" for k in scope_kcs[:6])]).strip()
    settings = services.effective(course_id)
    upload = (upload_path(services.settings.data_path(), course_id, job.ref_id, sources["upload"])
              if sources.get("upload") else None)
    try:
        if upload is not None:
            chunks = _upload_passages(upload, course_id, query) if upload.is_file() else []
        else:
            chunks = _passages(services, course_id, module, query, sources)
        if not chunks:
            raise DraftError("no indexed course material to draft from")
        if kind in TIER1:
            result = await generate_tier1_draft(course_id=course_id, kind=kind, passages=chunks,
                                                gateway=services.gateway, settings=settings, request=request)
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
    finally:
        if upload is not None:  # read once: a file for this draft only is not kept (V6)
            shutil.rmtree(upload.parent, ignore_errors=True)
    _save(services.engine, job.ref_id, status="draft", content=content,
          cited_sources=list(dict.fromkeys(result.cited_sources)))
