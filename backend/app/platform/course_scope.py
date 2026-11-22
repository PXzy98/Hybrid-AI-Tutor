"""The course a request runs in (guide 4.5; course-structure.md 4.1, 7, 8).

One pipeline runner serves every course: its steps read `services.content`, `services.learner`,
`services.retriever` and `services.sessions`, and inside `use(scope)` those names give the request's
course instead of the demo course that API v1 serves. `CourseScopes` builds and caches one scope per
course; a scope is rebuilt when the course's content or the component set (settings) changes.
"""
import contextlib
import copy
from contextvars import ContextVar
from dataclasses import dataclass
from threading import Lock

from sqlmodel import Session, col, select

from app.core.schemas import Chunk
from app.storage.models import Announcement, Course, Module

ANNOUNCEMENTS_PER_QUESTION = 2  # announcements sharing two words or more with a logistics question
SCOPED = ("content", "learner", "retriever", "sessions")
GENERAL_TOPIC = "general"  # a question about the course as a whole (no module chosen)


@dataclass
class CourseScope:
    course_id: int
    content: object  # ContentStore of the course
    learner: object  # LearnerModel bound to the course
    retriever: object  # Retriever over the course's own material
    sessions: object  # SessionStore limited to the course
    modules: dict[str, int]  # module code -> id


_current: ContextVar[CourseScope | None] = ContextVar("course_scope", default=None)


def current() -> CourseScope | None:
    return _current.get()


@contextlib.contextmanager
def use(scope: CourseScope):
    token = _current.set(scope)
    try:
        yield scope
    finally:
        _current.reset(token)


_question_kind: ContextVar[str] = ContextVar("question_kind", default="concept")


@contextlib.contextmanager
def question_kind(kind: str):
    """Tell the course retriever what the request asks (T5): "logistics" searches the course-level files
    (syllabus, calendar, assignments) first. Like `use`, it follows the request into worker threads."""
    token = _question_kind.set(kind)
    try:
        yield
    finally:
        _question_kind.reset(token)


class CourseModuleRetriever:
    """The `Retriever` interface over the course index (S4): the topic is the module code; a question
    without a module searches the whole course. The demo course without an index of its own falls back to
    the v1 retriever, so it answers as in API v1."""

    def __init__(self, services, course_id: int, modules: dict[str, int]) -> None:
        self.services, self.course_id, self.modules = services, course_id, modules

    def retrieve(self, query: str, topic: str, k: int = 4, kc_ids=None, level=None) -> list[Chunk]:
        indexed = getattr(self.services, "course_retriever", None)
        chunks: list[Chunk] = []
        if indexed is not None:
            try:
                # Retrievers that predate T5 take no question kind: only a logistics question passes it.
                extra = {"question_kind": "logistics"} if _question_kind.get() == "logistics" else {}
                chunks = indexed.retrieve(self.course_id, self.modules.get(topic), query, k, **extra)
            except Exception:  # noqa: BLE001 - no published index yet
                chunks = []
        if not chunks and self.course_id == self.services.content.course_id and topic in self.modules:
            chunks = self.services.retriever.retrieve(query, topic, k, kc_ids, level)
        if _question_kind.get() == "logistics":
            chunks = self.announcements(query) + chunks
        return chunks

    def announcements(self, query: str) -> list[Chunk]:
        """The course announcements that share words with a logistics question ("when is the proposal
        due?"), as course-level passages: instructors post dates and changes there that the files do not
        have. Announcements are course text, scanned for student data when saved (V20)."""
        from app.rag.query_text import analyze

        asked = {w for w in analyze(query) if " " not in w}
        engine = getattr(self.services, "engine", None)
        if not asked or engine is None:
            return []
        try:
            with Session(engine) as db:
                rows = db.exec(select(Announcement).where(Announcement.course_id == self.course_id)
                               .order_by(col(Announcement.created_at).desc()).limit(50)).all()
        except Exception:  # noqa: BLE001 - a database problem must not stop the answer
            return []
        ranked = []
        for row in rows:
            shared = len(asked & {w for w in analyze(f"{row.title} {row.body}") if " " not in w})
            if shared >= min(2, len(asked)):  # one common word ("due", "set") is not enough
                ranked.append((shared + (1 if row.pinned else 0), row))
        ranked.sort(key=lambda item: -item[0])  # stable: newest first among equals
        return [Chunk(text=f"Course announcement of {row.created_at.date().isoformat()}: {row.title}\n\n"
                           f"{row.body}",
                      source=f"Announcement: {row.title}", topic=f"course:{self.course_id}", score=1.0,
                      metadata={"course_id": self.course_id, "module_id": None, "origin": "announcement"})
                for _, row in ranked[:ANNOUNCEMENTS_PER_QUESTION]]


class CourseScopes:
    def __init__(self, services) -> None:
        self.services = services
        self._cache: dict[int, tuple[tuple, CourseScope]] = {}
        self._lock = Lock()

    def get(self, course_id: int) -> CourseScope:
        """The scope of the course; raises CatalogError/ContentError when its content cannot be loaded."""
        from app.catalog import load_course_content
        from app.learner.facade import build_learner_model

        services = self.services
        components = services.components
        with Session(services.engine) as db:
            course = db.get(Course, course_id)
            modules = {m.code: m.id for m in db.exec(select(Module).where(Module.course_id == course_id))}
        stamp = (course.content_version if course else None, id(components), id(services.content),
                 tuple(sorted(modules.items())))
        with self._lock:
            cached = self._cache.get(course_id)
            if cached and cached[0] == stamp:
                return cached[1]
        if course_id == services.content.course_id:  # the served demo course: the objects API v1 uses
            content, learner = services.content, components.learner
        else:
            content = load_course_content(services.engine, course_id)
            learner = build_learner_model(components.settings, services.engine, content)
        sessions = copy.copy(services.sessions)
        sessions.course_id = course_id
        scope = CourseScope(course_id=course_id, content=content, learner=learner, sessions=sessions,
                            retriever=CourseModuleRetriever(services, course_id, modules), modules=modules)
        with self._lock:
            self._cache[course_id] = (stamp, scope)
        return scope
