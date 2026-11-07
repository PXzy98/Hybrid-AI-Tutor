"""Course-level instructor insights: aggregate labels and counts, never question text.

This core has no HTTP or database access. A Z-owned access check must authorize the
instructor before using it; the future instructor AI receives only its aggregate.
"""
import re
from collections import Counter, defaultdict
from collections.abc import Sequence
from dataclasses import dataclass

_LABEL = re.compile(r"[A-Za-z0-9_.:-]{1,64}\Z")


class InsightsError(ValueError):
    """The input cannot safely produce an aggregate."""


@dataclass(frozen=True)
class InsightEvent:
    course_id: int
    student_id: str
    kc_id: str
    misconception_id: str | None = None


@dataclass(frozen=True)
class LabelCount:
    label: str
    count: int


@dataclass(frozen=True)
class ClassInsights:
    course_id: int
    kc_question_counts: tuple[LabelCount, ...]
    misconception_counts: tuple[LabelCount, ...]


def _eligible_counts(events: Sequence[tuple[str, str]], min_group: int,
                     limit: int) -> tuple[LabelCount, ...]:
    count = Counter(label for label, _ in events)
    participants: dict[str, set[str]] = defaultdict(set)
    for label, student_id in events:
        participants[label].add(student_id)
    eligible = [(label, total) for label, total in count.items()
                if len(participants[label]) >= min_group]
    eligible.sort(key=lambda item: (-item[1], item[0]))
    return tuple(LabelCount(label, total) for label, total in eligible[:limit])


def aggregate_class_insights(
    *, course_id: int, events: Sequence[InsightEvent],
    min_group: int = 5, limit: int = 20,
) -> ClassInsights:
    """Suppress cohort and label results with fewer than min_group distinct learners.

    Only allow canonical KC/misconception IDs, so arbitrary question content cannot
    be smuggled into a label. Repeated questions count as events; privacy thresholds
    count distinct pseudonymous students instead.
    """
    if type(course_id) is not int or course_id <= 0 or not 5 <= min_group <= 10000:
        raise InsightsError("Invalid course or minimum group size.")
    if type(limit) is not int or not 1 <= limit <= 50 or len(events) > 100000:
        raise InsightsError("Invalid result limit or event volume.")
    students: set[str] = set()
    questions: list[tuple[str, str]] = []
    misconceptions: list[tuple[str, str]] = []
    for event in events:
        if event.course_id != course_id or not event.student_id:
            raise InsightsError("Cross-course or invalid insight event.")
        if _LABEL.fullmatch(event.kc_id) is None:
            raise InsightsError("Invalid KC label.")
        if event.misconception_id is not None and _LABEL.fullmatch(event.misconception_id) is None:
            raise InsightsError("Invalid misconception label.")
        students.add(event.student_id)
        questions.append((event.kc_id, event.student_id))
        if event.misconception_id is not None:
            misconceptions.append((event.misconception_id, event.student_id))
    if len(students) < min_group:
        return ClassInsights(course_id, (), ())
    return ClassInsights(
        course_id=course_id,
        kc_question_counts=_eligible_counts(questions, min_group, limit),
        misconception_counts=_eligible_counts(misconceptions, min_group, limit),
    )
