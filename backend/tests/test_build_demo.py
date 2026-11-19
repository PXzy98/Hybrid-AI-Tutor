"""scripts/build_demo.py (task T9) against the app in-process: courses, modules, uploads, students, mode B and
the sample activity, all through API v2. One small open course pack (CS50x); models are fakes."""
import importlib.util
import json
import sys
import zipfile
from pathlib import Path

import pytest

from app.llm.fake import FakeLLMClient
from app.platform import jobs
from tests.conftest import PASSWORD, UNDERSTOOD_NOTHING, csrf_client

ROOT = Path(__file__).resolve().parents[2]
PACK = "harvard_cs50x"
spec = importlib.util.spec_from_file_location("build_demo", ROOT / "scripts" / "build_demo.py")
build_demo = importlib.util.module_from_spec(spec)
sys.modules["build_demo"] = build_demo
spec.loader.exec_module(build_demo)


@pytest.fixture
def packs_dir(tmp_path):
    out = tmp_path / "packs"
    with zipfile.ZipFile(ROOT / "data" / "demo_courses" / "archives" / f"{PACK}.zip") as z:
        z.extractall(out)
    return out


@pytest.fixture
def world(make_client, tmp_path):
    with make_client({"data_dir": str(tmp_path / "data")}) as client:
        services = client.app.state.services
        services.local_llm = FakeLLMClient("Fake local answer.", model="fake-local")
        services.understand_llm = FakeLLMClient(UNDERSTOOD_NOTHING, model="fake-understand")
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        yield client.app, services


def run(world, packs_dir, tmp_path, **kwargs):
    app, services = world
    return build_demo.build_demo(
        lambda: csrf_client(app), [PACK], ("prof", PASSWORD), packs_dir=packs_dir,
        accounts_path=tmp_path / "var" / "demo_accounts.json",
        sleep=lambda _seconds: jobs.run_pending(services), log=lambda _line: None, **kwargs)


def test_build_demo_twice_and_sample_activity(world, packs_dir, tmp_path):
    app, services = world
    manifest = json.loads((packs_dir / PACK / "manifest.json").read_text(encoding="utf-8"))
    files = len(manifest["modules"]) + len(manifest["documents"])

    first = run(world, packs_dir, tmp_path, students=2, sample=True)[0]
    assert first.created and first.modules == len(manifest["modules"])
    assert first.uploaded + len(first.refused) == files and first.uploaded > files // 2
    assert all(name.startswith("assignments_pset_") for name in (r.split(":")[0] for r in first.refused))
    assert first.index_version == 1 and first.failed == []

    prof = csrf_client(app)
    assert prof.post("/api/v2/auth/login", json={"username": "prof", "password": PASSWORD}).status_code == 200
    course = f"/api/v2/courses/{first.course_id}"
    assert prof.get(course).json()["visibility_mode"] == "B"
    assert len(prof.get(f"{course}/modules").json()) == first.modules
    members = [m for m in prof.get(f"{course}/members").json() if m["role"] == "student"]
    assert sorted(m["display_name"] for m in members) == ["Demo Student 1", "Demo Student 2"]
    assert all(m["status"] == "active" for m in members)

    # the accounts file holds generated passwords; the run printed none of them (log is silent here)
    accounts = json.loads((tmp_path / "var" / "demo_accounts.json").read_text(encoding="utf-8"))["students"]
    assert len(accounts) == 2 and all(len(a["password"]) >= 12 for a in accounts)

    # students acknowledged mode B and asked two questions each
    student = next(m for m in members if m["display_name"] == "Demo Student 1")
    assert prof.get(f"{course}/students/{student['student_id']}/overview").status_code == 200
    alice = csrf_client(app)
    login = {"username": accounts[0]["email"], "password": accounts[0]["password"]}
    assert alice.post("/api/v2/auth/login", json=login).status_code == 200
    assert len(alice.get(f"{course}/conversations").json()) == 2

    # a second run changes nothing: same course, nothing uploaded twice, same accounts
    second = run(world, packs_dir, tmp_path, students=2)[0]
    assert not second.created and second.course_id == first.course_id
    assert second.uploaded == 0 and second.existing == first.uploaded
    assert second.index_version == 1
    kept = json.loads((tmp_path / "var" / "demo_accounts.json").read_text(encoding="utf-8"))["students"]
    assert kept == accounts


class SchemaFake(FakeLLMClient):
    """The local model of the drafts: answers by the JSON schema it is asked for (S15)."""

    REPLIES = {
        "incorrect_belief": {"items": [{"name": "Arrays grow by themselves", "incorrect_belief":
                                        "A C array grows when you write past its end.", "correction":
                                        "Its size is fixed; writing past the end is undefined behaviour.",
                                        "kc_name": "Arrays", "citations": [1]}]},
        "correct_index": {"items": [{"question": "What does an array index start at in C?",
                                     "options": ["0", "1", "-1", "Any number"], "correct_index": 0,
                                     "explanation": "C arrays are zero-indexed.", "kc_names": ["Arrays"],
                                     "citations": [1]}]},
        "definition": {"items": [{"name": "Arrays", "definition": "Values of one type stored back to back.",
                                  "prerequisite_names": [], "citations": [1]}]},
        "questions": {"questions": [{"kind": "true_false", "kc": None, "stem": "C arrays start at index 0.",
                                     "answer": 0, "explanation": "They are zero-indexed.", "passage": 1}]},
    }

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        schema = json.dumps(json_schema or {})  # quiz questions are asked for without a schema
        key = next((k for k in self.REPLIES if f'"{k}"' in schema), "questions")
        self.replies = [json.dumps(self.REPLIES[key])]
        return await super().complete(messages, json_schema=json_schema, max_tokens=max_tokens)


def test_learner_content_gives_the_course_kcs_items_and_a_published_quiz(world, packs_dir, tmp_path):
    """S15: --learner-content drafts and accepts the learner content and publishes one practice quiz; run
    again, nothing is drafted twice."""
    from app.core.schemas import Chunk
    from app.llm.gateway import FakeGateway
    from app.rag.course import FakeCourseRetriever

    app, services = world
    local = SchemaFake(model="local-9b")
    services.gateway = FakeGateway({"local": local, "cloud": FakeLLMClient("never", backend="cloud")})
    passage = Chunk(text="Arrays store values of one type back to back.", source="week_2.md", topic="week_2",
                    score=1.0)
    services.course_retriever = FakeCourseRetriever([passage])
    report = run(world, packs_dir, tmp_path, students=0, learner_content=True, learner_modules=1)[0]
    assert report.failed == [], report.failed
    assert report.accepted == {"kcs": 1, "check_items": 1, "misconceptions": 1} and report.quiz_id
    prof = csrf_client(app)
    prof.post("/api/v2/auth/login", json={"username": "prof", "password": PASSWORD})
    course = f"/api/v2/courses/{report.course_id}"
    assert [k["name"] for k in prof.get(f"{course}/kcs").json()] == ["Arrays"]
    quiz = prof.get(f"{course}/quizzes/{report.quiz_id}").json()
    assert quiz["status"] == "published" and all(q["reviewed"] for q in quiz["questions"])
    calls = len(local.calls)
    again = run(world, packs_dir, tmp_path, students=0, learner_content=True, learner_modules=1)[0]
    assert again.accepted == {} and again.quiz_id == report.quiz_id and len(local.calls) == calls


class FailingFake(SchemaFake):
    """Misconceptions and quiz questions fail (a temporary model failure)."""

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        schema = json.dumps(json_schema or {})
        if '"incorrect_belief"' in schema or json_schema is None:
            self.replies = ["not json"]
            return await FakeLLMClient.complete(self, messages, json_schema=json_schema,
                                                max_tokens=max_tokens)
        return await super().complete(messages, json_schema=json_schema, max_tokens=max_tokens)


def test_learner_content_run_again_finishes_what_failed(world, packs_dir, tmp_path):
    """S15: a kind that failed is drafted on the next run without drafting the accepted KCs again, and a
    practice quiz left as a draft is filled and published."""
    from app.core.schemas import Chunk
    from app.llm.gateway import FakeGateway
    from app.rag.course import FakeCourseRetriever

    app, services = world
    passage = Chunk(text="Arrays store values of one type back to back.", source="week_2.md", topic="week_2",
                    score=1.0)
    services.course_retriever = FakeCourseRetriever([passage])
    cloud = FakeLLMClient("never", backend="cloud")
    services.gateway = FakeGateway({"local": FailingFake(model="local-9b"), "cloud": cloud})
    first = run(world, packs_dir, tmp_path, students=0, learner_content=True, learner_modules=1)[0]
    assert first.accepted == {"kcs": 1, "check_items": 1}
    assert any("misconceptions" in f for f in first.failed)
    assert any("practice quiz" in f for f in first.failed)
    assert first.quiz_id is None

    services.gateway = FakeGateway({"local": SchemaFake(model="local-9b"), "cloud": cloud})
    again = run(world, packs_dir, tmp_path, students=0, learner_content=True, learner_modules=1)[0]
    assert again.failed == [], again.failed
    assert again.accepted == {"misconceptions": 1} and again.quiz_id
    prof = csrf_client(app)
    prof.post("/api/v2/auth/login", json={"username": "prof", "password": PASSWORD})
    course = f"/api/v2/courses/{again.course_id}"
    quizzes = prof.get(f"{course}/quizzes").json()
    assert len(quizzes) == 1 and quizzes[0]["status"] == "published"


def test_build_demo_keeps_statistics_only_courses_in_mode_a(make_client, packs_dir, tmp_path):
    """v5 V1: where individual views are off, the demo build leaves mode A and the sample activity still
    runs without problems."""
    off = {"data_dir": str(tmp_path / "data"), "learner": {"instructor_individual_view": False}}
    with make_client(off) as client:
        services = client.app.state.services
        services.local_llm = FakeLLMClient("Fake local answer.", model="fake-local")
        services.understand_llm = FakeLLMClient(UNDERSTOOD_NOTHING, model="fake-understand")
        services.accounts.create_instructor("prof", PASSWORD, must_change=False)
        report = run((client.app, services), packs_dir, tmp_path, students=1, sample=True)[0]
        assert report.failed == []
        prof = csrf_client(client.app)
        prof.post("/api/v2/auth/login", json={"username": "prof", "password": PASSWORD})
        assert prof.get(f"/api/v2/courses/{report.course_id}").json()["visibility_mode"] == "A"


def test_instructor_only_files_are_never_uploaded(tmp_path):
    pack = tmp_path / "p"
    (pack / "instructor_only").mkdir(parents=True)
    (pack / "instructor_only" / "key.md").write_text("answers", encoding="utf-8")
    (pack / "ok.md").write_text("notes", encoding="utf-8")
    assert build_demo.safe_path(pack, "instructor_only/key.md") is None
    assert build_demo.safe_path(pack, "../outside.md") is None
    assert build_demo.safe_path(pack, "ok.md") == (pack / "ok.md").resolve()
    assert build_demo.document_name("exams/final.pdf") == "exams_final.pdf"
