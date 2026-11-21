"""Where the tier 3 class insights get their events (api-v2.md 3.6; task S10).

Built from rows that exist only for students who consented to learner data:
- "asked about a KC": the KC codes the understand step found in a question (`request_log.kc_ids`, V22), and
  the understand step's weak signals in `evidence_log` (`source = "understand"`, when weak evidence is on);
- "showed a misconception": any row that carries a misconception code (a chosen distractor, a weak signal).
No question text is stored anywhere, so none can reach the result: only KC and misconception codes.
"""
from sqlmodel import Session, col, select

from app.instructor_ai.insights import _LABEL, ClassInsights, InsightEvent, aggregate_class_insights
from app.storage.models import EvidenceLog, RequestLog

MAX_EVENTS = 100_000
MIN_GROUP = 5  # the core's lower bound; the setting `learner.class_summary_min_group` may raise it


def course_insights(engine, course_id: int, min_group: int, limit: int = 20) -> tuple[ClassInsights, int]:
    """The suppressed aggregate and the number of distinct learners behind it."""
    group = max(MIN_GROUP, min_group)
    with Session(engine) as db:
        asked = db.exec(select(EvidenceLog.student_id, EvidenceLog.kc_id)
                        .where(EvidenceLog.course_id == course_id, EvidenceLog.source == "understand")
                        .order_by(col(EvidenceLog.id).desc()).limit(MAX_EVENTS)).all()
        logged = db.exec(select(RequestLog.request_id, RequestLog.student_id, RequestLog.kc_ids)
                         .where(RequestLog.course_id == course_id, RequestLog.student_id != "deleted")
                         .order_by(col(RequestLog.id).desc()).limit(MAX_EVENTS)).all()
        shown = db.exec(select(EvidenceLog.student_id, EvidenceLog.kc_id, EvidenceLog.misconception_id)
                        .where(EvidenceLog.course_id == course_id,
                               col(EvidenceLog.misconception_id).is_not(None))
                        .order_by(col(EvidenceLog.id).desc()).limit(MAX_EVENTS)).all()
    # one event per question and KC; a weak signal of the same question would count it twice, so the request
    # log is used where it has KC codes and the weak signals only for questions recorded before V22
    events = [InsightEvent(course_id, student, kc) for _, student, kcs in logged for kc in (kcs or [])
              if isinstance(kc, str) and _LABEL.fullmatch(kc)]
    if not events:
        events = [InsightEvent(course_id, student, kc) for student, kc in asked if _LABEL.fullmatch(kc)]
    questions = aggregate_class_insights(course_id=course_id, min_group=group, limit=limit, events=events)
    misconceptions = aggregate_class_insights(
        course_id=course_id, min_group=group, limit=limit,
        events=[InsightEvent(course_id, student, kc, mc) for student, kc, mc in shown
                if _LABEL.fullmatch(kc) and _LABEL.fullmatch(mc)])
    learners = len({e.student_id for e in events} | {student for student, _, _ in shown})
    merged = ClassInsights(course_id, questions.kc_question_counts, misconceptions.misconception_counts)
    return merged, learners
