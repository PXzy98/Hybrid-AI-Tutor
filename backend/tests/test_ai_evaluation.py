"""Task Z12: instructor AI tier 4 (local vs cloud evaluation) and background jobs, with fake models only."""
import json

import pytest
from sqlmodel import Session

from app.core.schemas import Chunk
from app.llm.fake import FakeLLMClient
from app.llm.gateway import FakeGateway
from app.platform import jobs
from app.rag.course import FakeCourseRetriever
from app.storage.models import CourseMember, Job
from tests.conftest import PASSWORD, csrf_client

V2 = "/api/v2"
QUESTIONS = json.dumps({"questions": [
    {"question": "What does a pull-up resistor do?", "type": "concept", "reference": "It holds a line high."},
    {"question": "Pick a pull-up value for 3.3 V I2C.", "type": "application",
     "reference": "About 4.7 kOhm."},
]})


def _judge(messages) -> str:
    """Scores the cloud answer 5 and the local one 3, whichever position each was given (blind order)."""
    text = messages[-1]["content"]
    a = text.split("Answer A:\n", 1)[1].split("\n\nAnswer B:", 1)[0]
    return json.dumps({"score_a": 5 if "CLOUD" in a else 3, "score_b": 3 if "CLOUD" in a else 5,
                       "reason": "the cloud answer is complete"})


def _login(app, username):
    c = csrf_client(app)
    assert c.post(f"{V2}/auth/login", json={"username": username, "password": PASSWORD}).status_code == 200
    return c


@pytest.fixture
def world(make_client):
    with make_client() as client:
        services = client.app.state.services
        for name in ("prof", "other"):
            services.accounts.create_instructor(name, PASSWORD, must_change=False)
        alice, _ = services.accounts.create_student("alice", "Alice")
        services.accounts.set_password(alice.id, PASSWORD, must_change=False)
        prof = _login(client.app, "prof")
        body = {"code": "ELG 5902", "title": "F", "course_type": "ece"}
        course = prof.post(f"{V2}/courses", json=body).json()
        url = f"{V2}/courses/{course['id']}"
        module = prof.post(f"{url}/modules", json={"code": "circuits", "title": "Circuits"}).json()
        prof.post(f"{url}/kcs", json={"module_id": module["id"], "code": "C.1", "name": "Pull-up resistors",
                                      "difficulty": "basic"})
        with Session(services.engine) as db:
            db.add(CourseMember(course_id=course["id"], account_id=alice.id, role="student", status="active"))
            db.commit()
        note = Chunk(text="A pull-up resistor holds a line high.", source="notes.md", topic="circuits",
                     score=1.0)
        services.course_retriever = FakeCourseRetriever([note])
        local = FakeLLMClient([QUESTIONS, "LOCAL answer about pull-ups."], model="local-9b")
        cloud = FakeLLMClient("CLOUD answer about pull-ups.", model="cloud-x", backend="cloud")
        judge = FakeLLMClient(_judge, model="judge-y", backend="cloud")
        services.gateway = FakeGateway({"local": local, "cloud": cloud, "judge": judge})
        yield {"app": client.app, "services": services, "prof": prof, "url": url, "module": module,
               "local": local, "cloud": cloud, "judge": judge}


def test_generate_review_run_and_spot_check(world):
    prof, url, services = world["prof"], world["url"], world["services"]
    r = prof.post(f"{url}/ai/evaluations", json={"questions_per_module": 2})
    assert r.status_code == 202 and r.json()["status"] == "generating"
    evaluation_id, job_id = r.json()["id"], r.json()["job_id"]
    assert prof.get(f"{url}/jobs/{job_id}").json()["status"] == "queued"
    assert jobs.run_pending(services) == 1
    job = prof.get(f"{url}/jobs/{job_id}").json()
    assert (job["status"], job["progress"]) == ("done", 100)
    ev = prof.get(f"{url}/ai/evaluations/{evaluation_id}").json()
    assert ev["status"] == "review" and [q["type"] for q in ev["questions"]] == ["concept", "application"]
    # the material stayed local: only the local model wrote the questions
    assert len(world["local"].calls) == 1 and world["cloud"].calls == [] and world["judge"].calls == []
    assert "pull-up resistor holds a line high" in world["local"].sent_text()

    edited = [{"module_id": world["module"]["id"], "type": "concept",
               "question": ev["questions"][0]["question"], "reference": "It holds a line high."}]
    questions_url = f"{url}/ai/evaluations/{evaluation_id}/questions"
    assert prof.put(questions_url, json={"questions": edited}).status_code == 200
    assert prof.post(f"{url}/ai/evaluations/{evaluation_id}/run", json={}).status_code == 422  # no consent
    r = prof.post(f"{url}/ai/evaluations/{evaluation_id}/run", json={"confirm_cloud": True})
    assert r.status_code == 202 and r.json()["status"] == "running"
    assert prof.put(questions_url, json={"questions": edited}).status_code == 409  # no edits while running
    jobs.run_pending(services)
    ev = prof.get(f"{url}/ai/evaluations/{evaluation_id}").json()
    assert ev["status"] == "done" and len(ev["results"]) == 1
    result = ev["results"][0]
    assert (result["local"]["score"], result["cloud"]["score"]) == (3, 5)  # mapped back from the blind order
    assert result["judge_model"] == "judge-y" and result["local"]["model"] == "local-9b"
    overall = ev["report"]["overall"]
    assert (overall["local_score"], overall["cloud_score"], overall["cloud_better"]) == (3, 5, 1)
    assert ev["report"]["by_module"]["Circuits"]["questions"] == 1 and "concept" in ev["report"]["by_type"]
    r = prof.patch(f"{url}/ai/evaluations/{evaluation_id}/results/1", json={"agrees_with_judge": True})
    assert r.status_code == 200 and r.json()["report"]["spot_checks"] == 1
    assert prof.patch(f"{url}/ai/evaluations/{evaluation_id}/results/99",
                      json={"agrees_with_judge": True}).status_code == 404
    listed = prof.get(f"{url}/ai/evaluations").json()
    assert [(e["id"], e["status"], e["questions"]) for e in listed] == [(evaluation_id, "done", 1)]


def test_a_local_only_course_cannot_send_material_to_the_cloud(world):
    prof, url, services = world["prof"], world["url"], world["services"]
    evaluation_id = prof.post(f"{url}/ai/evaluations", json={}).json()["id"]
    jobs.run_pending(services)
    prof.put(f"{url}/settings", json={"values": {"local_only": True}, "version": 0})
    r = prof.post(f"{url}/ai/evaluations/{evaluation_id}/run", json={"confirm_cloud": True})
    assert r.status_code == 409 and "local model only" in r.json()["detail"]
    assert world["cloud"].calls == [] and world["judge"].calls == []


def test_a_failing_model_marks_the_evaluation_and_the_job_failed(world):
    prof, url, services = world["prof"], world["url"], world["services"]
    evaluation_id = prof.post(f"{url}/ai/evaluations", json={}).json()["id"]
    jobs.run_pending(services)
    del services.gateway.clients["cloud"]  # no cloud connection configured
    run = prof.post(f"{url}/ai/evaluations/{evaluation_id}/run", json={"confirm_cloud": True})
    job_id = run.json()["job_id"]
    jobs.run_pending(services)
    ev = prof.get(f"{url}/ai/evaluations/{evaluation_id}").json()
    assert ev["status"] == "failed" and "no model connection" in ev["error"]
    job = prof.get(f"{url}/jobs/{job_id}").json()
    assert job["status"] == "failed" and job["error"].startswith("LLMUnavailable")


def test_no_material_means_no_questions(world):
    world["services"].course_retriever = FakeCourseRetriever([])
    prof, url = world["prof"], world["url"]
    evaluation_id = prof.post(f"{url}/ai/evaluations", json={}).json()["id"]
    jobs.run_pending(world["services"])
    ev = prof.get(f"{url}/ai/evaluations/{evaluation_id}").json()
    assert ev["status"] == "failed" and "no module has indexed material" in ev["error"]


def test_only_the_course_instructors_reach_evaluations_and_jobs(world):
    prof, url, app = world["prof"], world["url"], world["app"]
    created = prof.post(f"{url}/ai/evaluations", json={}).json()
    evaluation_id, job_id = created["id"], created["job_id"]
    other_course = prof.post(f"{V2}/courses", json={"code": "ELG 1", "title": "O",
                                                    "course_type": "ece"}).json()
    for who in ("other", "alice"):
        c = _login(app, who)
        assert c.get(f"{url}/ai/evaluations").status_code == 404
        assert c.get(f"{url}/ai/evaluations/{evaluation_id}").status_code == 404
        assert c.post(f"{url}/ai/evaluations", json={}).status_code == 404
        run_url = f"{url}/ai/evaluations/{evaluation_id}/run"
        assert c.post(run_url, json={"confirm_cloud": True}).status_code == 404
        assert c.get(f"{url}/jobs/{job_id}").status_code == 404
    assert prof.get(f"{V2}/courses/{other_course['id']}/ai/evaluations/{evaluation_id}").status_code == 404
    assert prof.get(f"{V2}/courses/{other_course['id']}/jobs/{job_id}").status_code == 404
    bad = prof.post(f"{url}/ai/evaluations", json={"module_ids": [999999]})
    assert bad.status_code == 422


def test_unknown_job_kinds_fail_and_stale_jobs_are_failed(world):
    services = world["services"]
    job = jobs.enqueue(services.engine, "no.such.kind")
    jobs.run_pending(services)
    with Session(services.engine) as db:
        row = db.get(Job, job.id)
        assert row.status == "failed" and "no handler" in row.error
        stale = Job(kind="x", status="running", started_at=row.created_at - jobs.STALE_AFTER * 2)
        db.add(stale)
        db.commit()
        stale_id = stale.id
    assert jobs.fail_stale(services.engine) >= 1
    with Session(services.engine) as db:
        assert db.get(Job, stale_id).status == "failed"


def test_the_app_reads_the_course_index_from_data_dir(make_client, tmp_path, monkeypatch):
    """Production wiring (review of #53): a course with a published index gets questions from it."""
    from app.rag.course_retriever import IndexedCourseRetriever

    monkeypatch.setenv("DATA_DIR", str(tmp_path))
    with make_client() as client:
        services = client.app.state.services
        assert isinstance(services.course_retriever, IndexedCourseRetriever)
        assert services.course_retriever.data_root == tmp_path
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        prof = _login(client.app, "prof")
        body = {"code": "ELG 5902", "title": "F", "course_type": "ece"}
        course_id = prof.post(f"{V2}/courses", json=body).json()["id"]
        url = f"{V2}/courses/{course_id}"
        module = prof.post(f"{url}/modules", json={"code": "circuits", "title": "Circuits"}).json()
        prof.post(f"{url}/kcs", json={"module_id": module["id"], "code": "C.1", "name": "Pull-up resistors",
                                      "definition": "What holds a signal line high.", "difficulty": "basic"})
        folder = tmp_path / "courses" / str(course_id) / "materials" / "_course"
        folder.mkdir(parents=True)
        note = "A pull-up resistor holds a signal line high when nothing drives it."
        (folder / "notes.md").write_text(note, encoding="utf-8")
        IndexedCourseRetriever(tmp_path, scan=lambda text: True).rebuild(course_id)  # the worker's job (S4)
        services.gateway = FakeGateway({"local": FakeLLMClient(QUESTIONS)})
        evaluation_id = prof.post(f"{url}/ai/evaluations", json={"module_ids": [module["id"]]}).json()["id"]
        jobs.run_pending(services)
        ev = prof.get(f"{url}/ai/evaluations/{evaluation_id}").json()
        assert ev["status"] == "review", ev["error"]
        assert len(ev["questions"]) == 2
        assert "pull-up resistor holds a signal line high" in services.gateway.clients["local"].sent_text()


def test_two_runs_at_the_same_moment_start_one_job(world):
    import threading

    prof, url, services, app = world["prof"], world["url"], world["services"], world["app"]
    evaluation_id = prof.post(f"{url}/ai/evaluations", json={}).json()["id"]
    jobs.run_pending(services)
    clients = [_login(app, "prof") for _ in range(4)]
    start, codes = threading.Barrier(len(clients)), []

    def run(c):
        start.wait()
        r = c.post(f"{url}/ai/evaluations/{evaluation_id}/run", json={"confirm_cloud": True})
        codes.append(r.status_code)

    threads = [threading.Thread(target=run, args=(c,)) for c in clients]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert sorted(codes) == [202, 409, 409, 409]
    with Session(services.engine) as db:
        from sqlmodel import select

        runs = db.exec(select(Job).where(Job.kind == "ai_evaluation.run", Job.ref_id == evaluation_id)).all()
    assert len(runs) == 1


def test_the_worker_fails_a_job_that_becomes_stale_while_it_runs(use_config, tmp_path, monkeypatch):
    """Review of #53: stale jobs are checked every round, not only at start."""
    import threading
    import time

    from app import worker
    from app.core.config import get_settings
    from app.storage.db import make_engine

    monkeypatch.setattr(worker, "HEARTBEAT", tmp_path / "alive")
    use_config({"limits": {"settings": {"poll_seconds": 0.2}}})
    stop, seen = threading.Event(), {}

    def watch():
        for _ in range(1200):  # building the services takes a while
            if (tmp_path / "alive").exists():
                break
            time.sleep(0.1)
        engine = make_engine(get_settings().database_url, pooled=False)
        with Session(engine) as db:  # a job left running by a worker that stopped long ago
            job = Job(kind="x", status="running", started_at=Job().created_at - jobs.STALE_AFTER * 2)
            db.add(job)
            db.commit()
            job_id = job.id
        for _ in range(100):
            with Session(engine) as db:
                if db.get(Job, job_id).status == "failed":
                    seen["failed"] = True
                    break
            time.sleep(0.1)
        engine.dispose()
        stop.set()

    threading.Thread(target=watch).start()
    worker.run(stop)
    assert seen.get("failed") is True
