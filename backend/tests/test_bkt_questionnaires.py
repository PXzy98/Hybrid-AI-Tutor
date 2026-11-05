"""All five medical-topic BKT diagnostics: content, app integration, consent and review gate.

All new clinical content is draft and must not be treated as medically reviewed.
"""

from collections import Counter
from pathlib import Path

import pytest

from app.learner.checks import choose_item, diagnostic_items, grade, topological
from app.learner.content import ContentStore
from tests.conftest import Api

CONTENT = Path(__file__).resolve().parents[2] / "content" / "topics"
TOPICS = ("type2_diabetes", "asthma", "migraine", "pneumonia")


@pytest.mark.parametrize("topic", TOPICS)
def test_new_topic_content_has_five_kcs_and_three_questions_per_kc(topic):
    store = ContentStore(CONTENT, serve_unreviewed=True)
    tc = store.topic(topic)
    assert len(tc.kcs) == 5
    assert len(tc.items) == 15
    assert len(tc.misconceptions) == 5
    assert all(item.reviewed_by is None for item in tc.items)
    assert all(mc.reviewed_by is None for mc in tc.misconceptions)
    assert len(diagnostic_items(store, topic)) == 5
    assert [item.kc for item in diagnostic_items(store, topic)] == topological(store, topic)
    assert all(item.level == "basic" for item in diagnostic_items(store, topic))
    for kc in tc.kcs:
        items = [i for i in tc.items if i.kc == kc.id]
        assert set(i.level for i in items) == {"basic", "intermediate", "advanced"}
    counts = Counter(i.answer for i in tc.items)
    assert set(counts) == set("ABCD")
    assert max(counts.values()) <= 4
    used = {o.misconception for i in tc.items for o in i.options.values() if o.misconception}
    assert used == {mc.id for mc in tc.misconceptions}
    for item in tc.items:
        assert len(item.options) == 4
        assert item.options[item.answer].misconception is None
        assert grade(item, item.answer).correct
        for choice, option in item.options.items():
            if option.misconception:
                result = grade(item, choice)
                assert not result.correct and result.misconception_id == option.misconception


@pytest.mark.parametrize("topic", TOPICS)
def test_student_onboarding_bkt_updates_on_correct_diagnostic_answers(make_client, topic):
    with make_client({"content": {"serve_unreviewed": True}, "learner": {"knowledge": "bkt"}}) as client:
        api = Api(client)
        student = api.make_student()
        api.login("alice")
        response = client.get("/api/v1/onboarding", params={"topic": topic})
        assert response.status_code == 200, response.text
        questions = response.json()["diagnostic"]
        assert len(questions) == 5
        assert len({question["kc_id"] for question in questions}) == 5
        assert all(set(question) == {"id", "kc_id", "stem", "options"} for question in questions)
        assert all(set(question["options"]) == set("ABCD") for question in questions)
        before = api.services.learner.context(student.student_id, topic).kc_states
        answers = [
            {"item_id": question["id"], "choice": api.services.content.item(question["id"]).answer}
            for question in questions
        ]
        result = client.post(
            "/api/v1/onboarding",
            json={
                "topic": topic,
                "consent": True,
                "answers": answers,
                "preferences": {"sequencing": "concept_first", "detail": "detailed"},
            },
        )
        assert result.status_code == 200, result.text
        body = result.json()
        assert body["personalized"] is True
        assert len(body["assessed"]) == 5
        assert all(body["assessed"].values())
        assert body["skipped"] == []
        after = api.services.learner.context(student.student_id, topic).kc_states
        for kc in body["assessed"]:
            prior = before[kc].p_mastery if kc in before else 0.20  # BKT default initial probability
            assert after[kc].p_mastery > prior
        logs = api.services.learner.repo.evidence(student.student_id)
        assert len([entry for entry in logs if entry.kind == "diagnostic"]) == 5
        first_kc = api.services.content.kcs(topic)[0].id
        followup = choose_item(
            api.services.content, api.services.learner.repo, student.student_id, first_kc, "intermediate"
        )
        assert followup is not None and followup.id != questions[0]["id"]
        checking = client.post("/api/v1/check", json={"item_id": followup.id, "choice": followup.answer})
        assert checking.status_code == 200, checking.text
        assert checking.json()["correct"] is True
        assert (
            len(
                [
                    entry
                    for entry in api.services.learner.repo.evidence(student.student_id)
                    if entry.kind == "strong"
                ]
            )
            == 1
        )


@pytest.mark.parametrize("topic", TOPICS)
def test_wrong_prerequisite_blocks_dependent_diagnostic_kcs(make_client, topic):
    with make_client({"content": {"serve_unreviewed": True}, "learner": {"knowledge": "bkt"}}) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        questions = client.get("/api/v1/onboarding", params={"topic": topic}).json()["diagnostic"]
        answers = []
        for i, question in enumerate(questions):
            correct = api.services.content.item(question["id"]).answer
            answers.append(
                {
                    "item_id": question["id"],
                    "choice": next(x for x in "ABCD" if x != correct) if i == 0 else correct,
                }
            )
        result = client.post("/api/v1/onboarding", json={"topic": topic, "consent": True, "answers": answers})
        assert result.status_code == 200, result.text
        out = result.json()
        assert out["assessed"] == {questions[0]["kc_id"]: False}
        assert set(out["skipped"]) == {q["kc_id"] for q in questions[1:]}


@pytest.mark.parametrize("topic", TOPICS)
def test_unreviewed_drafts_never_served_or_accepted_by_default(make_client, topic):
    with make_client({"content": {"serve_unreviewed": False}}) as client:
        api = Api(client)
        student = api.make_student()
        api.login("alice")
        questions = client.get("/api/v1/onboarding", params={"topic": topic}).json()["diagnostic"]
        assert questions == []
        item = ContentStore(CONTENT, serve_unreviewed=True).topic(topic).items[0]
        response = client.post(
            "/api/v1/onboarding",
            json={
                "topic": topic,
                "consent": True,
                "answers": [{"item_id": item.id, "choice": item.answer}],
            },
        )
        assert response.status_code == 422
        assert api.services.learner.repo.evidence(student.student_id) == []
        assert (
            client.post("/api/v1/check", json={"item_id": item.id, "choice": item.answer}).status_code == 404
        )
