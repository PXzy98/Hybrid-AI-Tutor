"""v5 V16: an instructor may draft with the cloud model from public course material, only after confirming
that the material goes to it, and never in a local-only course. The local model stays the default. Fakes."""
# ruff: noqa: F811  (the `world` fixture of test_instructor_ai_api is reused as a test argument)
import asyncio

import pytest
from pydantic import ValidationError
from sqlmodel import Session, select

from app.core.schemas import Chunk, DraftCloudRequest
from app.instructor_ai import draft_jobs
from app.instructor_ai.drafts import generate_tier1_draft
from app.llm.cloud_guard import CloudClient, build_draft_cloud_request
from app.llm.fake import FakeLLMClient
from app.llm.gateway import FakeGateway
from app.platform import jobs
from app.storage.models import AiDraft, Kc
from tests.test_ai_drafts_v5 import _upload
from tests.test_instructor_ai_api import PASSAGE, TIER1, FakeCourseRetriever, _draft, world  # noqa: F401
from tests.test_web_pages_v7 import _html, _resolver, _site


def _start(world, body):
    return world["prof"].post(f"{world['url']}/ai/drafts", json=body)


def test_the_cloud_model_drafts_only_after_confirmation(world):
    local = world["use"](TIER1)
    world["cloud"].replies = [TIER1]
    assert _start(world, {"kind": "faq", "model": "cloud"}).status_code == 422  # not confirmed
    r = _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True})
    assert r.status_code == 202, r.text
    assert jobs.run_pending(world["services"]) >= 1
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "draft" and draft["sources"].get("model") == "cloud"
    assert len(world["cloud"].calls) == 1 and local.calls == []


def test_the_local_model_stays_the_default(world):
    local = world["use"](TIER1)
    r = _start(world, {"kind": "faq"})
    assert jobs.run_pending(world["services"]) >= 1
    assert _draft(world, r.json()["id"])["status"] == "draft"
    assert len(local.calls) == 1 and world["cloud"].calls == []


def test_a_local_only_course_never_drafts_with_the_cloud(world):
    world["use"](TIER1)
    prof, url = world["prof"], world["url"]
    current = prof.get(f"{url}/settings").json()
    assert prof.put(f"{url}/settings", json={"values": {"local_only": True},
                                             "version": current["version"]}).status_code == 200
    assert _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True}).status_code == 409
    world["services"].web_fetch_options = {"resolve": _resolver(), "inner": _site({"example.org/p": _html()})}
    page = {"url": "https://example.org/p", "kind": "faq", "model": "cloud", "confirm_cloud": True}
    assert prof.post(f"{url}/ai/drafts/url", json=page).status_code == 409
    assert world["cloud"].calls == []


def test_a_request_with_student_data_never_reaches_the_cloud(world):
    """The job scans the instructor's request before the cloud call, also for a draft stored before the
    request scan of the API existed."""
    world["use"](TIER1)
    world["cloud"].replies = [TIER1]
    services = world["services"]
    leak = "Write feedback for student 300123456 (jane.doe@uottawa.ca), who got 45% on the final."
    with Session(services.engine, expire_on_commit=False) as db:
        row = AiDraft(course_id=world["course_id"], kind="custom", focus="", request=leak,
                      sources={"model": "cloud"}, created_by=None)
        db.add(row)
        db.commit()
    jobs.enqueue(services.engine, draft_jobs.GENERATE, course_id=world["course_id"], ref_id=row.id,
                 created_by=None)
    jobs.run_pending(services)
    draft = _draft(world, row.id)
    assert draft["status"] == "failed" and "300123456" not in (draft["error"] or "")
    assert world["cloud"].calls == []


def _set_local_only(world):
    prof, url = world["prof"], world["url"]
    current = prof.get(f"{url}/settings").json()
    assert prof.put(f"{url}/settings", json={"values": {"local_only": True},
                                             "version": current["version"]}).status_code == 200


UPLOAD = "Open drain outputs need pull-ups.\n\nMore text."


# ---------------------------------------------------------------------------------- the cloud gate
def test_a_cloud_draft_passes_the_cloud_gate_with_the_allow_listed_fields_only(world):
    world["cloud"].replies = [TIER1]
    r = _start(world, {"kind": "custom", "request": "Write a short guide", "model": "cloud",
                       "confirm_cloud": True})
    assert jobs.run_pending(world["services"]) >= 1
    assert _draft(world, r.json()["id"])["status"] == "draft"
    call = world["cloud"].calls[0]
    assert PASSAGE in world["cloud"].sent_text() and "Write a short guide" in world["cloud"].sent_text()
    assert call["json_schema"] is not None and call["messages"][0]["role"] == "system"


def test_the_draft_request_of_the_gate_takes_no_other_field():
    ok = build_draft_cloud_request(kind="faq", passages=[(1, "syllabus.md", "text")])
    assert isinstance(ok, DraftCloudRequest)
    with pytest.raises(ValidationError):
        DraftCloudRequest.model_validate({**ok.model_dump(), "learner_profile": {"level": "weak"}})
    with pytest.raises(ValidationError):
        DraftCloudRequest.model_validate({**ok.model_dump(), "sanitized_question": "a question"})
    with pytest.raises(ValidationError):
        DraftCloudRequest.model_validate({**ok.model_dump(), "passages": [
            {"number": 1, "source": "s", "text": "t", "student": "x"}]})


def test_the_cloud_client_sends_a_draft_only_as_a_draft_request():
    cloud = FakeLLMClient(TIER1, model="cloud-x", backend="cloud")
    client = CloudClient(cloud)
    request = build_draft_cloud_request(kind="faq", passages=[(1, "s", "t")])
    with pytest.raises(TypeError):
        asyncio.run(client.complete_draft({"passages": ["free text"]}))  # type: ignore[arg-type]
    with pytest.raises(TypeError):
        asyncio.run(client.complete(request))  # type: ignore[arg-type]
    assert cloud.calls == []
    result = asyncio.run(client.complete_draft(request))
    assert result.backend == "cloud" and len(cloud.calls) == 1


def test_a_core_never_calls_gateway_complete_for_the_cloud():
    class Gate(FakeGateway):
        async def complete(self, role, messages, **kwargs):
            raise AssertionError("the cloud draft must go through cloud_client")

    cloud = FakeLLMClient(TIER1, model="cloud-x", backend="cloud")
    chunk = Chunk(text="Some public course text.", source="syllabus.md", topic="t", score=1.0,
                  metadata={"course_id": 7})
    draft = asyncio.run(generate_tier1_draft(course_id=7, kind="faq", passages=[chunk],
                                             gateway=Gate({"cloud": cloud}), settings=None, model="cloud"))
    assert draft.title and len(cloud.calls) == 1


# ------------------------------------------------------------------------------ scan before the cloud
def test_passages_with_personal_data_never_reach_the_cloud(world):
    world["services"].course_retriever = FakeCourseRetriever([Chunk(
        text="Contact student 300123456 (jane.doe@uottawa.ca) about the late project.",
        source="notes.md", topic="circuits", score=1.0)])
    r = _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True})
    jobs.run_pending(world["services"])
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "failed" and "300123456" not in (draft["error"] or "")
    assert "personal data" in draft["error"] and world["cloud"].calls == []


def test_kc_names_and_definitions_with_personal_data_never_reach_the_cloud(world):
    with Session(world["services"].engine) as db:
        row = db.exec(select(Kc).where(Kc.course_id == world["course_id"])).first()
        row.status = "active"
        row.definition = "Ask jane.doe@uottawa.ca, student 300123456, about this."
        db.add(row)
        db.commit()
    r = _start(world, {"kind": "kcs", "model": "cloud", "confirm_cloud": True})
    jobs.run_pending(world["services"])
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "failed" and "300123456" not in (draft["error"] or "")
    assert world["cloud"].calls == []


def test_a_draft_of_a_course_that_became_local_only_fails_instead_of_using_the_local_model(world):
    local = world["use"](TIER1)
    r = _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True})
    assert r.status_code == 202
    _set_local_only(world)
    jobs.run_pending(world["services"])
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "failed" and "local model" in draft["error"]
    assert local.calls == [] and world["cloud"].calls == []


# ------------------------------------------------------------------------------ routes and availability
def test_no_cloud_model_configured_is_a_conflict_and_not_available(world):
    prof, url = world["prof"], world["url"]
    assert prof.get(url).json()["cloud_available"] is True
    world["services"].gateway = FakeGateway({"local": FakeLLMClient(TIER1)})
    assert prof.get(url).json()["cloud_available"] is False
    assert _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True}).status_code == 409
    assert _start(world, {"kind": "faq"}).status_code == 202  # the local model is not affected


def test_upload_with_the_cloud_model_needs_the_confirmation(world):
    r = _upload(world["prof"], world["url"], "paper.md", UPLOAD, kind="faq", model="cloud")
    assert r.status_code == 422 and world["cloud"].calls == []
    r = _upload(world["prof"], world["url"], "paper.md", UPLOAD, kind="faq", model="cloud",
                confirm_cloud=True)
    assert r.status_code == 202


def test_upload_in_a_local_only_course_never_uses_the_cloud(world):
    _set_local_only(world)
    r = _upload(world["prof"], world["url"], "paper.md", UPLOAD, kind="faq", model="cloud",
                confirm_cloud=True)
    assert r.status_code == 409 and world["cloud"].calls == []
