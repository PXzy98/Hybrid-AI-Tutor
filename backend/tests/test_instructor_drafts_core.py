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
                       stream=False, max_tokens=None):
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
async def test_the_local_model_is_asked_for_markdown_not_json():
    """M8: asked for one JSON object, the local model looped until max_tokens in most custom drafts."""
    gateway = StubGateway()
    seen = {}
    original = gateway.complete

    async def complete(role, messages, **kw):
        seen.update(kw, messages=messages)
        return await original(role, messages, **kw)

    gateway.complete = complete
    await generate_tier1_draft(course_id=101, kind="faq", passages=[_chunk()], gateway=gateway, settings=None)
    assert seen.get("json_schema") is None
    system = seen["messages"][0]["content"]
    assert "Markdown" in system and "Citations:" in system and "JSON" not in system


class TextGateway(StubGateway):
    def __init__(self, text):
        super().__init__()
        self.text = text

    async def complete(self, role, messages, **kw):
        self.calls.append((role, messages))
        return type("Response", (), {"text": self.text, "prompt_tokens": 900, "completion_tokens": 300})()


@pytest.mark.asyncio
@pytest.mark.parametrize("last", ["Citations: 1", "**Citations:** 1", "citations: 1."])
async def test_a_markdown_draft_is_parsed(last):
    text = f"# Quartzzyme worked example\n\n## Example\n\nUse the fictional Quartzzyme step.\n\n{last}\n"
    draft = await generate_tier1_draft(course_id=101, kind="custom", passages=[_chunk()],
                                       gateway=TextGateway(text), settings=None, request="One example")
    assert draft.title == "Quartzzyme worked example"
    assert draft.body == "## Example\n\nUse the fictional Quartzzyme step."
    assert draft.cited_sources == ["course/101/_course/syllabus.md"]


@pytest.mark.asyncio
@pytest.mark.parametrize("text", [
    "# Title only\n\nA body without a citations line.",
    "No title line\n\nBody.\n\nCitations: 1",
    "# Looped\n\nper passages 1, 2, 3, 4, 5, 6, 7, 8, 9, 10, 11, 12",
])
async def test_a_markdown_draft_without_title_or_citations_fails(text):
    with pytest.raises(DraftError, match="valid draft"):
        await generate_tier1_draft(course_id=101, kind="custom", passages=[_chunk()],
                                   gateway=TextGateway(text), settings=None, request="One example")


@pytest.mark.asyncio
async def test_a_markdown_draft_citing_a_missing_passage_fails():
    with pytest.raises(DraftError, match="citation"):
        await generate_tier1_draft(course_id=101, kind="custom", passages=[_chunk()],
                                   gateway=TextGateway("# T\n\nBody.\n\nCitations: 1, 3"), settings=None,
                                   request="One example")


@pytest.mark.asyncio
async def test_the_draft_log_has_counts_and_no_text(caplog):
    text = "# Quartzzyme secret title\n\nZephyrlens body text.\n\nCitations: 1"
    with caplog.at_level("INFO", logger="app.instructor_ai.drafts"):
        await generate_tier1_draft(course_id=101, kind="custom", passages=[_chunk()],
                                   gateway=TextGateway(text), settings=None, request="Quartzzyme request")
    logged = " ".join(r.getMessage() for r in caplog.records)
    assert "passages=1" in logged and "prompt_tokens=900" in logged and "completion_tokens=300" in logged
    assert "Quartzzyme" not in logged and "Zephyrlens" not in logged


def test_the_cloud_draft_keeps_the_json_format():
    from app.core.schemas import DraftCloudRequest
    from app.instructor_ai.draft_cloud import render_draft

    req = DraftCloudRequest.model_validate({"kind": "faq", "passages": [
        {"number": 1, "source": "course/101/_course/syllabus.md", "text": "Fictional Quartzzyme text."}]})
    messages, schema, _ = render_draft(req)
    assert "JSON" in messages[0]["content"] and set(schema["properties"]) == {"title", "body", "citations"}


@pytest.mark.asyncio
async def test_input_budget_can_be_raised_up_to_the_hard_limit():
    passages = [_chunk() for _ in range(12)]
    with pytest.raises(DraftError):
        await generate_tier1_draft(course_id=101, kind="project_ideas", passages=passages,
                                   gateway=StubGateway(), settings=None)
    draft = await generate_tier1_draft(course_id=101, kind="project_ideas", passages=passages,
                                       gateway=StubGateway(), settings=None, max_passages=16)
    assert draft.status == "draft"
    with pytest.raises(DraftError, match="hard limits"):
        await generate_tier1_draft(course_id=101, kind="project_ideas", passages=passages,
                                   gateway=StubGateway(), settings=None, max_passages=100)
