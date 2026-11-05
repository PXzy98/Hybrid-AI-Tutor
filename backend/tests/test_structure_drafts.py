"""S7: offline structure generation tests, fictional content only."""
import json

import pytest

from app.core.schemas import Chunk
from app.instructor_ai.drafts import DraftError
from app.instructor_ai.structure_drafts import generate_structure_draft


class FakeGateway:
    def __init__(self, items):
        self.items = items
        self.calls = []

    async def complete(self, role, messages, *, settings, trust_required, stream=False):
        self.calls.append((role, trust_required, stream, messages))
        return type("Response", (), {"text": json.dumps({"items": self.items})})()


def _chunk(course_id=101):
    return Chunk(text="A fictional course about Quartzzyme has three imaginary modules.",
                 source="course/101/_course/guide.md", topic="course:101",
                 score=0.8, metadata={"course_id": course_id})


def _item(kind):
    if kind == "kcs":
        return {"name": "Quartzzyme Overview", "definition": "Explain the fictional Quartzzyme process.",
                "prerequisite_names": [], "citations": [1]}
    if kind == "check_items":
        return {"question": "Which imaginary property describes Quartzzyme?",
                "options": ["Example A", "Example B", "Example C", "Example D"],
                "correct_index": 0, "explanation": "Example A is specified in the fictional notes.",
                "kc_names": ["Quartzzyme Overview"], "citations": [1]}
    return {"name": "Quartzzyme Mistake", "incorrect_belief": "Quartzzyme is not a fictional process.",
            "correction": "The imaginary course describes Quartzzyme as a fictional process.",
            "kc_name": "Quartzzyme Overview", "citations": [1]}


@pytest.mark.asyncio
@pytest.mark.parametrize("kind", ["kcs", "check_items", "misconceptions"])
async def test_generate_draft_only_with_trusted_local_gateway(kind):
    gateway = FakeGateway([_item(kind)])
    result = await generate_structure_draft(
        course_id=101, kind=kind, passages=[_chunk()], gateway=gateway, settings=object(),
    )
    assert result.status == "draft" and result.course_id == 101
    assert result.cited_sources == ["course/101/_course/guide.md"]
    assert gateway.calls[0][:3] == ("local", "trusted_local", False)
    assert "Quartzzyme" in gateway.calls[0][3][1]["content"]


@pytest.mark.asyncio
async def test_cross_course_evidence_is_rejected_before_gateway():
    gateway = FakeGateway([_item("kcs")])
    with pytest.raises(DraftError, match="scope"):
        await generate_structure_draft(course_id=101, kind="kcs",
                                       passages=[_chunk(202)], gateway=gateway, settings=None)
    assert not gateway.calls


@pytest.mark.asyncio
@pytest.mark.parametrize("wrong", [[2], [0], [1, 1], [True]])
async def test_invalid_citations_are_rejected(wrong):
    item = _item("kcs") | {"citations": wrong}
    with pytest.raises(DraftError, match="citation|invalid"):
        await generate_structure_draft(course_id=101, kind="kcs",
                                       passages=[_chunk()], gateway=FakeGateway([item]),
                                       settings=None)


@pytest.mark.asyncio
async def test_duplicate_choice_rejected():
    item = _item("check_items")
    item["options"] = ["Same", "Same", "Other", "Unique"]
    with pytest.raises(DraftError, match="invalid"):
        await generate_structure_draft(course_id=101, kind="check_items",
                                       passages=[_chunk()], gateway=FakeGateway([item]),
                                       settings=None)


@pytest.mark.asyncio
async def test_generated_item_never_contains_publication_state():
    result = await generate_structure_draft(
        course_id=101, kind="misconceptions", passages=[_chunk()],
        gateway=FakeGateway([_item("misconceptions")]), settings=None,
    )
    assert result.status == "draft"
    assert "accepted" not in result.model_dump_json()
    assert "approved" not in result.model_dump_json()


@pytest.mark.asyncio
async def test_invalid_draft_kind_rejected():
    with pytest.raises(DraftError):
        await generate_structure_draft(course_id=101, kind="student_marks",
                                       passages=[_chunk()], gateway=FakeGateway([]),
                                       settings=None)
