"""Tasks S6, S7, S10: instructor AI tiers 1 to 3 over the API (drafts, accept, insights), fake models only."""
import json
import zipfile
from pathlib import Path

import pytest
from sqlmodel import Session

from app.core.schemas import Chunk
from app.llm.fake import FakeLLMClient
from app.llm.gateway import FakeGateway
from app.platform import jobs
from app.rag.course import FakeCourseRetriever
from app.storage.models import CourseMember, EvidenceLog, Job, RequestLog
from tests.conftest import PASSWORD, csrf_client

V2 = "/api/v2"
ARCHIVES = Path(__file__).resolve().parents[2] / "data" / "demo_courses" / "archives"
PACK, OTHER_PACK = "mit_6_002_circuits", "mit_res_6_007_signals"  # open course packs (AGENTS.md)
SOURCE = "syllabus.md"


def _pack_course(name: str) -> dict:
    """The course of an open course pack, as the body of POST /courses."""
    with zipfile.ZipFile(ARCHIVES / f"{name}.zip") as z:
        m = json.loads(z.read(f"{name}/manifest.json"))
    return {"code": m["course_code"], "title": m["course_title"], "course_type": m["course_type"]}


def _pack_passage(name: str, document: str, starts: str) -> str:
    with zipfile.ZipFile(ARCHIVES / f"{name}.zip") as z:
        text = z.read(f"{name}/{document}").decode("utf-8")
    return next(line[2:] for line in text.splitlines() if line.startswith("- " + starts))


PASSAGE = _pack_passage(PACK, SOURCE, "Understand the basic electrical engineering principles")
SECRET_QUESTION = "zq-private-question-text-4471"
TIER1 = json.dumps({"title": "Pull-up projects", "body": "Build an I2C sensor board.", "citations": [1]})
KCS = json.dumps({"items": [
    {"name": "Open drain outputs", "definition": "Outputs that only pull a line low.",
     "prerequisite_names": ["Pull-up resistors"], "citations": [1]},
    {"name": "Bus capacitance", "definition": "Load that limits the rise time of a line.",
     "prerequisite_names": ["Open drain outputs"], "citations": [1]}]})
ITEMS = json.dumps({"items": [
    {"question": "What does a pull-up resistor do on an idle line?",
     "options": ["Holds it high", "Holds it low", "Cuts the line", "Doubles the voltage"],
     "correct_index": 0, "explanation": "It pulls the idle line to the supply.",
     "kc_names": ["Pull-up resistors"], "citations": [1]}]})
MISCONCEPTIONS = json.dumps({"items": [
    {"name": "Pull-ups lower the voltage", "incorrect_belief": "A pull-up resistor drops the supply voltage.",
     "correction": "It only sets the idle level of the line.", "kc_name": "Pull-up resistors",
     "citations": [1]}]})


def _login(app, username):
    c = csrf_client(app)
    assert c.post(f"{V2}/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


@pytest.fixture
def world(make_client, tmp_path, monkeypatch):
    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with make_client() as client:
        services = client.app.state.services
        for name in ("prof", "other"):
            services.accounts.create_instructor(name, PASSWORD, must_change=False)
        alice, _ = services.accounts.create_student("alice", "Alice")
        services.accounts.set_password(alice.id, PASSWORD, must_change=False)
        prof = _login(client.app, "prof")
        course = prof.post(f"{V2}/courses", json=_pack_course(PACK)).json()
        url = f"{V2}/courses/{course['id']}"
        module = prof.post(f"{url}/modules", json={"code": "circuits", "title": "Circuits"}).json()
        prof.post(f"{url}/kcs", json={"module_id": module["id"], "code": "C.1", "name": "Pull-up resistors",
                                      "difficulty": "basic"})
        with Session(services.engine) as db:
            db.add(CourseMember(course_id=course["id"], account_id=alice.id, role="student", status="active"))
            db.commit()
        services.course_retriever = FakeCourseRetriever([
            Chunk(text=PASSAGE, source=SOURCE, topic="circuits", score=1.0)])
        cloud = FakeLLMClient("CLOUD must not be called", model="cloud-x", backend="cloud")

        def use(reply) -> FakeLLMClient:
            local = FakeLLMClient(reply, model="local-9b")
            services.gateway = FakeGateway({"local": local, "cloud": cloud})
            return local

        use(TIER1)
        yield {"app": client.app, "services": services, "prof": prof, "url": url, "course": course,
               "module": module, "cloud": cloud, "use": use, "course_id": course["id"], "tmp": tmp_path}


def _generate(world, kind, reply, **body):
    local = world["use"](reply)
    r = world["prof"].post(f"{world['url']}/ai/drafts", json={"kind": kind, **body})
    assert r.status_code == 202 and r.json()["status"] == "generating" and r.json()["job_id"]
    assert jobs.run_pending(world["services"]) == 1
    return r.json(), local


def _draft(world, draft_id):
    return world["prof"].get(f"{world['url']}/ai/drafts/{draft_id}").json()


@pytest.mark.parametrize("kind", ["project_ideas", "sample_proposal", "faq"])
def test_tier1_kinds_generate_with_the_local_model_only(world, kind):
    created, local = _generate(world, kind, TIER1)
    job = world["prof"].get(f"{world['url']}/jobs/{created['job_id']}").json()
    assert (job["status"], job["progress"]) == ("done", 100)
    draft = _draft(world, created["id"])
    assert draft["status"] == "draft" and draft["kind"] == kind
    assert draft["content"] == {"title": "Pull-up projects", "body": "Build an I2C sensor board."}
    assert draft["cited_sources"] == [SOURCE]
    assert len(local.calls) == 1 and world["cloud"].calls == []
    assert PASSAGE in local.sent_text()


@pytest.mark.parametrize(("kind", "reply", "field"), [
    ("kcs", KCS, "name"), ("check_items", ITEMS, "question"), ("misconceptions", MISCONCEPTIONS, "name")])
def test_tier2_kinds_generate_with_the_local_model_only(world, kind, reply, field):
    created, local = _generate(world, kind, reply)
    draft = _draft(world, created["id"])
    assert draft["status"] == "draft" and field in draft["content"]["items"][0]
    assert "citations" not in draft["content"]["items"][0]
    assert draft["cited_sources"] == [SOURCE]
    assert len(local.calls) == 1 and world["cloud"].calls == []
    if kind != "kcs":  # the model is told which KCs exist
        assert "Pull-up resistors" in local.sent_text()


def test_tier1_edit_then_accept_stores_a_scanned_material(world):
    prof, url, services = world["prof"], world["url"], world["services"]
    created, _ = _generate(world, "faq", TIER1)
    edited = {"title": "Course FAQ", "body": "Office hours are listed in the syllabus."}
    r = prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": edited})
    assert r.status_code == 200 and r.json()["content"] == edited
    assert prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": {"title": "x"}}).status_code == 422
    r = prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={})
    assert r.status_code == 200 and r.json()["draft"]["status"] == "accepted"
    material_id = r.json()["created"]["materials"][0]
    listing = prof.get(f"{url}/materials").json()
    row = next(m for m in listing["materials"] if m["id"] == material_id)
    assert row["filename"].startswith("faq-course-faq-") and row["module_id"] is None
    assert row["scan_status"] == "accepted"
    path = world["tmp"] / "courses" / str(world["course_id"]) / "materials" / "_course" / row["filename"]
    text = path.read_text(encoding="utf-8")
    assert text.startswith("# Course FAQ") and "Office hours" in text and SOURCE in text
    with Session(services.engine) as db:  # indexed like an upload: a rebuild job waits
        assert db.get(Job, r.json()["rebuild_job_id"]).kind == "index.rebuild"
    # accepted: no more edits, accepting or discarding
    assert prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": edited}).status_code == 409
    assert prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={}).status_code == 409
    assert prof.delete(f"{url}/ai/drafts/{created['id']}").status_code == 409


def test_tier1_material_with_student_data_is_refused(world):
    prof, url = world["prof"], world["url"]
    created, _ = _generate(world, "faq", TIER1)
    body = "Student 300418277 got 87% on the midterm."
    content = {"title": "Class list", "body": body}
    r = prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": content})
    assert r.status_code == 422 and "STUDENT_ID" in r.json()["detail"] and "300418277" not in r.text
    assert "300418277" not in str(_draft(world, created["id"])["content"])  # never stored
    assert _draft(world, created["id"])["status"] == "draft"
    assert prof.get(f"{url}/materials").json()["materials"] == []


def test_kcs_accept_into_the_content_tables(world):
    prof, url = world["prof"], world["url"]
    created, _ = _generate(world, "kcs", KCS)
    r = prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={})
    assert r.status_code == 422 and "module_id" in r.json()["detail"]  # a module is needed
    assert prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={"module_id": 999999}).status_code == 422
    r = prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={"module_id": world["module"]["id"]})
    assert r.status_code == 200 and len(r.json()["created"]["kcs"]) == 2
    kcs = {k["name"]: k for k in prof.get(f"{url}/kcs").json()}
    drafted, bus = kcs["Open drain outputs"], kcs["Bus capacitance"]
    assert drafted["status"] == "active" and drafted["code"] == "circuits.1"
    assert drafted["module_id"] == world["module"]["id"]
    assert drafted["prerequisite_ids"] == [kcs["Pull-up resistors"]["id"]]
    assert bus["prerequisite_ids"] == [drafted["id"]]
    assert prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={}).status_code == 409  # only once
    assert len(prof.get(f"{url}/kcs").json()) == 3


def test_check_items_and_misconceptions_accept_as_active_content(world):
    prof, url = world["prof"], world["url"]
    created, _ = _generate(world, "check_items", ITEMS)
    r = prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={})
    assert r.status_code == 200 and len(r.json()["created"]["check_items"]) == 1
    [item] = prof.get(f"{url}/check-items").json()
    assert item["status"] == "active" and item["code"] == "C.1-q1" and item["level"] == "basic"
    assert item["options"][item["answer"]]["text"] == "Holds it high"  # the shuffle kept the right answer
    created, _ = _generate(world, "misconceptions", MISCONCEPTIONS)
    r = prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={})
    assert r.status_code == 200 and len(r.json()["created"]["misconceptions"]) == 1
    [mc] = prof.get(f"{url}/misconceptions").json()
    assert mc["status"] == "active" and mc["code"] == "C.1.MC1"
    assert mc["statement"] == "A pull-up resistor drops the supply voltage."


def test_an_edited_draft_with_an_unknown_kc_is_refused_and_creates_nothing(world):
    prof, url = world["prof"], world["url"]
    created, _ = _generate(world, "check_items", ITEMS)
    items = _draft(world, created["id"])["content"]["items"]
    items[0]["kc_names"] = ["No such KC"]
    r = prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": {"items": items}})
    assert r.status_code == 200
    r = prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={})
    assert r.status_code == 422 and "No such KC" in r.json()["detail"]
    assert prof.get(f"{url}/check-items").json() == []
    assert _draft(world, created["id"])["status"] == "draft"
    items[0]["options"] = ["same", "same", "x", "y"]  # edits are validated like the model's output
    r = prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": {"items": items}})
    assert r.status_code == 422


def test_discarding_a_draft(world):
    prof, url = world["prof"], world["url"]
    created, _ = _generate(world, "faq", TIER1)
    assert prof.delete(f"{url}/ai/drafts/{created['id']}").status_code == 204
    assert _draft(world, created["id"])["status"] == "discarded"
    assert prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": {"title": "a", "body": "b"}}
                      ).status_code == 409
    assert prof.post(f"{url}/ai/drafts/{created['id']}/accept", json={}).status_code == 409
    listed = prof.get(f"{url}/ai/drafts", params={"status": "discarded"}).json()
    assert [d["id"] for d in listed] == [created["id"]]
    assert prof.get(f"{url}/ai/drafts", params={"status": "draft"}).json() == []


def test_a_draft_discarded_while_generating_stays_discarded(world):
    prof, url = world["prof"], world["url"]
    world["use"](TIER1)
    created = prof.post(f"{url}/ai/drafts", json={"kind": "faq"}).json()
    assert prof.get(f"{url}/ai/drafts/{created['id']}").json()["status"] == "generating"
    assert prof.patch(f"{url}/ai/drafts/{created['id']}", json={"content": {"title": "a", "body": "b"}}
                      ).status_code == 409  # not editable before it is a draft
    assert prof.delete(f"{url}/ai/drafts/{created['id']}").status_code == 204
    jobs.run_pending(world["services"])
    assert _draft(world, created["id"])["status"] == "discarded"


def test_a_bad_model_answer_fails_the_draft_and_the_job(world):
    created, _ = _generate(world, "kcs", "this is not json")
    draft = _draft(world, created["id"])
    assert draft["status"] == "failed" and "invalid structure draft" in draft["error"]
    job = world["prof"].get(f"{world['url']}/jobs/{created['job_id']}").json()
    assert job["status"] == "failed" and job["error"].startswith("DraftError")
    # a citation to a passage that does not exist is refused too
    bad = json.dumps({"title": "T", "body": "B", "citations": [7]})
    created, _ = _generate(world, "faq", bad)
    assert _draft(world, created["id"])["status"] == "failed"


def test_no_material_and_no_kcs_fail_with_a_reason(world):
    world["services"].course_retriever = FakeCourseRetriever([])
    created, local = _generate(world, "faq", TIER1)
    draft = _draft(world, created["id"])
    assert draft["status"] == "failed" and "no indexed course material" in draft["error"]
    assert local.calls == []  # the model is not asked without material
    world["services"].course_retriever = FakeCourseRetriever([
        Chunk(text=PASSAGE, source=SOURCE, topic="x", score=1.0)])
    prof, url = world["prof"], world["url"]
    other = prof.post(f"{V2}/courses", json=_pack_course(OTHER_PACK)).json()
    world["use"](ITEMS)
    r = prof.post(f"{V2}/courses/{other['id']}/ai/drafts", json={"kind": "check_items"})
    jobs.run_pending(world["services"])
    draft = prof.get(f"{V2}/courses/{other['id']}/ai/drafts/{r.json()['id']}").json()
    assert draft["status"] == "failed" and "no KCs yet" in draft["error"]
    assert prof.post(f"{url}/ai/drafts", json={"kind": "faq", "module_id": 999999}).status_code == 422
    assert prof.post(f"{url}/ai/drafts", json={"kind": "essay"}).status_code == 422


def test_the_module_scopes_the_material(world):
    created, _ = _generate(world, "faq", TIER1, module_id=world["module"]["id"], focus="grading")
    calls = world["services"].course_retriever.calls
    assert calls[-1][:2] == (world["course_id"], world["module"]["id"]) and "grading" in calls[-1][2]
    assert _draft(world, created["id"])["module_id"] == world["module"]["id"]


# ------------------------------------------------------------------------------------ class insights
def _evidence(services, course_id, students, kc, source, misconception=None, extra=None):
    with Session(services.engine) as db:
        for student in students:
            db.add(EvidenceLog(student_id=student, course_id=course_id, kc_id=kc, kind="weak", source=source,
                               signal="misconception" if misconception else "confusion",
                               misconception_id=misconception))
        for text in extra or []:
            db.add(RequestLog(request_id=text, session_id="s", student_id="s1", course_id=course_id,
                              topic="circuits", sanitized_question=text))
        db.commit()


def test_insights_are_suppressed_for_small_groups_and_have_no_question_text(world):
    prof, url, services, course_id = world["prof"], world["url"], world["services"], world["course_id"]
    empty = prof.get(f"{url}/insights").json()
    assert empty["suppressed"] is True and empty["kc_question_counts"] == []
    four = [f"p{i}" for i in range(4)]
    _evidence(services, course_id, four, "C.1", "understand", extra=[SECRET_QUESTION])
    small = prof.get(f"{url}/insights").json()
    assert small["suppressed"] is True and small["kc_question_counts"] == []
    assert small["min_group"] == 5 and SECRET_QUESTION not in json.dumps(small)
    five = [f"p{i}" for i in range(5)]
    _evidence(services, course_id, five, "C.1", "understand", extra=[SECRET_QUESTION])
    _evidence(services, course_id, five[:5], "C.1", "check", misconception="C.MC1")
    _evidence(services, course_id, ["p0"], "C.2", "understand")  # one learner only: the label is hidden
    data = prof.get(f"{url}/insights").json()
    assert data["suppressed"] is False
    assert data["kc_question_counts"] == [{"label": "C.1", "name": "Pull-up resistors", "count": 9}]
    assert data["misconception_counts"] == [{"label": "C.MC1", "name": None, "count": 5}]
    assert SECRET_QUESTION not in json.dumps(data)


def test_insights_only_count_this_course(world):
    prof, url, services = world["prof"], world["url"], world["services"]
    other = prof.post(f"{V2}/courses", json=_pack_course(OTHER_PACK)).json()
    _evidence(services, other["id"], [f"p{i}" for i in range(6)], "C.1", "understand")
    assert prof.get(f"{url}/insights").json()["kc_question_counts"] == []
    assert len(prof.get(f"{V2}/courses/{other['id']}/insights").json()["kc_question_counts"]) == 1


# ---------------------------------------------------------------------------------------- access
def test_only_the_course_instructors_reach_drafts_and_insights(world):
    prof, url, app = world["prof"], world["url"], world["app"]
    created, _ = _generate(world, "faq", TIER1)
    draft_url = f"{url}/ai/drafts/{created['id']}"
    other_course = prof.post(f"{V2}/courses", json=_pack_course(OTHER_PACK)).json()
    calls = [("post", f"{url}/ai/drafts", {"kind": "faq"}), ("get", f"{url}/ai/drafts", None),
             ("get", draft_url, None), ("patch", draft_url, {"content": {"title": "a", "body": "b"}}),
             ("post", f"{draft_url}/accept", {}), ("delete", draft_url, None),
             ("get", f"{url}/insights", None)]
    clients = ((_login(app, "other"), 404), (_login(app, "alice"), 404), (csrf_client(app), 401))
    for client, expected in clients:
        for method, path, body in calls:
            r = getattr(client, method)(path, **({"json": body} if body is not None else {}))
            assert r.status_code == expected, (method, path, expected, r.status_code)
    # the other course's instructor (here the same account) cannot reach the draft through its own course
    assert prof.get(f"{V2}/courses/{other_course['id']}/ai/drafts/{created['id']}").status_code == 404
    assert prof.patch(f"{V2}/courses/{other_course['id']}/ai/drafts/{created['id']}",
                      json={"content": {"title": "a", "body": "b"}}).status_code == 404
    assert prof.post(f"{V2}/courses/{other_course['id']}/ai/drafts/{created['id']}/accept",
                     json={}).status_code == 404
    assert prof.delete(f"{V2}/courses/{other_course['id']}/ai/drafts/{created['id']}").status_code == 404
    assert prof.get(f"{V2}/courses/{other_course['id']}/ai/drafts").json() == []
    assert _draft(world, created["id"])["status"] == "draft"  # nothing above changed it
    assert world["cloud"].calls == []
