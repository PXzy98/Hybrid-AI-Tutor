"""Course catalog (task Z4): courses, modules, KCs, check items and misconceptions in the database.

- `import_topics` writes validated `TopicContent` (the YAML seed) into a course, one module per topic.
- `load_course_content` reads a course back as the `ContentStore` the learner model and pipeline use.
- `ensure_demo_course` creates "General Medical Knowledge" (MED 0000) from content/topics on first start
  (course-structure.md §11 steps 1–2). Unreviewed items and misconceptions are imported as `draft`
  (invisible to students) unless `content.seed_status` says otherwise.
"""
from collections.abc import Sequence

from sqlalchemy import Engine, text
from sqlmodel import Session, select

from app.learner.content import KC as ContentKc
from app.learner.content import (
    ContentError,
    ContentStatus,
    ContentStore,
    Item,
    Misconception,
    TopicContent,
    validate,
)
from app.storage.models import CatalogMisconception, CheckItem, Course, Kc, KcPrerequisite, Module

_SEED_LOCK = 590_202  # pg_advisory_xact_lock key for creating the demo course

DEMO_COURSE = {"code": "MED 0000", "title": "General Medical Knowledge", "course_type": "medical_science",
               "visibility_mode": "A"}


class CatalogError(ContentError):
    """The course is missing or the content to import is inconsistent."""


def create_course(db: Session, *, code: str, title: str, course_type: str = "general",
                  visibility_mode: str = "A", term_label: str = "") -> Course:
    course = Course(code=code, title=title, course_type=course_type, visibility_mode=visibility_mode,
                    term_label=term_label)
    db.add(course)
    db.flush()
    return course


def import_topics(db: Session, course_id: int, topics: Sequence[TopicContent],
                  status: ContentStatus | None = None) -> dict[str, int]:
    """Import topics as modules of the course (in the given order). `status` overrides item and
    misconception statuses; KCs are imported active (they are the course structure). Caller commits."""
    problems = validate(list(topics))
    if problems:
        raise CatalogError("invalid content:\n" + "\n".join(problems))
    if db.exec(select(Kc).where(Kc.course_id == course_id)).first() is not None:
        raise CatalogError("the course already has content; import into an empty course")
    counts = {"modules": 0, "kcs": 0, "items": 0, "misconceptions": 0}
    kc_ids: dict[str, int] = {}
    for position, topic in enumerate(topics):
        module = Module(course_id=course_id, code=topic.topic, title=topic.name, position=position,
                        guideline=topic.guideline)
        db.add(module)
        db.flush()
        counts["modules"] += 1
        for k in topic.kcs:
            row = Kc(course_id=course_id, module_id=module.id, code=k.id, name=k.name,
                     definition=k.definition, difficulty=k.difficulty, status="active")
            db.add(row)
            db.flush()
            kc_ids[k.id] = row.id
            counts["kcs"] += 1
        for k in topic.kcs:
            for p in k.prerequisites:
                db.add(KcPrerequisite(kc_id=kc_ids[k.id], prerequisite_id=kc_ids[p]))
        for m in topic.misconceptions:
            db.add(CatalogMisconception(course_id=course_id, kc_id=kc_ids[m.kc], code=m.id,
                                        statement=m.statement, correction=m.correction,
                                        status=status or m.status))
            counts["misconceptions"] += 1
        for i in topic.items:
            db.add(CheckItem(course_id=course_id, kc_id=kc_ids[i.kc], code=i.id, level=i.level, stem=i.stem,
                             options={key: o.model_dump() for key, o in i.options.items()}, answer=i.answer,
                             explanation=i.explanation, status=status or i.status))
            counts["items"] += 1
    db.flush()
    return counts


def load_course_content(engine: Engine, course_id: int) -> ContentStore:
    """The course's modules as validated topics. Retired KCs and modules without KCs are left out; items and
    misconceptions keep their status (the store serves only active ones)."""
    with Session(engine) as db:
        course = db.get(Course, course_id)
        if course is None:
            raise CatalogError(f"no course {course_id}")
        topics = course_topics(db, course_id)
    return ContentStore(topics, course_id=course_id, source=f"course {course.code}")


def course_topics(db: Session, course_id: int) -> list[TopicContent]:
    """The course's modules that have KCs, as topics (not validated across topics; see `validate`)."""
    modules = db.exec(select(Module).where(Module.course_id == course_id)
                      .order_by(Module.position, Module.id)).all()
    kcs = db.exec(select(Kc).where(Kc.course_id == course_id, Kc.status != "retired").order_by(Kc.id)).all()
    codes = {k.id: k.code for k in kcs}
    prereqs: dict[int, list[str]] = {}
    for edge in db.exec(select(KcPrerequisite).where(KcPrerequisite.kc_id.in_(list(codes)))).all():
        if edge.prerequisite_id in codes:
            prereqs.setdefault(edge.kc_id, []).append(codes[edge.prerequisite_id])
    items = db.exec(select(CheckItem).where(CheckItem.course_id == course_id).order_by(CheckItem.id)).all()
    mcs = db.exec(select(CatalogMisconception).where(CatalogMisconception.course_id == course_id)
                  .order_by(CatalogMisconception.id)).all()
    loaded_mcs = {m.code for m in mcs if m.kc_id in codes}  # misconceptions of retired KCs are left out

    def options(raw: dict) -> dict:
        """Drop tags that point at a misconception of a retired KC, so the remaining content stays valid."""
        return {key: {**o, "misconception": o.get("misconception") if o.get("misconception") in loaded_mcs
                      else None} for key, o in raw.items()}

    topics = []
    for module in modules:
        module_kcs = [k for k in kcs if k.module_id == module.id]
        if not module_kcs:
            continue  # a new module before its first KC
        ids = {k.id for k in module_kcs}
        topics.append(TopicContent(
            topic=module.code, name=module.title, guideline=module.guideline,
            kcs=[ContentKc(id=k.code, name=k.name, definition=k.definition, difficulty=k.difficulty,
                           prerequisites=sorted(prereqs.get(k.id, []))) for k in module_kcs],
            items=[Item(id=i.code, kc=codes[i.kc_id], level=i.level, stem=i.stem, options=options(i.options),
                        answer=i.answer, explanation=i.explanation, status=i.status)
                   for i in items if i.kc_id in ids],
            misconceptions=[Misconception(id=m.code, kc=codes[m.kc_id], statement=m.statement,
                                          correction=m.correction, status=m.status)
                            for m in mcs if m.kc_id in ids],
        ))
    return topics


def ensure_demo_course(engine: Engine, topics: Sequence[TopicContent], status: ContentStatus | None) -> int:
    """The demo course's ID; created and filled from the YAML seed when the catalog has no course yet."""
    with Session(engine) as db:
        # Parallel API workers on a new database: one creates the course, the others wait and then find it.
        db.exec(text("SELECT pg_advisory_xact_lock(:k)").bindparams(k=_SEED_LOCK))
        existing = db.exec(select(Course).where(Course.code == DEMO_COURSE["code"])).first()
        if existing is not None:
            return existing.id
        course = create_course(db, **DEMO_COURSE)
        import_topics(db, course.id, topics, status)
        db.commit()
        return course.id
