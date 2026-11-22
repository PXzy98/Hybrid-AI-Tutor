"""v5 V1: with `learner.instructor_individual_view` off (the deployment default) instructors see class
statistics only. Mode B cannot be chosen, a course stored in mode B reads as mode A, and no endpoint returns
one student's learning data, even for a student who acknowledged mode B before the switch went off."""
import pytest
from sqlmodel import Session, select

from app.storage.models import Account, AuditLog, ConfigHistory, Course, CourseMember, CourseSettings, utcnow
from tests.test_ask_v2 import V2, World, _login
from tests.test_learner_v2 import Q1

OFF = {"learner": {"instructor_individual_view": False, "class_summary_min_group": 1}}


@pytest.fixture
def world(make_client):
    with make_client(OFF) as client:
        w = World(client)
        w.consent("alice")
        w.sid = w.students["alice"].student_id
        yield w


def _engine(world):
    return world.app.state.services.engine


def _stored_mode_b_with_alice_visible(world) -> None:
    """The state a course could be in from before V1: mode B on the course row and an acknowledgement."""
    with Session(_engine(world)) as db:
        db.get(Course, world.course).visibility_mode = "B"
        member = db.exec(select(CourseMember).join(Account, CourseMember.account_id == Account.id).where(
            CourseMember.course_id == world.course, Account.student_id == world.sid)).one()
        member.visibility_ack_at = member.visible_since = utcnow()
        db.commit()


def test_mode_b_cannot_be_chosen(world):
    current = world.prof.get(f"{world.url}/settings").json()
    r = world.prof.put(f"{world.url}/settings", json={"values": {"visibility_mode": "B"},
                                                     "version": current["version"]})
    assert r.status_code == 422
    course = next(c for c in world.prof.get(f"{V2}/courses").json() if c["id"] == world.course)
    assert course["visibility_mode"] == "A" and course["individual_view"] is False


def test_a_course_stored_in_mode_b_shows_nothing_individual(world):
    alice = _login(world.app, "alice")
    alice.post(f"{world.url}/check", json=Q1)
    _stored_mode_b_with_alice_visible(world)
    alice.post(f"{world.url}/check", json=Q1)  # after the acknowledgement: would be shown in mode B

    course = next(c for c in world.prof.get(f"{V2}/courses").json() if c["id"] == world.course)
    assert course["visibility_mode"] == "A"
    base = f"{world.url}/students/{world.sid}"
    assert world.prof.get(f"{base}/overview").status_code == 404
    assert world.prof.get(f"{base}/plan").status_code == 404
    plan = {"focus_kcs": ["C.1"], "goal": "intermediate", "notes": "Review the basics."}
    assert world.prof.put(f"{base}/plan", json=plan).status_code == 404
    members = world.prof.get(f"{world.url}/members").json()
    assert all(not m.get("visible_to_instructor") for m in members)
    profile = alice.get(f"{world.url}/me/profile").json()
    assert profile["visibility"]["mode"] == "A" and profile["visibility"]["visible_to_instructor"] is False
    assert alice.post(f"{world.url}/me/visibility", json={"action": "acknowledge"}).status_code == 409


def test_a_stored_mode_b_does_not_block_saving_other_settings(world):
    """Codex review of V1: the settings page sends back the values it read; a stored B must not come back."""
    from app.storage.models import CourseSettings

    current = world.prof.get(f"{world.url}/settings").json()
    with Session(_engine(world)) as db:
        db.add(CourseSettings(course_id=world.course, visibility_mode="B", version=current["version"] + 1))
        db.commit()
    current = world.prof.get(f"{world.url}/settings").json()
    assert current["values"]["visibility_mode"] is None
    r = world.prof.put(f"{world.url}/settings", json={"values": {**current["values"], "local_only": True},
                                                     "version": current["version"]})
    assert r.status_code == 200, r.text


def _store_b_settings(world) -> int:
    current = world.prof.get(f"{world.url}/settings").json()
    with Session(_engine(world)) as db:
        db.add(CourseSettings(course_id=world.course, visibility_mode="B", version=current["version"] + 1))
        db.commit()
    _stored_mode_b_with_alice_visible(world)
    return world.prof.get(f"{world.url}/settings").json()["version"]


def _alice_member(world) -> CourseMember:
    with Session(_engine(world)) as db:
        return db.exec(select(CourseMember).join(Account, CourseMember.account_id == Account.id).where(
            CourseMember.course_id == world.course, Account.student_id == world.sid)).one()


def _visibility_changes(world) -> int:
    with Session(_engine(world)) as db:
        history = db.exec(select(ConfigHistory).where(ConfigHistory.course_id == world.course)).all()
        audit = db.exec(select(AuditLog).where(AuditLog.target == f"course:{world.course}")).all()
    changed = [a for a in audit if "visibility_mode" in (a.details or {}).get("changed", [])]
    return len([h for h in history if h.values.get("visibility_mode") != (h.previous or {}).get(
        "visibility_mode")]) + len(changed)


def test_saving_other_settings_keeps_a_stored_b_and_its_acknowledgements(world):
    version = _store_b_settings(world)
    current = world.prof.get(f"{world.url}/settings").json()
    assert current["values"]["visibility_mode"] is None
    r = world.prof.put(f"{world.url}/settings", json={"values": {**current["values"], "local_only": True},
                                                     "version": version})
    assert r.status_code == 200, r.text
    with Session(_engine(world)) as db:
        assert db.get(CourseSettings, world.course).visibility_mode == "B"
        assert db.get(CourseSettings, world.course).local_only is True
    member = _alice_member(world)
    assert member.visibility_ack_at is not None and member.visible_since is not None
    assert _visibility_changes(world) == 0
    again = world.prof.get(f"{world.url}/settings").json()
    r = world.prof.put(f"{world.url}/settings", json={"values": {**again["values"], "visibility_mode": "B"},
                                                     "version": again["version"]})
    assert r.status_code == 422


def test_restoring_an_entry_with_b_works_while_off(world):
    version = _store_b_settings(world)
    with Session(_engine(world)) as db:
        entry = ConfigHistory(account_id=None, scope="course", course_id=world.course, version=1,
                              values={"visibility_mode": "B", "local_only": True}, previous={})
        db.add(entry)
        db.commit()
        entry_id = entry.id
    r = world.prof.post(f"{world.url}/settings/restore/{entry_id}")
    assert r.status_code == 200, r.text
    with Session(_engine(world)) as db:
        row = db.get(CourseSettings, world.course)
        assert row.visibility_mode == "B" and row.local_only is True and row.version > version
    assert _alice_member(world).visibility_ack_at is not None


def test_acknowledgements_are_cleared_at_startup_while_off(world):
    from app.learner.course_views import invalidate_acknowledgements_while_off

    _store_b_settings(world)
    assert _alice_member(world).visibility_ack_at is not None
    assert invalidate_acknowledgements_while_off(_engine(world), False) == [world.course]
    member = _alice_member(world)
    assert member.visibility_ack_at is None and member.visible_since is None
    assert invalidate_acknowledgements_while_off(_engine(world), False) == []  # idempotent
    with Session(_engine(world)) as db:
        actions = [a.action for a in db.exec(select(AuditLog)).all()]
    assert actions.count("visibility.reset.individual_views_off") == 1
    alice = _login(world.app, "alice")
    assert alice.post(f"{world.url}/me/visibility", json={"action": "acknowledge"}).status_code == 409
    assert _alice_member(world).visibility_ack_at is None


def test_acknowledgements_of_an_inherited_mode_b_are_cleared_too(world):
    """Mode B on the course row, no settings override: the acknowledgement must not outlive the switch."""
    from app.learner.course_views import invalidate_acknowledgements_while_off

    _stored_mode_b_with_alice_visible(world)
    assert invalidate_acknowledgements_while_off(_engine(world), False) == [world.course]
    member = _alice_member(world)
    assert member.visibility_ack_at is None and member.visible_since is None


def test_nothing_is_cleared_while_individual_views_are_on(world):
    from app.learner.course_views import invalidate_acknowledgements_while_off

    _store_b_settings(world)
    assert invalidate_acknowledgements_while_off(_engine(world), True) == []
    assert _alice_member(world).visibility_ack_at is not None


def test_quiz_results_are_class_statistics_only(world):
    _stored_mode_b_with_alice_visible(world)
    body = {"title": "Week 1 check", "module_id": world.module,
            "questions": [{"kind": "true_false", "kc": None, "stem": "A resistor stores charge.",
                           "answer": 1, "explanation": "A capacitor stores charge."}]}
    quiz = world.prof.post(f"{world.url}/quizzes", json=body).json()
    world.prof.patch(f"{world.url}/quizzes/{quiz['id']}", json={"status": "published"})
    alice = _login(world.app, "alice")
    assert alice.post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [1]}).status_code == 201
    res = world.prof.get(f"{world.url}/quizzes/{quiz['id']}/results").json()
    assert res["attempts"] == 1 and res["mean_score"] == 1.0  # the class statistics stay
    assert res["students"] == []


def test_the_consent_text_says_the_instructor_sees_statistics_only(world):
    from app.privacy.profiles import STATISTICS_ONLY_NOTE

    alice = _login(world.app, "alice")
    info = alice.get(f"{world.url}/onboarding", params={"module_id": world.module}).json()
    assert info["consent_text"].endswith(STATISTICS_ONLY_NOTE)
