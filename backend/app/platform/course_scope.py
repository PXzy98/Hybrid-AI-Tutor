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

from sqlmodel import Session, select

from app.core.schemas import Chunk
from app.storage.models import Course, Module

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
                chunks = indexed.retrieve(self.course_id, self.modules.get(topic), query, k)
            except Exception:  # noqa: BLE001 - no published index yet
                chunks = []
        if not chunks and self.course_id == self.services.content.course_id and topic in self.modules:
            chunks = self.services.retriever.retrieve(query, topic, k, kc_ids, level)
        return chunks


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
