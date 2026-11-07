"""S6/S7 integration contract tests against Z1's actual fail-closed model gateway."""
import json

import pytest

from app.core.schemas import Chunk
from app.instructor_ai.drafts import generate_tier1_draft
from app.instructor_ai.structure_drafts import generate_structure_draft
from app.llm.fake import FakeLLMClient
from app.llm.gateway import FakeGateway, TrustViolation
from app.platform.settings import effective_settings


def _passages():
    return [Chunk(
        topic="course:101", source="course/101/_course/fictional.md",
        text="Quartzzyme is an imaginary course-wide policy.",
        score=0.6, metadata={"course_id": 101, "module_id": None},
    )]


@pytest.mark.asyncio
async def test_s6_uses_real_gateway_contract_without_cloud_leak():
    local = FakeLLMClient(json.dumps({
        "title": "Fictional project", "body": "Explain Quartzzyme.",
        "citations": [1],
    }))
    cloud = FakeLLMClient("should not be called", backend="cloud")
    gateway = FakeGateway({"local": local, "cloud": cloud})
    settings = effective_settings(101)
    result = await generate_tier1_draft(
        course_id=101, kind="project_ideas", passages=_passages(),
        gateway=gateway, settings=settings,
    )
    assert result.status == "draft"
    assert len(local.calls) == 1
    assert cloud.calls == []
    assert "Quartzzyme" in local.sent_text()


@pytest.mark.asyncio
async def test_s7_uses_real_gateway_contract_without_cloud_leak():
    local = FakeLLMClient(json.dumps({"items": [{
        "name": "Imaginary KC", "definition": "The Quartzzyme fictional policy.",
        "prerequisite_names": [], "citations": [1],
    }]}))
    cloud = FakeLLMClient("should not be called", backend="cloud")
    gateway = FakeGateway({"local": local, "cloud": cloud})
    result = await generate_structure_draft(
        course_id=101, kind="kcs", passages=_passages(), gateway=gateway,
        settings=effective_settings(101),
    )
    assert result.status == "draft"
    assert len(local.calls) == 1 and cloud.calls == []


@pytest.mark.asyncio
async def test_untrusted_local_model_cannot_receive_instructor_source():
    local = FakeLLMClient("{}")
    gateway = FakeGateway({"local": local}, trusted=frozenset())
    with pytest.raises(TrustViolation):
        await generate_tier1_draft(
            course_id=101, kind="faq", passages=_passages(), gateway=gateway,
            settings=effective_settings(101),
        )
    assert local.calls == []
