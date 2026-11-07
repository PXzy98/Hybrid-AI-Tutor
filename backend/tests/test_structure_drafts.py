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

    async def complete(self, role, messages, *, settings, trust_required, json_schema=None,
                       stream=False):
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


@pytest.mark.asyncio
async def test_unknown_prerequisite_and_unknown_kc_are_rejected():
    kc = dict(_item("kcs"), prerequisite_names=["Nonexistent KC"])
    with pytest.raises(DraftError, match="unknown"):
        await generate_structure_draft(course_id=101, kind="kcs", passages=[_chunk()],
                                       gateway=FakeGateway([kc]), settings=None)
    with pytest.raises(DraftError, match="unknown"):
        await generate_structure_draft(course_id=101, kind="check_items", passages=[_chunk()],
                                       gateway=FakeGateway([_item("check_items")]), settings=None,
                                       known_kc_names=["Another KC"])
    ok = await generate_structure_draft(course_id=101, kind="check_items", passages=[_chunk()],
                                        gateway=FakeGateway([_item("check_items")]), settings=None,
                                        known_kc_names=["quartzzyme overview"])
    assert ok.items


@pytest.mark.asyncio
async def test_check_item_options_are_shuffled_and_the_answer_follows():
    items = [dict(_item("check_items"), question=f"Which imaginary property {n} describes Quartzzyme?")
             for n in range(12)]
    result = await generate_structure_draft(course_id=101, kind="check_items", passages=[_chunk()],
                                            gateway=FakeGateway(items), settings=None)
    assert all(item.options[item.correct_index] == "Example A" for item in result.items)
    assert len({item.correct_index for item in result.items}) > 1


def _resolve(schema: dict, node):
    """Follow every $ref from the document root; fails if a reference does not resolve."""
    if isinstance(node, dict):
        if "$ref" in node:
            target = schema
            for part in node["$ref"].removeprefix("#/").split("/"):
                target = target[part]
        for value in node.values():
            _resolve(schema, value)
    elif isinstance(node, list):
        for value in node:
            _resolve(schema, value)


@pytest.mark.parametrize("kind", ["kcs", "check_items", "misconceptions"])
def test_output_schema_is_the_whole_answer_with_resolvable_references(kind):
    from app.instructor_ai.structure_drafts import response_schema

    schema = response_schema(kind)
    assert schema["required"] == ["items"] and schema["additionalProperties"] is False
    assert "$defs" in schema and "$defs" not in schema["properties"]["items"]
    _resolve(schema, schema)


@pytest.mark.asyncio
async def test_accepted_kc_names_are_given_to_the_model():
    gateway = FakeGateway([_item("check_items")])
    await generate_structure_draft(course_id=101, kind="check_items", passages=[_chunk()], gateway=gateway,
                                   settings=None, known_kc_names=["Quartzzyme Overview", "Zephyrlens Basics"])
    request = json.loads(gateway.calls[0][3][1]["content"])
    assert request["accepted_kc_names"] == ["Quartzzyme Overview", "Zephyrlens Basics"]
    assert "accepted_kc_names" in request["kc_rule"]
