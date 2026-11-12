"""Quizzes and the end-of-term survey (api-v2.md 3.9, 3.10; course-structure.md 4.6, 4.7). Fictional data;
the models are fakes."""
import json
from datetime import timedelta

import pytest

from app.core.schemas import Chunk
from app.llm.fake import FakeLLMClient
from app.llm.gateway import FakeGateway
from app.platform import jobs
from app.rag.course import FakeCourseRetriever
from app.storage.models import utcnow
from tests.conftest import PASSWORD, csrf_client
from tests.test_ask_v2 import World, _login, rows
from tests.test_learner_v2 import set_mode

MCQ = {"kind": "mcq", "kc": "C.1", "stem": "What does Ohm's law relate?",
       "options": ["Voltage, current and resistance", "Mass and energy", "Heat and work"], "answer": 0,
       "explanation": "V = I R."}
TF = {"kind": "true_false", "kc": None, "stem": "A resistor stores charge.", "answer": 1,
      "explanation": "A capacitor stores charge."}


@pytest.fixture
def world(make_client):
    with make_client({"learner": {"class_summary_min_group": 2}}) as client:
        w = World(client)
        w.enrol("bob")
        for name in ("alice", "bob"):
            w.consent(name)
        w.sid = {n: w.students[n].student_id for n in ("alice", "bob")}
        yield w


def _quiz(world, **extra) -> dict:
    body = {"title": "Week 1 check", "module_id": world.module, "questions": [MCQ, TF], **extra}
    r = world.prof.post(f"{world.url}/quizzes", json=body)
    assert r.status_code == 201, r.text
    return r.json()


def _publish(world, quiz_id: int) -> None:
    r = world.prof.patch(f"{world.url}/quizzes/{quiz_id}", json={"status": "published"})
    assert r.status_code == 200, r.text


def test_students_answer_a_published_quiz_once_without_seeing_the_answers(world):
    quiz = _quiz(world)
    assert quiz["status"] == "draft" and quiz["questions"][1]["options"] == ["True", "False"]
    alice = _login(world.app, "alice")
    assert alice.get(f"{world.url}/quizzes").json() == []  # a draft is not shown
    assert alice.get(f"{world.url}/quizzes/{quiz['id']}").status_code == 404
    _publish(world, quiz["id"])
    listed = alice.get(f"{world.url}/quizzes").json()
    assert [q["id"] for q in listed] == [quiz["id"]] and listed[0]["open"]
    assert "answer" not in json.dumps(listed[0]["questions"]) and "explanation" not in json.dumps(listed)
    r = alice.post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [0, 0]})
    assert r.status_code == 201, r.text
    body = r.json()
    assert (body["score"], body["total"]) == (1, 2)
    assert [x["correct"] for x in body["results"]] == [True, False] and body["results"][1]["answer"] == 1
    again = alice.post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [0, 1]})
    assert again.status_code == 409
    after = alice.get(f"{world.url}/quizzes/{quiz['id']}").json()
    assert after["attempt"]["score"] == 1
    assert after["questions"][0]["stem"] == MCQ["stem"]  # shown again, to read the result
    # with consent the answer to the KC-linked question is evidence for the knowledge model
    quiz_evidence = [e for e in rows("evidence_log") if e["source"] == "quiz"]
    found = [(e["kc_id"], e["correct"], e["course_id"]) for e in quiz_evidence]
    assert found == [("C.1", True, world.course)]
    # the questions cannot change once students have answered
    r = world.prof.patch(f"{world.url}/quizzes/{quiz['id']}", json={"questions": [MCQ]})
    assert r.status_code == 409
    assert world.prof.delete(f"{world.url}/quizzes/{quiz['id']}").status_code == 409


def test_windows_assignments_and_validation(world):
    soon = (utcnow() + timedelta(days=1)).isoformat()
    later = _quiz(world, opens_at=soon)
    _publish(world, later["id"])
    only_bob = _quiz(world, assigned_to=[world.sid["bob"]])
    _publish(world, only_bob["id"])
    alice = _login(world.app, "alice")
    listed = {q["id"]: q for q in alice.get(f"{world.url}/quizzes").json()}
    assert set(listed) == {later["id"]} and listed[later["id"]]["open"] is False
    assert listed[later["id"]]["questions"] == []
    early = alice.post(f"{world.url}/quizzes/{later['id']}/attempt", json={"answers": [0, 1]})
    assert early.status_code == 409
    assert alice.post(f"{world.url}/quizzes/{only_bob['id']}/attempt",
                      json={"answers": [0, 1]}).status_code == 404
    bob = _login(world.app, "bob")
    assert bob.post(f"{world.url}/quizzes/{only_bob['id']}/attempt", json={"answers": [0]}).status_code == 422
    bad = {"title": "x", "questions": [{**MCQ, "kc": "HBP.1"}]}  # another course's KC
    assert world.prof.post(f"{world.url}/quizzes", json=bad).status_code == 422
    bad = {"title": "x", "questions": [{**MCQ, "answer": 5}]}
    assert world.prof.post(f"{world.url}/quizzes", json=bad).status_code == 422
    empty = world.prof.post(f"{world.url}/quizzes", json={"title": "empty"}).json()
    r = world.prof.patch(f"{world.url}/quizzes/{empty['id']}", json={"status": "published"})
    assert r.status_code == 409
    assert world.prof.delete(f"{world.url}/quizzes/{empty['id']}").status_code == 204


def test_ai_drafts_come_from_the_local_model_and_need_review(world):
    services = world.services
    reply = json.dumps({"questions": [
        {"kind": "mcq", "kc": "C.1", "stem": "Ohm's law says V equals what?", "options": ["I R", "I / R",
         "R / I", "I + R"], "answer": 0, "explanation": "From the notes.", "passage": 1},
        {"kind": "true_false", "kc": "nope", "stem": "Current is measured in amperes.", "answer": 0,
         "explanation": "The notes say so.", "passage": 1},
        {"kind": "mcq", "stem": "broken", "options": ["a"], "answer": 3},  # invalid: dropped
    ]})
    local = FakeLLMClient(reply, model="local-9b")
    cloud = FakeLLMClient("never", model="cloud-x", backend="cloud")
    services.gateway = FakeGateway({"local": local, "cloud": cloud})
    services.course_retriever = FakeCourseRetriever([Chunk(text="Ohm's law: V = I R. Current in amperes.",
                                                           source="notes.md", topic="circuits", score=1.0)])
    body = {"title": "AI quiz", "module_id": world.module}
    quiz = world.prof.post(f"{world.url}/quizzes", json=body).json()
    r = world.prof.post(f"{world.url}/quizzes/{quiz['id']}/drafts", json={"count": 5})
    assert r.status_code == 202
    assert jobs.run_pending(services) == 1
    assert world.prof.get(f"{world.url}/jobs/{r.json()['job_id']}").json()["status"] == "done"
    drafted = world.prof.get(f"{world.url}/quizzes/{quiz['id']}").json()["questions"]
    assert [(q["kind"], q["kc"], q["reviewed"], q["sources"]) for q in drafted] == [
        ("mcq", "C.1", False, ["notes.md"]), ("true_false", None, False, ["notes.md"])]
    assert len(local.calls) == 1 and cloud.calls == []  # course material stayed local
    assert "Ohm's law: V = I R" in local.sent_text()
    r = world.prof.patch(f"{world.url}/quizzes/{quiz['id']}", json={"status": "published"})
    assert r.status_code == 409 and "review" in r.json()["detail"]
    world.prof.patch(f"{world.url}/quizzes/{quiz['id']}", json={"questions": drafted})  # saved = reviewed
    _publish(world, quiz["id"])
    assert world.prof.post(f"{world.url}/quizzes/{quiz['id']}/drafts", json={}).status_code == 409


def test_results_show_individuals_only_when_visible(world):
    quiz = _quiz(world, kind="final")
    _publish(world, quiz["id"])
    alice, bob = _login(world.app, "alice"), _login(world.app, "bob")
    url = f"{world.url}/quizzes/{quiz['id']}"
    alice.post(f"{url}/attempt", json={"answers": [0, 1]})
    res = world.prof.get(f"{url}/results").json()
    assert res["attempts"] == 1 and res["sufficient_sample"] is False and res["mean_score"] is None
    assert res["questions"] == [] and res["students"] == []  # mode A: no individual results
    bob.post(f"{url}/attempt", json={"answers": [1, 1]})
    res = world.prof.get(f"{url}/results").json()
    assert res["sufficient_sample"] and res["mean_score"] == 0.75
    assert [q["correct_rate"] for q in res["questions"]] == [0.5, 1.0]
    assert res["students"] == []
    set_mode(world, "B")
    bob.post(f"{world.url}/me/visibility", json={"action": "acknowledge"})
    res = world.prof.get(f"{url}/results").json()
    assert res["students"] == []  # bob answered before he became visible
    later = _quiz(world)
    _publish(world, later["id"])
    bob.post(f"{world.url}/quizzes/{later['id']}/attempt", json={"answers": [0, 1]})
    alice.post(f"{world.url}/quizzes/{later['id']}/attempt", json={"answers": [1, 0]})
    res = world.prof.get(f"{world.url}/quizzes/{later['id']}/results").json()
    assert [(s["student_id"], s["score"]) for s in res["students"]] == [(world.sid["bob"], 2)]
    views = [a for a in rows("audit_log") if a["action"] == "learner.quiz_results.view"]
    assert views and all(v["details"]["student_id"] == world.sid["bob"] for v in views)


def test_a_final_quiz_is_compared_with_the_diagnostic(world):
    for name, choice in (("alice", "B"), ("bob", "B")):  # both get the diagnostic wrong
        c = _login(world.app, name)
        c.post(f"{world.url}/onboarding", json={"module_id": world.module,
                                                "answers": [{"item_id": "C.1-q1", "choice": choice}]})
    quiz = _quiz(world, kind="final")
    _publish(world, quiz["id"])
    for name in ("alice", "bob"):
        _login(world.app, name).post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [0, 1]})
    res = world.prof.get(f"{world.url}/quizzes/{quiz['id']}/results").json()
    assert res["pre_post"] == {"students": 2, "pre_mean": 0.0, "post_mean": 1.0}


def test_other_people_cannot_use_the_quiz_endpoints(world):
    quiz = _quiz(world)
    _publish(world, quiz["id"])
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    carol, _ = world.services.accounts.create_student("carol", "Carol")
    world.services.accounts.set_password(carol.id, PASSWORD, must_change=False)
    other, outsider = _login(world.app, "other"), _login(world.app, "carol")
    anonymous = csrf_client(world.app)
    alice = _login(world.app, "alice")
    url = f"{world.url}/quizzes"
    one = f"{url}/{quiz['id']}"
    for client, code in ((other, 404), (outsider, 404), (anonymous, 401)):
        assert client.get(url).status_code == code
        assert client.post(url, json={"title": "x"}).status_code == code
        assert client.get(one).status_code == code
        assert client.patch(one, json={"title": "x"}).status_code == code
        assert client.delete(one).status_code == code
        assert client.post(f"{one}/drafts", json={}).status_code == code
        assert client.post(f"{one}/attempt", json={"answers": [0, 1]}).status_code == code
        assert client.get(f"{one}/results").status_code == code
    # a student of the course cannot use the instructor endpoints
    assert alice.post(url, json={"title": "x"}).status_code == 404
    assert alice.patch(one, json={"title": "x"}).status_code == 404
    assert alice.get(f"{one}/results").status_code == 404
    assert alice.post(f"{one}/drafts", json={}).status_code == 404
    assert world.prof.post(f"{one}/attempt", json={"answers": [0, 1]}).status_code == 404
    assert rows("quiz_attempt") == []


# ---------------------------------------------------------------------------------- end-of-term survey
ANSWERS = {"helpfulness": 4, "material_relevance": 5, "clarity": 3, "source_confidence": 4,
           "learning_effect": 2}


def test_the_survey_is_answered_once_inside_its_window_and_stays_anonymous(world):
    carol, _ = world.services.accounts.create_student("carol", "Carol")
    world.students["carol"] = world.services.accounts.set_password(carol.id, PASSWORD, must_change=False)
    world.enrol("carol")
    alice = _login(world.app, "alice")
    assert alice.get(f"{world.url}/survey").json()["open"] is False
    assert alice.post(f"{world.url}/survey/responses", json=ANSWERS).status_code == 409  # not open
    start, end = utcnow() - timedelta(hours=1), utcnow() + timedelta(days=7)
    window = {"opens_at": start.isoformat(), "closes_at": end.isoformat()}
    backwards = {**window, "closes_at": start.isoformat()}
    assert world.prof.put(f"{world.url}/survey", json=backwards).status_code == 422
    assert world.prof.put(f"{world.url}/survey", json=window).json()["open"] is True
    assert alice.post(f"{world.url}/survey/responses", json=ANSWERS).json()["answered"] is True
    assert alice.post(f"{world.url}/survey/responses", json=ANSWERS).status_code == 409  # once
    assert alice.post(f"{world.url}/survey/responses", json={**ANSWERS, "comment": "hi"}).status_code == 422
    results = world.prof.get(f"{world.url}/survey").json()["results"]
    assert results["responses"] == 1 and results["means"] is None  # below the minimum group
    for name in ("bob", "carol"):
        assert _login(world.app, name).post(f"{world.url}/survey/responses", json=ANSWERS).status_code == 201
    results = world.prof.get(f"{world.url}/survey").json()["results"]
    assert results["sufficient_sample"] and results["means"]["learning_effect"] == 2.0
    assert all("student_id" not in r and "created_at" not in r for r in rows("course_survey_response"))
    assert alice.get(f"{world.url}/survey").json()["results"] is None  # students see no results


def test_other_people_cannot_use_the_survey(world):
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    other, anonymous = _login(world.app, "other"), csrf_client(world.app)
    window = {"opens_at": (utcnow() - timedelta(hours=1)).isoformat(),
              "closes_at": (utcnow() + timedelta(days=1)).isoformat()}
    world.prof.put(f"{world.url}/survey", json=window)
    for client, code in ((other, 404), (anonymous, 401)):
        assert client.get(f"{world.url}/survey").status_code == code
        assert client.put(f"{world.url}/survey", json=window).status_code == code
        assert client.post(f"{world.url}/survey/responses", json=ANSWERS).status_code == code
    assert _login(world.app, "alice").put(f"{world.url}/survey", json=window).status_code == 404
    assert world.prof.post(f"{world.url}/survey/responses", json=ANSWERS).status_code == 404
    assert rows("course_survey_response") == []


def test_end_of_term_exports_and_deletes_quiz_and_survey_data(world, tmp_path):
    world.services.settings.data_dir = str(tmp_path)
    quiz = _quiz(world)
    _publish(world, quiz["id"])
    window = {"opens_at": (utcnow() - timedelta(hours=1)).isoformat(),
              "closes_at": (utcnow() + timedelta(days=1)).isoformat()}
    world.prof.put(f"{world.url}/survey", json=window)
    for name in ("alice", "bob"):
        c = _login(world.app, name)
        c.post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [0, 1]})
        c.post(f"{world.url}/survey/responses", json=ANSWERS)
    done = world.prof.post(f"{world.url}/end-term", json={"confirm": True}).json()
    assert done["deleted"]["quiz_attempt"] == 2 and done["deleted"]["course_survey_response"] == 2
    for table in ("quiz_attempt", "course_survey_response", "course_survey_submission", "survey_window"):
        assert rows(table) == [], table
    kept = world.prof.get(f"{world.url}/quizzes/{quiz['id']}").json()
    assert kept["status"] == "closed" and len(kept["questions"]) == 2  # course content stays
    import io
    import zipfile

    r = world.prof.get(f"{world.url}/exports/{done['export_id']}")
    with zipfile.ZipFile(io.BytesIO(r.content)) as z:
        quizzes = json.loads(z.read("quizzes.json"))
        survey = json.loads(z.read("survey.json"))
    assert quizzes[0]["attempts"] == 2 and quizzes[0]["mean_score"] == 1.0 and quizzes[0]["students"] == []
    assert survey["responses"] == 2


def test_a_student_deleting_their_data_removes_their_attempts(world):
    quiz = _quiz(world)
    _publish(world, quiz["id"])
    alice = _login(world.app, "alice")
    alice.post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [0, 1]})
    _login(world.app, "bob").post(f"{world.url}/quizzes/{quiz['id']}/attempt", json={"answers": [0, 1]})
    assert alice.delete(f"{world.url}/me/learning-data").status_code == 204
    assert [a["student_id"] for a in rows("quiz_attempt")] == [world.sid["bob"]]
