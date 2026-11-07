"""S10 fictional class insights: sparse cohorts and cross-course data stay private."""
import pytest

from app.instructor_ai.insights import (
    InsightEvent,
    InsightsError,
    aggregate_class_insights,
)


def _events(n=6, *, cid=100, label="KC-1", misconception="M-1"):
    return [InsightEvent(cid, f"fictional-{i}", label, misconception) for i in range(n)]


def test_aggregate_counts_have_no_question_text_or_student_identifiers():
    report = aggregate_class_insights(course_id=100, events=_events())
    assert [(x.label, x.count) for x in report.kc_question_counts] == [("KC-1", 6)]
    assert [(x.label, x.count) for x in report.misconception_counts] == [("M-1", 6)]
    assert "fictional-" not in repr(report)
    assert "private question" not in repr(report)


def test_suppresses_small_class_entirely():
    assert aggregate_class_insights(course_id=100, events=_events(4)).kc_question_counts == ()


def test_suppresses_sparse_label_even_in_large_class():
    events = _events(6)
    events.append(InsightEvent(100, "fictional-0", "KC-PRIVATE", "M-PRIVATE"))
    report = aggregate_class_insights(course_id=100, events=events)
    assert [(x.label, x.count) for x in report.kc_question_counts] == [("KC-1", 6)]
    assert [(x.label, x.count) for x in report.misconception_counts] == [("M-1", 6)]


def test_repeated_questions_count_but_not_as_distinct_people():
    events = _events(6) + [InsightEvent(100, "fictional-0", "KC-1", "M-1")] * 3
    report = aggregate_class_insights(course_id=100, events=events)
    assert report.kc_question_counts[0].count == 9
    assert report.misconception_counts[0].count == 9


def test_cross_course_event_is_rejected():
    with pytest.raises(InsightsError, match="Cross-course"):
        aggregate_class_insights(course_id=100, events=_events() + _events(1, cid=200))


@pytest.mark.parametrize("label", ["What is my grade?", "a/b", "", " "])
def test_free_text_cannot_be_used_as_label(label):
    with pytest.raises(InsightsError, match="KC label"):
        aggregate_class_insights(course_id=100, events=_events(5, label=label))


def test_extra_question_text_cannot_enter_event_schema():
    with pytest.raises(TypeError):
        InsightEvent(course_id=100, student_id="fictional-0",
                     kc_id="KC-1", question="private question")


def test_deterministic_order_and_limit():
    events = _events(5, label="KC-B", misconception=None)
    events += _events(5, label="KC-A", misconception=None)
    report = aggregate_class_insights(course_id=100, events=events, limit=1)
    assert [(x.label, x.count) for x in report.kc_question_counts] == [("KC-A", 5)]


def test_invalid_limits_fail_closed():
    with pytest.raises(InsightsError):
        aggregate_class_insights(course_id=100, events=_events(), min_group=1)
    with pytest.raises(InsightsError):
        aggregate_class_insights(course_id=100, events=_events(), limit=0)
