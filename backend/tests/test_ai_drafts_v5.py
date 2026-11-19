"""v5 V4, V5, V6: a custom draft request, a chosen set of sources (modules or files), and a file uploaded for
one draft. The local model is a fake; the course is an open course pack (AGENTS.md)."""
# ruff: noqa: F811  (the `world` fixture of test_instructor_ai_api is reused as a test argument)
import json
from pathlib import Path

from sqlmodel import Session, select

from app.core.schemas import Chunk
from app.platform import jobs
from app.rag.course import FakeCourseRetriever
from app.storage.models import Material
from tests.conftest import csrf_client
from tests.test_instructor_ai_api import TIER1, _draft, _login, world  # noqa: F401  (fixture)

REQUEST = "Summarize what the course says about pull-up resistors and suggest one lab exercise."


def _passage(text: str, module_id: int | None, name: str, course_id: int) -> Chunk:
    folder = module_id if module_id is not None else "_course"
    return Chunk(text=text, source=f"course/{course_id}/{folder}/{name}", topic=f"course:{course_id}",
                 score=1.0, metadata={"course_id": course_id, "module_id": module_id})


def _start(world, body: dict, reply: str = TIER1):
    local = world["use"](reply)
    r = world["prof"].post(f"{world['url']}/ai/drafts", json=body)
    if r.status_code != 202:
        return r, local
    assert jobs.run_pending(world["services"]) >= 1
    return r, local


def test_a_custom_request_reaches_the_local_model_and_stays_a_draft(world):
    r, local = _start(world, {"kind": "custom", "request": REQUEST})
    assert r.status_code == 202, r.text
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "draft" and draft["request"] == REQUEST
    sent = json.loads(local.calls[0]["messages"][1]["content"])
    assert sent["instructor_request"] == REQUEST and "instructor_request" in sent["task"]
    assert world["cloud"].calls == []
    assert world["prof"].post(f"{world['url']}/ai/drafts", json={"kind": "custom"}).status_code == 422
    accepted = world["prof"].post(f"{world['url']}/ai/drafts/{draft['id']}/accept", json={})
    assert accepted.status_code == 200 and accepted.json()["created"]["materials"]


def test_only_the_chosen_modules_or_files_are_used(world):
    services, cid, module = world["services"], world["course_id"], world["module"]["id"]
    other = world["prof"].post(f"{world['url']}/modules",
                               json={"code": "filters", "title": "Filters"}).json()["id"]
    with Session(services.engine) as db:
        for mid, name in ((module, "pullups.md"), (other, "filters.md"), (None, "syllabus.md")):
            db.add(Material(course_id=cid, module_id=mid, filename=name, size_bytes=1, sha256="0" * 64,
                            scan_status="accepted"))
        db.commit()
        ids = {m.filename: m.id for m in db.exec(select(Material).where(Material.course_id == cid)).all()}
    services.course_retriever = FakeCourseRetriever([
        _passage("PULLUP-PASSAGE pull-up resistors hold the line high.", module, "pullups.md", cid),
        _passage("FILTER-PASSAGE a low-pass filter passes low frequencies.", other, "filters.md", cid),
        _passage("SYLLABUS-PASSAGE the course has two quizzes.", None, "syllabus.md", cid)])

    r, local = _start(world, {"kind": "faq", "module_ids": [other]})
    sent = local.sent_text()
    assert r.status_code == 202 and "FILTER-PASSAGE" in sent and "PULLUP-PASSAGE" not in sent
    assert "SYLLABUS-PASSAGE" not in sent  # chosen modules only, not the course-level files
    assert _draft(world, r.json()["id"])["sources"] == {"module_ids": [other]}

    r, local = _start(world, {"kind": "faq", "material_ids": [ids["syllabus.md"], ids["pullups.md"]]})
    sent = local.sent_text()
    assert "SYLLABUS-PASSAGE" in sent and "PULLUP-PASSAGE" in sent and "FILTER-PASSAGE" not in sent

    bad = [{"kind": "faq", "module_ids": [other], "material_ids": [ids["syllabus.md"]]},
           {"kind": "faq", "module_id": module, "module_ids": [other]},
           {"kind": "faq", "material_ids": [999999]}, {"kind": "faq", "module_ids": [999999]}]
    for body in bad:
        assert world["prof"].post(f"{world['url']}/ai/drafts", json=body).status_code == 422, body


def _upload(client, url, name: str, text: str, **form):
    data = {k: (str(v).lower() if isinstance(v, bool) else str(v)) for k, v in form.items()}
    return client.post(f"{url}/ai/drafts/upload", data=data,
                       files={"file": (name, text.encode("utf-8"), "text/markdown")})


PAPER = ("# A new study\n\nOpen drain outputs need a pull-up resistor on every line of the bus.\n\n"
         "PAPER-PASSAGE The study measured rise times with three resistor values.")


def test_a_file_uploaded_for_one_draft_is_used_and_not_kept(world):
    local = world["use"](TIER1)
    r = _upload(world["prof"], world["url"], "paper.md", PAPER, kind="custom",
                request="What does this paper mean for the lab?")
    assert r.status_code == 202, r.text
    draft_id = r.json()["id"]
    upload_dir = Path(world["tmp"]) / "courses" / str(world["course_id"]) / "draft_uploads" / str(draft_id)
    assert (upload_dir / "paper.md").is_file()
    assert jobs.run_pending(world["services"]) >= 1
    draft = _draft(world, draft_id)
    assert draft["status"] == "draft" and draft["sources"] == {"upload": "paper.md"}
    assert not upload_dir.exists()  # read once, then deleted
    assert "PAPER-PASSAGE" in local.sent_text() and world["cloud"].calls == []
    with Session(world["services"].engine) as db:
        assert db.exec(select(Material).where(Material.filename == "paper.md")).first() is None


def test_an_uploaded_file_can_also_be_added_to_the_course(world):
    world["use"](TIER1)
    r = _upload(world["prof"], world["url"], "paper.md", PAPER, kind="faq", add_to_course=True,
                module_id=world["module"]["id"])
    assert r.status_code == 202, r.text
    assert jobs.run_pending(world["services"]) >= 1
    listed = world["prof"].get(f"{world['url']}/materials").json()["materials"]
    assert [(m["filename"], m["module_id"]) for m in listed] == [("paper.md", world["module"]["id"])]
    again = _upload(world["prof"], world["url"], "paper.md", PAPER, kind="faq", add_to_course=True,
                    module_id=world["module"]["id"])
    assert again.status_code == 409


def test_a_refused_file_creates_no_draft(world):
    roster = "Student 300123456, jane.doe@uottawa.ca, final grade 45%"
    r = _upload(world["prof"], world["url"], "roster.md", roster, kind="faq")
    assert r.status_code == 422 and "300123456" not in r.text
    assert world["prof"].get(f"{world['url']}/ai/drafts").json() == []


def test_who_may_upload_a_file_for_a_draft(world):
    app, url = world["app"], world["url"]
    for client, code in ((_login(app, "other"), 404), (_login(app, "alice"), 404), (csrf_client(app), 401)):
        assert _upload(client, url, "paper.md", PAPER, kind="faq").status_code == code


def test_a_request_with_student_data_is_refused_and_not_stored(world):
    """The custom request and the focus are scanned before they are stored, in both endpoints."""
    leak = "Write feedback for student 300123456 (jane.doe@uottawa.ca), who got 45% on the final."
    for body in ({"kind": "custom", "request": leak}, {"kind": "faq", "focus": leak}):
        r = world["prof"].post(f"{world['url']}/ai/drafts", json=body)
        assert r.status_code == 422 and "300123456" not in r.text, body
    r = _upload(world["prof"], world["url"], "paper.md", PAPER, kind="custom", request=leak)
    assert r.status_code == 422 and "300123456" not in r.text
    assert world["prof"].get(f"{world['url']}/ai/drafts").json() == []


def test_a_long_paragraph_of_an_uploaded_file_is_not_cut(world):
    """A file without blank lines (or text extracted with single newlines) is split into passages; the end
    of the file still reaches the model."""
    local = world["use"](TIER1)
    lines = [f"Line {i}: open drain outputs share the bus through one pull-up resistor." for i in range(40)]
    text = "\n".join([*lines, "LATE-PASSAGE rise times were measured with three resistor values."])
    assert len(text) > 2500
    r = _upload(world["prof"], world["url"], "paper.md", text, kind="custom",
                request="Summarize the rise time measurements with three resistor values.")
    assert r.status_code == 202, r.text
    assert jobs.run_pending(world["services"]) >= 1
    assert "LATE-PASSAGE" in local.sent_text()


def test_chosen_files_are_not_crowded_out_by_other_material(world):
    """Many better-ranked passages of other files do not hide the chosen file's passages."""
    services, cid, module = world["services"], world["course_id"], world["module"]["id"]
    with Session(services.engine) as db:
        db.add(Material(course_id=cid, module_id=module, filename="chosen.md", size_bytes=1, sha256="0" * 64,
                        scan_status="accepted"))
        db.commit()
        chosen = db.exec(select(Material).where(Material.filename == "chosen.md")).one().id
    crowd = [_passage(f"pull-up resistors, passage {i}", module, "other.md", cid) for i in range(400)]
    services.course_retriever = FakeCourseRetriever(
        [*crowd, _passage("CHOSEN-PASSAGE pull-up resistors", module, "chosen.md", cid)])
    r, local = _start(world, {"kind": "faq", "material_ids": [chosen]})
    assert r.status_code == 202 and _draft(world, r.json()["id"])["status"] == "draft"
    assert "CHOSEN-PASSAGE" in local.sent_text()
