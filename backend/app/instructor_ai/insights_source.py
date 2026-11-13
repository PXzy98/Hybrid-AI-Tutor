"""Where the tier 3 class insights get their events (api-v2.md 3.6; task S10).

Built from the course's `evidence_log` rows, which exist only for students who consented to learner data:
- "asked about a KC": the understand step's weak signals (`source = "understand"`): the KC code only;
- "showed a misconception": any row that carries a misconception code (a chosen distractor, a weak signal).
No question text is stored anywhere, so none can reach the result: only KC and misconception codes.
`request_log` is not used: it keeps a module topic but no KC.
"""
from sqlmodel import Session, col, select

from app.instructor_ai.insights import _LABEL, ClassInsights, InsightEvent, aggregate_class_insights
from app.storage.models import EvidenceLog

MAX_EVENTS = 100_000
MIN_GROUP = 5  # the core's lower bound; the setting `learner.class_summary_min_group` may raise it


def course_insights(engine, course_id: int, min_group: int, limit: int = 20) -> tuple[ClassInsights, int]:
    """The suppressed aggregate and the number of distinct learners behind it."""
    group = max(MIN_GROUP, min_group)
    with Session(engine) as db:
        asked = db.exec(select(EvidenceLog.student_id, EvidenceLog.kc_id)
                        .where(EvidenceLog.course_id == course_id, EvidenceLog.source == "understand")
                        .order_by(col(EvidenceLog.id).desc()).limit(MAX_EVENTS)).all()
        shown = db.exec(select(EvidenceLog.student_id, EvidenceLog.kc_id, EvidenceLog.misconception_id)
                        .where(EvidenceLog.course_id == course_id,
                               col(EvidenceLog.misconception_id).is_not(None))
                        .order_by(col(EvidenceLog.id).desc()).limit(MAX_EVENTS)).all()
    questions = aggregate_class_insights(
        course_id=course_id, min_group=group, limit=limit,
        events=[InsightEvent(course_id, student, kc) for student, kc in asked if _LABEL.fullmatch(kc)])
    misconceptions = aggregate_class_insights(
        course_id=course_id, min_group=group, limit=limit,
        events=[InsightEvent(course_id, student, kc, mc) for student, kc, mc in shown
                if _LABEL.fullmatch(kc) and _LABEL.fullmatch(mc)])
    learners = len({student for student, _ in asked} | {student for student, _, _ in shown})
    merged = ClassInsights(course_id, questions.kc_question_counts, misconceptions.misconception_counts)
    return merged, learners
