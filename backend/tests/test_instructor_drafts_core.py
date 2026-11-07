"""Offline S6 draft tests. Nothing is sent to a live LLM or published."""
import json

import pytest

from app.core.schemas import Chunk
from app.instructor_ai.drafts import DraftError, generate_tier1_draft


class StubGateway:
    def __init__(self, reply=None):
        self.reply = reply or {"title": "Imaginary project", "body": "Use Quartzzyme.",
                               "citations": [1]}
        self.calls = []

    async def complete(self, role, messages, *, settings, trust_required, json_schema=None,
                       stream=False):
        self.calls.append((role, messages, settings, trust_required, stream))
        return type("Response", (), {"text": json.dumps(self.reply)})()


def _chunk(cid=101, source="course/101/_course/syllabus.md"):
    return Chunk(text="Quartzzyme is a fictional project exercise.",
                 source=source, topic=f"course:{cid}", score=0.9,
                 metadata={"course_id": cid})


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["project_ideas", "sample_proposal", "faq"])
async def test_trusted_local_gateway_returns_only_draft(kind):
    gateway = StubGateway()
    settings = object()
    draft = await generate_tier1_draft(course_id=101, kind=kind,
                                      passages=[_chunk()], gateway=gateway, settings=settings)
    assert draft.status == "draft"
    assert draft.course_id == 101 and draft.kind == kind
    assert draft.cited_sources == ["course/101/_course/syllabus.md"]
    assert gateway.calls[0][0] == "local"
    assert gateway.calls[0][2] is settings
    assert gateway.calls[0][3] == "trusted_local"
    assert gateway.calls[0][4] is False
    assert "Quartzzyme" in gateway.calls[0][1][1]["content"]
    assert "publish" not in draft.model_dump()


@pytest.mark.asyncio
async def test_cross_course_passages_rejected_before_model_call():
    gateway = StubGateway()
    with pytest.raises(DraftError, match="another course"):
        await generate_tier1_draft(course_id=101, kind="faq",
                                   passages=[_chunk(202)], gateway=gateway, settings=None)
    assert not gateway.calls


@pytest.mark.asyncio
async def test_citations_must_refer_to_actual_evidence():
    for bad in ([2], [0], [1, 1]):
        gateway = StubGateway({"title": "Wrong citation", "body": "Fictional answer.",
                               "citations": bad})
        with pytest.raises(DraftError, match="citation"):
            await generate_tier1_draft(course_id=101, kind="faq",
                                       passages=[_chunk()], gateway=gateway, settings=None)


@pytest.mark.asyncio
async def test_no_source_no_generation():
    gateway = StubGateway()
    with pytest.raises(DraftError, match="required"):
        await generate_tier1_draft(course_id=101, kind="faq",
                                   passages=[], gateway=gateway, settings=None)
    assert not gateway.calls


@pytest.mark.asyncio
async def test_invalid_result_is_not_accepted():
    gateway = StubGateway({"title": "Bad", "body": "Text", "citations": [1],
                           "status": "accepted"})
    with pytest.raises(DraftError, match="valid draft"):
        await generate_tier1_draft(course_id=101, kind="faq",
                                   passages=[_chunk()], gateway=gateway, settings=None)


@pytest.mark.asyncio
async def test_nonsense_kind_fails_closed():
    gateway = StubGateway()
    with pytest.raises(DraftError, match="Unsupported"):
        await generate_tier1_draft(course_id=101, kind="grade_student",
                                   passages=[_chunk()], gateway=gateway, settings=None)
    assert not gateway.calls


@pytest.mark.parametrize("text", [
    '{"title": "T", "body": "B", "citations": [1]}',
    '<think>checking the passages</think>\n```json\n{"title": "T", "body": "B", "citations": [1]}\n```',
    'Here is the draft:\n{"title": "T", "body": "B", "citations": [1]}',
])
def test_local_model_answers_with_reasoning_or_fences_are_parsed(text):
    from app.instructor_ai.drafts import parse_model_json

    assert parse_model_json(text) == {"title": "T", "body": "B", "citations": [1]}


@pytest.mark.asyncio
async def test_the_gateway_receives_the_output_schema():
    gateway = StubGateway()
    seen = {}
    original = gateway.complete

    async def complete(role, messages, **kw):
        seen.update(kw)
        return await original(role, messages, **kw)

    gateway.complete = complete
    await generate_tier1_draft(course_id=101, kind="faq", passages=[_chunk()], gateway=gateway, settings=None)
    assert set(seen["json_schema"]["properties"]) == {"title", "body", "citations"}
