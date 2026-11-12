"""Learner data is per course (course-structure.md 4.1, 4.4): two courses never mix, and one course's data
can be exported and deleted as a whole. Preferences and consent are global."""
from sqlalchemy import text
from sqlmodel import Session

from app.catalog import create_course, load_course_content
from app.core.config import get_settings
from app.core.schemas import Evidence
from app.core.services import build_services
from app.learner.content import ContentStore
from app.learner.course_data import course_students, delete_course_data, export_course_data
from app.learner.facade import build_learner_model
from app.learner.preference import PreferenceSignal
from app.storage.testing import table_rows

A, B = "student-a", "student-b"


def strong(kc, correct, item=None):
    return Evidence(kc_id=kc, kind="strong", correct=correct, item_id=item, source="check")


def rows(table):
    return table_rows(get_settings().database_url, table)


def two_courses(use_config):
    """The demo course and a second course with the same KC codes (codes are unique per course only)."""
    services = build_services(use_config({}))
    with Session(services.engine) as db:
        other = create_course(db, code="TEST 2", title="Second course").id
        db.commit()
    content = services.content
    same_content = ContentStore([content.topic(t) for t in content.topics()], course_id=other)
    second = build_learner_model(services.settings, services.engine, same_content)
    return services, services.learner, second, other


def test_state_evidence_and_misconceptions_do_not_cross_courses(use_config):
    services, first, second, other = two_courses(use_config)
    first.set_consent(A, True)
    for _ in range(3):
        first.observe(A, strong("HBP.1", True, "HBP.1-q1"))
    mc = services.content.topic("high_blood_pressure").misconceptions[0]
    first.misconception_stated(A, mc.id)
    first.context(A, "high_blood_pressure")  # stores the module level

    prior = second.knowledge.prior("HBP.1").p_mastery
    assert first.knowledge.state(A, ["HBP.1"])["HBP.1"].p_mastery > prior
    assert second.knowledge.state(A, ["HBP.1"])["HBP.1"].p_mastery == prior
    assert second.repo.evidence(A) == [] and second.repo.answered_items(A) == {}
    assert second.repo.misconceptions(A) == [] and len(first.repo.misconceptions(A)) == 1

    second.observe(A, strong("HBP.1", False))
    assert {r["course_id"] for r in rows("learner_kc_state")} == {services.content.course_id, other}
    assert first.knowledge.state(A, ["HBP.1"])["HBP.1"].n_obs == 3
    assert second.knowledge.state(A, ["HBP.1"])["HBP.1"].n_obs == 1


def test_a_student_deletes_one_course_only_and_keeps_preferences(use_config):
    _, first, second, other = two_courses(use_config)
    first.set_consent(A, True)
    first.update_preferences(A, PreferenceSignal(dimension="detail", value="detailed", explicit=True))
    first.observe(A, strong("HBP.1", True))
    second.observe(A, strong("HBP.1", True))

    second.delete_course_data(A)
    assert second.repo.evidence(A) == [] and len(first.repo.evidence(A)) == 1
    assert first.preferences.get(A).detail == "detailed" and first.has_consent(A)


def test_withdrawing_consent_forgets_every_course(use_config):
    _, first, second, _ = two_courses(use_config)
    first.set_consent(A, True)
    first.observe(A, strong("HBP.1", True))
    second.observe(A, strong("HBP.1", True))
    second.set_consent(A, False)
    for table in ("learner_kc_state", "evidence_log", "learner_preference"):
        assert rows(table) == [], table


def test_export_and_delete_a_whole_course(use_config):
    services, first, second, other = two_courses(use_config)
    demo = services.content.course_id
    for sid in (A, B):
        first.set_consent(sid, True)
        first.observe(sid, strong("HBP.1", True, "HBP.1-q1"))
        first.context(sid, "high_blood_pressure")
    second.observe(A, strong("HBP.1", False))

    assert course_students(services.engine, demo) == [A, B]
    assert course_students(services.engine, other) == [A]
    exported = export_course_data(services.engine, demo)
    assert [e.student_id for e in exported] == [A, B]
    a = exported[0]
    assert a.kc_states[0].kc_id == "HBP.1" and a.kc_states[0].n_obs == 1
    assert a.evidence[0].item_id == "HBP.1-q1" and a.evidence[0].correct is True
    assert a.module_levels[0].module == "high_blood_pressure"
    only_b = export_course_data(services.engine, demo, [B, "nobody"])
    assert [e.student_id for e in only_b] == ["nobody", B] and only_b[0].evidence == []

    deleted = delete_course_data(services.engine, demo, B)  # one student
    assert deleted["evidence_log"] == 1 and course_students(services.engine, demo) == [A]
    deleted = delete_course_data(services.engine, demo)  # end of term
    assert deleted["learner_kc_state"] == 1 and course_students(services.engine, demo) == []
    assert course_students(services.engine, other) == [A]  # the other course is untouched
    assert first.has_consent(A) and first.has_consent(B)  # global data stays


def test_deleting_a_course_removes_its_learner_rows(use_config):
    services, _, second, other = two_courses(use_config)
    second.set_consent(A, True)
    second.observe(A, strong("HBP.1", True))
    with Session(services.engine) as db:
        from app.storage.models import Course

        db.delete(db.get(Course, other))
        db.commit()
    assert rows("evidence_log") == [] and rows("learner_kc_state") == []


def test_load_course_content_carries_the_course_id(use_config):
    services = build_services(use_config({}))
    content = load_course_content(services.engine, services.content.course_id)
    learner = build_learner_model(services.settings, services.engine, content)
    assert learner.repo.course_id == content.course_id is not None


def test_rows_from_before_the_course_column_join_the_demo_course_at_startup(use_config):
    """A database upgraded from before the course catalog has no course when the migration runs."""
    services = build_services(use_config({}))
    services.learner.set_consent(A, True)
    services.learner.observe(A, strong("HBP.1", True))
    with services.engine.begin() as conn:
        conn.execute(text("UPDATE learner_kc_state SET course_id = NULL"))
        conn.execute(text("UPDATE evidence_log SET course_id = NULL"))
    assert services.learner.repo.evidence(A) == []
    services = build_services(get_settings())  # the next start
    assert len(services.learner.repo.evidence(A)) == 1
    assert services.learner.knowledge.state(A, ["HBP.1"])["HBP.1"].n_obs == 1
