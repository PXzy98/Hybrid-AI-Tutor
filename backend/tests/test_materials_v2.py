"""Course material through API v2 (api-v2.md 3.4; course-structure.md 7): scanned before it is stored,
indexed by the worker job, retrieved only in its course. Fictional text."""
import pytest

from app.platform import jobs
from tests.conftest import PASSWORD, csrf_client
from tests.test_ask_v2 import World, _login, rows

SYLLABUS = b"# Syllabus\n\nProblem set 3 is due on Friday of week 5. The final exam counts for 40 percent.\n"
NOTES = b"# Circuits\n\nKirchhoff's current law: the currents into a node sum to zero.\n"
ROSTER = b"Student 300418277 got 87% on the midterm.\n"


@pytest.fixture
def world(make_client, tmp_path):
    with make_client({"data_dir": str(tmp_path)}) as client:
        w = World(client)
        w.data = tmp_path
        yield w


def _upload(client, url, name, data, module_id=None):
    form = {"module_id": str(module_id)} if module_id is not None else {}
    return client.post(f"{url}/materials", files={"file": (name, data, "text/markdown")}, data=form)


def test_upload_index_and_retrieve_in_the_course(world):
    r = _upload(world.prof, world.url, "syllabus.md", SYLLABUS)
    assert r.status_code == 201, r.text
    assert r.json()["material"]["module_id"] is None
    r2 = _upload(world.prof, world.url, "kcl.md", NOTES, world.module)
    assert r2.json()["job_id"] == r.json()["job_id"]  # one waiting rebuild sees both files
    assert (world.data / "courses" / str(world.course) / "materials" / str(world.module) / "kcl.md").is_file()
    listed = world.prof.get(f"{world.url}/materials").json()
    assert listed["index_version"] == 0 and listed["rebuild_job_id"] == r.json()["job_id"]
    assert jobs.run_pending(world.services) == 1
    assert world.prof.get(f"{world.url}/jobs/{r.json()['job_id']}").json()["status"] == "done"
    listed = world.prof.get(f"{world.url}/materials").json()
    assert listed["index_version"] == 1 and listed["rebuild_job_id"] is None
    assert [m["filename"] for m in listed["materials"]] == ["kcl.md", "syllabus.md"]
    found = world.services.course_retriever.retrieve(world.course, None, "When is problem set 3 due?", 2)
    assert found and "Problem set 3" in found[0].text
    # another course never sees it
    assert world.services.course_retriever.retrieve(world.demo, None, "problem set 3 due", 2) == []
    assert _upload(world.prof, world.url, "syllabus.md", SYLLABUS).status_code == 409


def test_student_data_and_bad_files_are_refused_and_not_stored(world):
    r = _upload(world.prof, world.url, "results.md", ROSTER)
    assert r.status_code == 422 and "STUDENT_ID" in r.json()["detail"]
    assert "300418277" not in r.text
    assert _upload(world.prof, world.url, "run.exe", b"MZ").status_code == 422
    assert _upload(world.prof, world.url, "empty.md", b"").status_code == 422
    assert _upload(world.prof, world.url, "x.md", NOTES, module_id=999999).status_code == 404
    assert rows("material") == [] and not (world.data / "courses" / str(world.course) / "materials").exists()


def test_deleting_material_rebuilds_without_it(world):
    material = _upload(world.prof, world.url, "kcl.md", NOTES, world.module).json()["material"]
    jobs.run_pending(world.services)
    assert world.services.course_retriever.retrieve(world.course, world.module, "Kirchhoff current law", 1)
    assert world.prof.delete(f"{world.url}/materials/{material['id']}").status_code == 204
    jobs.run_pending(world.services)
    retriever = world.services.course_retriever
    assert retriever.retrieve(world.course, world.module, "Kirchhoff current law", 1) == []
    index = world.data / "courses" / str(world.course) / "index"
    assert sorted(p.name for p in index.iterdir() if p.name.startswith("v")) == ["v2"]  # old text removed
    assert world.prof.delete(f"{world.url}/materials/{material['id']}").status_code == 404


def test_only_the_course_instructors_manage_material(world):
    material = _upload(world.prof, world.url, "kcl.md", NOTES).json()["material"]
    world.services.accounts.create_instructor("other", PASSWORD, must_change=False)
    for client, code in ((_login(world.app, "other"), 404), (_login(world.app, "alice"), 404),
                         (csrf_client(world.app), 401)):
        assert client.get(f"{world.url}/materials").status_code == code
        assert _upload(client, world.url, "evil.md", NOTES).status_code == code
        assert client.delete(f"{world.url}/materials/{material['id']}").status_code == code
    assert [m["filename"] for m in rows("material")] == ["kcl.md"]
