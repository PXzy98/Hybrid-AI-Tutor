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


def test_instructor_only_files_are_never_uploaded(tmp_path):
    pack = tmp_path / "p"
    (pack / "instructor_only").mkdir(parents=True)
    (pack / "instructor_only" / "key.md").write_text("answers", encoding="utf-8")
    (pack / "ok.md").write_text("notes", encoding="utf-8")
    assert build_demo.safe_path(pack, "instructor_only/key.md") is None
    assert build_demo.safe_path(pack, "../outside.md") is None
    assert build_demo.safe_path(pack, "ok.md") == (pack / "ok.md").resolve()
    assert build_demo.document_name("exams/final.pdf") == "exams_final.pdf"
