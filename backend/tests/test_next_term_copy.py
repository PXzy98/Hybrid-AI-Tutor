"""V17 W12: start next term's course from this one (POST /api/v2/courses/{id}/copy). It copies what the
instructor built (settings, modules, content, draft quizzes, materials) and nothing about students.
Fictional data; the models are fakes."""
import pytest
from sqlmodel import Session, select

from app.platform import jobs
from app.storage.models import CourseInvite, CourseMember
from tests.conftest import csrf_client
from tests.test_ask_v2 import World, _login, rows

V2 = "/api/v2"
NOTES = b"# Circuits\n\nKirchhoff's current law: the currents into a node sum to zero.\n"
SYLLABUS = b"# Syllabus\n\nProblem set 3 is due on Friday of week 5.\n"
BODY = {"code": "ELG 5902 W", "title": "Fictional course, next term", "term_label": "Winter 2028"}
LEARNER_TABLES = ("session_turn", "request_log", "quiz_attempt", "usage_counter")


@pytest.fixture
def world(make_client, tmp_path):
    with make_client({"data_dir": str(tmp_path)}) as client:
        w = World(client)
        w.data = tmp_path
        yield w


def _filled(world):
    """The source course with a student's traces, settings, a quiz and two materials."""
    alice = _login(world.app, "alice")
    assert alice.post(f"{world.url}/ask", json={"question": "What is Ohm's law?"}).status_code == 200
    world.prof.patch(f"{world.url}", json={"guideline": "Answer briefly."})
    current = world.prof.get(f"{world.url}/settings").json()
    r = world.prof.put(f"{world.url}/settings", json={"values": {"routing_threshold": 0.7},
                                                     "version": current["version"]})
    assert r.status_code == 200, r.text
    question = {"kind": "true_false", "kc": None, "stem": "A resistor stores charge.", "answer": 1,
                "explanation": "A capacitor does."}
    r = world.prof.post(f"{world.url}/quizzes", json={"title": "Week 1", "module_id": world.module,
                                                     "questions": [question]})
    assert r.status_code == 201, r.text
    for name, data, module in (("kcl.md", NOTES, world.module), ("syllabus.md", SYLLABUS, None)):
        r = world.prof.post(f"{world.url}/materials", files={"file": (name, data, "text/markdown")},
                            data={"module_id": str(module)} if module else {})
        assert r.status_code == 201, r.text
    world.prof.post(f"{world.url}/invite/rotate")


def _count(table: str, course_id: int) -> int:
    return len([r for r in rows(table) if r.get("course_id") == course_id])


def test_the_copy_has_the_content_and_materials_but_no_student_data(world):
    _filled(world)
    r = world.prof.post(f"{world.url}/copy", json=BODY)
    assert r.status_code == 201, r.text
    body = r.json()
    new = body["course"]
    assert (new["code"], new["title"], new["term_label"], new["my_role"]) == (
        "ELG 5902 W", "Fictional course, next term", "Winter 2028", "instructor")
    assert new["course_type"] == "ece" and new["guideline"] == "Answer briefly."
    assert body["copied"] == {"modules": 1, "kcs": 1, "items": 1, "misconceptions": 0, "quizzes": 1,
                              "materials": 2}
    url = f"{V2}/courses/{new['id']}"
    modules = world.prof.get(f"{url}/modules").json()
    assert [m["code"] for m in modules] == ["circuits"]
    assert [k["code"] for k in world.prof.get(f"{url}/kcs").json()] == ["C.1"]
    assert [i["code"] for i in world.prof.get(f"{url}/check-items").json()] == ["C.1-q1"]
    assert world.prof.get(f"{url}/settings").json()["values"]["routing_threshold"] == 0.7
    quizzes = world.prof.get(f"{url}/quizzes").json()
    assert [(q["title"], q["status"], q["module_id"]) for q in quizzes] == [
        ("Week 1", "draft", modules[0]["id"])]
    listed = world.prof.get(f"{url}/materials").json()
    assert {(m["filename"], m["module_id"]) for m in listed["materials"]} == {
        ("kcl.md", modules[0]["id"]), ("syllabus.md", None)}
    folder = world.data / "courses" / str(new["id"]) / "materials"
    assert (folder / str(modules[0]["id"]) / "kcl.md").read_bytes() == NOTES
    assert (folder / "_course" / "syllabus.md").read_bytes() == SYLLABUS
    assert listed["rebuild_job_id"] == body["rebuild_job_id"] is not None
    jobs.run_pending(world.services)
    assert world.services.course_retriever.retrieve(new["id"], None, "problem set 3 due", 2)
    # the source course is unchanged and still has its files
    assert len(world.prof.get(f"{world.url}/materials").json()["materials"]) == 2
    # nothing about people
    with Session(world.services.engine) as db:
        members = db.exec(select(CourseMember).where(CourseMember.course_id == new["id"])).all()
        invites = db.exec(select(CourseInvite).where(CourseInvite.course_id == new["id"])).all()
    assert [(m.role, m.status) for m in members] == [("instructor", "active")] and invites == []
    for table in LEARNER_TABLES:
        assert _count(table, new["id"]) == 0, table
    assert _count("session_turn", world.course) > 0
    assert world.prof.get(f"{url}/members").json()[0]["role"] == "instructor"
    assert len(world.prof.get(f"{url}/members").json()) == 1


def test_a_course_without_content_or_materials_copies_to_an_empty_course(world):
    empty = world.prof.post(f"{V2}/courses", json={"code": "E 1", "title": "E", "course_type": "ece"}).json()
    r = world.prof.post(f"{V2}/courses/{empty['id']}/copy", json={"code": "E 2", "title": "E again"})
    assert r.status_code == 201, r.text
    assert r.json()["rebuild_job_id"] is None and r.json()["copied"]["materials"] == 0


def test_a_taken_code_is_a_conflict_and_leaves_nothing_behind(world):
    before = len(rows("course"))
    r = world.prof.post(f"{world.url}/copy", json={**BODY, "code": "ELG 5902"})
    assert r.status_code == 409
    assert len(rows("course")) == before


def test_a_disabled_course_type_is_refused_like_a_new_course(world):
    _, version, _ = world.services.settings_service.system_values()
    world.services.settings_service.save_system({"enabled_course_types": ["medical_science"]},
                                                expected_version=version, account_id=None)
    r = world.prof.post(f"{world.url}/copy", json=BODY)
    assert r.status_code == 422 and r.json()["code"] == "invalid"
    assert "ELG 5902 W" not in {c["code"] for c in rows("course")}


def test_only_an_instructor_of_the_course_can_copy_it(world):
    world.services.accounts.create_instructor("other", "a-long-password-1", must_change=False)
    other = csrf_client(world.app)
    assert other.post(f"{V2}/auth/login", json={"username": "other", "password": "a-long-password-1"}
                      ).status_code == 200
    alice, anon = _login(world.app, "alice"), csrf_client(world.app)
    assert other.post(f"{world.url}/copy", json=BODY).status_code == 404  # another course's instructor
    assert alice.post(f"{world.url}/copy", json=BODY).status_code == 404  # a student of the course
    assert anon.post(f"{world.url}/copy", json=BODY).status_code == 401
    assert "ELG 5902 W" not in {c["code"] for c in rows("course")}
