"""API v2 learner endpoints (api-v2.md 3.5, 3.6; course-structure.md 4.4, 4.5; task S9): what a student does
in a course, and what the instructor may see. Rule 9: what must not be seen is not returned."""
import pytest
from sqlmodel import Session

from app.storage.models import CourseMember
from tests.test_ask_v2 import V2, World, _login, rows

Q1 = {"item_id": "C.1-q1", "choice": "A"}  # the correct choice


def set_mode(world, mode: str) -> None:
    current = world.prof.get(f"{world.url}/settings").json()
    r = world.prof.put(f"{world.url}/settings", json={"values": {"visibility_mode": mode},
                                                     "version": current["version"]})
    assert r.status_code == 200, r.text


@pytest.fixture
def world(make_client):
    with make_client() as client:
        w = World(client)
        w.consent("alice")
        w.sid = w.students["alice"].student_id
        yield w


def test_check_answers_and_profile_belong_to_the_course(world):
    alice = _login(world.app, "alice")
    r = alice.post(f"{world.url}/check", json=Q1)
    assert r.status_code == 200 and r.json()["correct"] is True and r.json()["kc_id"] == "C.1"
    assert {e["course_id"] for e in rows("evidence_log")} == {world.course}
    # the demo course does not know this item, and its own profile is untouched
    demo = f"{V2}/courses/{world.demo}"
    assert alice.post(f"{demo}/check", json=Q1).status_code == 404
    profile = alice.get(f"{world.url}/me/profile").json()
    assert profile["personalized"] and [m["code"] for m in profile["modules"]] == ["circuits"]
    assert profile["modules"][0]["module_id"] == world.module
    assert profile["modules"][0]["kcs"][0]["kc_id"] == "C.1"
    assert "p_mastery" not in str(profile)  # bands only
    assert profile["visibility"] == {"mode": "A", "acknowledged": False, "opted_out": False,
                                     "visible_to_instructor": False, "visible_since": None}
    demo_codes = {k["kc_id"] for m in alice.get(f"{demo}/me/profile").json()["modules"] for k in m["kcs"]}
    assert "C.1" not in demo_codes and demo_codes


def test_onboarding_runs_the_course_diagnostic(world):
    alice = _login(world.app, "alice")
    info = alice.get(f"{world.url}/onboarding", params={"module_id": world.module}).json()
    assert info["consent_given"] is True and [i["id"] for i in info["diagnostic"]] == ["C.1-q1"]
    assert "answer" not in info["diagnostic"][0]
    r = alice.post(f"{world.url}/onboarding", json={"module_id": world.module, "answers": [Q1]})
    assert r.status_code == 200 and r.json()["assessed"] == {"C.1": True}
    assert alice.get(f"{world.url}/onboarding", params={"module_id": 999999}).status_code == 404
    bad = {"module_id": world.module, "answers": [{"item_id": "HBP.1-q1", "choice": "A"}]}
    assert alice.post(f"{world.url}/onboarding", json=bad).status_code == 422  # another course's item


def test_without_consent_nothing_is_stored(world):
    alice = _login(world.app, "alice")
    alice.put(f"{V2}/me/consent", json={"given": False})
    r = alice.post(f"{world.url}/check", json=Q1)
    assert r.status_code == 200 and r.json()["kc_level"] is None
    assert rows("evidence_log") == []
    assert alice.get(f"{world.url}/me/profile").json()["personalized"] is False


def test_the_instructor_sees_a_student_only_in_mode_b_after_the_acknowledgement(world):
    alice = _login(world.app, "alice")
    overview, plan_url = (f"{world.url}/students/{world.sid}/overview",
                          f"{world.url}/students/{world.sid}/plan")
    plan = {"focus_kcs": ["C.1"], "goal": "intermediate", "notes": "Review the basics."}
    alice.post(f"{world.url}/check", json=Q1)  # before any visibility: never shown later

    def hidden():
        assert world.prof.get(overview).status_code == 404
        assert world.prof.put(plan_url, json=plan).status_code == 404
        assert world.prof.get(plan_url).status_code == 404

    hidden()  # mode A
    assert alice.post(f"{world.url}/me/visibility", json={"action": "acknowledge"}).status_code == 409
    set_mode(world, "B")
    hidden()  # mode B, not acknowledged yet
    seen = alice.post(f"{world.url}/me/visibility", json={"action": "acknowledge"}).json()
    assert seen["visible_to_instructor"] and seen["acknowledged"] and seen["visible_since"]

    body = world.prof.get(overview).json()
    assert body["kcs"] == [] and body["checks_answered"] == 0  # the earlier answer stays hidden
    alice.post(f"{world.url}/check", json=Q1)
    body = world.prof.get(overview).json()
    assert [k["kc_code"] for k in body["kcs"]] == ["C.1"] and body["checks_answered"] == 1
    views = [a for a in rows("audit_log") if a["action"] == "learner.overview.view"]
    assert len(views) == 2 and views[0]["details"] == {"student_id": world.sid}

    saved = world.prof.put(plan_url, json=plan)
    assert saved.status_code == 200 and saved.json()["focus_kcs"] == ["C.1"]
    assert world.prof.get(plan_url).json()["goal"] == "intermediate"
    assert alice.get(f"{world.url}/me/profile").json()["plan"]["notes"] == "Review the basics."
    assert world.prof.put(plan_url, json={**plan, "focus_kcs": ["HBP.1"]}).status_code == 422

    out = alice.post(f"{world.url}/me/visibility", json={"action": "opt_out"}).json()
    assert out["opted_out"] and not out["visible_to_instructor"]
    hidden()
    assert alice.get(f"{world.url}/me/profile").json()["plan"] is None
    alice.post(f"{world.url}/me/visibility", json={"action": "opt_in"})
    body = world.prof.get(overview).json()  # a new start: nothing from before the opt-in
    assert body["kcs"] == [] and world.prof.get(plan_url).status_code == 404

    set_mode(world, "A")  # back to A: nobody is visible, and B needs a new acknowledgement
    hidden()
    set_mode(world, "B")
    hidden()
    assert alice.get(f"{world.url}/me/profile").json()["visibility"]["acknowledged"] is False


def test_other_people_cannot_use_the_learner_endpoints(world):
    world.accounts = world.services.accounts
    world.accounts.create_instructor("other", "correct-horse-battery", must_change=False)
    other, bob, alice = _login(world.app, "other"), _login(world.app, "bob"), _login(world.app, "alice")
    set_mode(world, "B")
    alice.post(f"{world.url}/me/visibility", json={"action": "acknowledge"})
    for outsider in (other, bob):  # another course's instructor, a student outside the course
        assert outsider.get(f"{world.url}/students/{world.sid}/overview").status_code == 404
        summary = outsider.get(f"{world.url}/class-summary", params={"module_id": world.module})
        assert summary.status_code == 404
        assert outsider.get(f"{world.url}/me/profile").status_code == 404
        assert outsider.post(f"{world.url}/check", json=Q1).status_code == 404
    world.enrol("bob")  # a classmate is not an instructor
    assert bob.get(f"{world.url}/students/{world.sid}/overview").status_code == 404
    assert bob.get(f"{world.url}/students/{world.sid}/plan").status_code == 404
    assert bob.get(f"{world.url}/class-summary", params={"module_id": world.module}).status_code == 404
    assert world.prof.get(f"{world.url}/me/profile").status_code == 404  # students only
    # an unknown student and a student of another course look the same as a hidden one
    bob_sid = world.students["bob"].student_id
    assert world.prof.get(f"{world.url}/students/nobody/overview").status_code == 404
    assert world.prof.get(f"{world.url}/students/{bob_sid}/overview").status_code == 404  # not acknowledged


def test_class_summary_counts_only_the_course_and_hides_small_groups(make_client):
    with make_client({"learner": {"class_summary_min_group": 2}}) as client:
        world = World(client)
        world.enrol("bob")
        for name in ("alice", "bob"):
            world.consent(name)
            _login(world.app, name).post(f"{world.url}/check", json=Q1)
        r = world.prof.get(f"{world.url}/class-summary", params={"module_id": world.module})
        assert r.status_code == 200 and r.json()["students"] == 2 and not r.json()["suppressed"]
        assert sum(v or 0 for v in r.json()["kcs"][0]["counts"].values()) == 2
        with Session(world.services.engine) as db:  # one student left: too few to show anything
            member = db.exec(CourseMember.__table__.select().where(
                CourseMember.course_id == world.course,
                CourseMember.account_id == world.students["bob"].id)).first()
            db.exec(CourseMember.__table__.delete().where(CourseMember.id == member.id))
            db.commit()
        r = world.prof.get(f"{world.url}/class-summary", params={"module_id": world.module})
        assert r.json()["suppressed"] is True and r.json()["kcs"] == []


def test_a_student_deletes_their_data_in_one_course_only(world):
    alice = _login(world.app, "alice")
    demo = f"{V2}/courses/{world.demo}"
    alice.post(f"{world.url}/check", json=Q1)
    alice.post(f"{world.url}/ask", json={"question": "What is a volt?"})
    alice.post(f"{demo}/ask", json={"question": "What is asthma?"})
    alice.put(f"{V2}/me/preferences", json={"detail": "detailed"})
    assert alice.delete(f"{world.url}/me/learning-data").status_code == 204
    assert rows("evidence_log") == [] and rows("learner_kc_state") == []
    assert {t["course_id"] for t in rows("session_turn")} == {world.demo}
    logs = {(r["course_id"], r["student_id"]) for r in rows("request_log")}
    assert logs == {(world.course, "deleted"), (world.demo, world.sid)}
    assert alice.get(f"{V2}/me/preferences").json()["detail"] == "detailed"
    assert alice.get(f"{V2}/me/consent").json()["given"] is True
    assert alice.get(f"{world.url}/conversations").json() == []
    assert alice.get(f"{world.url}/me/profile").status_code == 200  # still a member


def test_members_list_gives_the_student_id_for_the_learner_endpoints(world):
    members = world.prof.get(f"{world.url}/members").json()
    by_role = {m["role"]: m for m in members}
    assert by_role["student"]["student_id"] == world.sid and by_role["instructor"]["student_id"] is None
