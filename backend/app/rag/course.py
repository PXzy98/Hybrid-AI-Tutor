"""Course retriever interface (task S4; course-structure.md section 7).

Retrieves from the course-level material plus one module (or the whole course when `module_id` is None).
A `question_kind` of "logistics" (T5) asks for the course-level files (syllabus, calendar, assignments) first.
`FakeCourseRetriever` returns fixed passages so that pipeline and frontend work can start before S4.
"""
from dataclasses import dataclass, field
from typing import Protocol

from app.core.schemas import Chunk


class CourseRetriever(Protocol):
    def retrieve(self, course_id: int, module_id: int | None, query: str, k: int = 4,
                 question_kind: str = "concept") -> list[Chunk]: ...


@dataclass
class FakeCourseRetriever:
    passages: list[Chunk] = field(default_factory=list)
    calls: list[tuple[int, int | None, str, int]] = field(default_factory=list)
    kinds: list[str] = field(default_factory=list)  # the question kind of every call

    def retrieve(self, course_id: int, module_id: int | None, query: str, k: int = 4,
                 question_kind: str = "concept") -> list[Chunk]:
        self.calls.append((course_id, module_id, query, k))
        self.kinds.append(question_kind)
        return self.passages[:k]
