"""Cross-component Siyun v4 smoke test, exclusively fictional local fixtures.

This does not simulate production authorization, database/worker transactions,
or the Z11 privacy scanner; those must be implemented by their component owners.
"""
import json
from datetime import UTC, datetime

import pytest

from app.instructor_ai.drafts import generate_tier1_draft
from app.instructor_ai.insights import InsightEvent, aggregate_class_insights
from app.instructor_ai.structure_drafts import generate_structure_draft
from app.learner.knowledge.course_core import CourseEvidence, CourseKnowledgeCore
from app.learner.learning_plan import LearningPlan, validate_learning_plan
from app.learner.visibility_policy import (
    LearnerSignal,
    VisibilityState,
    instructor_visible_signals,
)
from app.rag.course_retriever import IndexedCourseRetriever
from app.rag.evaluation import GoldLabel, evaluate_two_course_rag


class _FakeLocalGateway:
    def __init__(self):
        self.messages = []

    async def complete(self, role, messages, *, settings, trust_required, stream=False):
        assert (role, trust_required, stream) == ("local", "trusted_local", False)
        self.messages.append(messages)
        task = json.loads(messages[1]["content"])["task"]
        if task.startswith("Draft knowledge"):
            result = {"items": [{
                "name": "Quartzzyme concept",
                "definition": "Understand the fictional Quartzzyme protocol.",
                "prerequisite_names": [],
                "citations": [1],
            }]}
        else:
            result = {"title": "Draft teaching project",
                      "body": "Write about the fictional Quartzzyme policy.",
                      "citations": [1]}
        return type("Response", (), {"text": json.dumps(result)})()


def _prepare(tmp_path):
    materials = [
        (101, "_course", "syllabus.md",
         "# Invented Course\nQuartzzyme describes the fictional course policy."),
        (101, "7", "lecture.md",
         "# Module Seven\nZephyrlens explains a pretend lab technique."),
        (202, "_course", "syllabus.md",
         "# Other Course\nSecondforge describes another fictional course policy."),
    ]
    for cid, module, name, text in materials:
        path = tmp_path / "courses" / str(cid) / "materials" / module / name
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(text, encoding="utf-8")

    # A permissive scanner is injected ONLY in this fictional unit-test fixture.
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    assert rag.rebuild(101) == 1
    assert rag.rebuild(202) == 1
    return rag


@pytest.mark.asyncio
async def test_s4_s6_s7_s8_s9_s10_s11_fictional_end_to_end(tmp_path):
    rag = _prepare(tmp_path)
    evidence = rag.retrieve(101, 7, "Quartzzyme fictional course policy", 4)
    assert evidence and all(p.metadata["course_id"] == 101 for p in evidence)
    assert rag.retrieve(202, None, "Quartzzyme", 4) == []
    assert not any("Zephyrlens" in p.text for p in rag.retrieve(101, 8, "Zephyrlens", 4))

    gateway = _FakeLocalGateway()
    tier1 = await generate_tier1_draft(
        course_id=101, kind="project_ideas", passages=evidence,
        gateway=gateway, settings=object(),
    )
    tier2 = await generate_structure_draft(
        course_id=101, kind="kcs", passages=evidence,
        gateway=gateway, settings=object(),
    )
    assert tier1.status == tier2.status == "draft"
    assert tier1.cited_sources == tier2.cited_sources
    assert len(gateway.messages) == 2

    learner = CourseKnowledgeCore({"KC-demo": []})
    initial = learner.initial(101, "fictional-learner")
    updated = learner.update(
        initial, CourseEvidence(101, "fictional-learner", "KC-demo", "strong", True),
    )
    assert updated.kcs["KC-demo"].probability > initial.ability
    at = datetime(2026, 11, 5, tzinfo=UTC)
    consent = VisibilityState(101, "fictional-learner", "B", at, at)
    audits = []
    viewed = instructor_visible_signals(
        state=consent, authorized_instructor=True,
        signals=[LearnerSignal(101, "fictional-learner", at, "KC-demo",
                               updated.kcs["KC-demo"].probability)],
        audit_view=lambda cid, sid: audits.append((cid, sid)) or True,
    )
    assert len(viewed) == 1 and audits == [(101, "fictional-learner")]
    plan = LearningPlan(101, "fictional-learner", ("KC-demo",),
                        "basic", "Review the fictional course.", at)
    assert validate_learning_plan(
        state=consent, plan=plan, known_kcs={"KC-demo"},
        authorized_instructor=True, audit_update=lambda *_: True,
    ) == plan

    events = [InsightEvent(101, f"fake-{i}", "KC-demo") for i in range(6)]
    report = aggregate_class_insights(course_id=101, events=events)
    assert report.kc_question_counts[0].count == 6
    assert "fake-" not in repr(report)

    labels = [
        GoldLabel("course-a", 101, None, "Quartzzyme fictional course policy",
                  "course/101/_course/syllabus.md", "Quartzzyme describes", False),
        GoldLabel("course-b", 202, None, "Secondforge fictional course policy",
                  "course/202/_course/syllabus.md", "Secondforge describes", False),
    ]
    metrics = evaluate_two_course_rag(
        retriever=rag, index_root=tmp_path, labels=labels, k=4,
    )
    assert metrics["courses"] == 2
    assert metrics["recall_at_k"] == 1.0
    assert metrics["source_traceability"] == 1.0
