"""Step 7: onboarding, check questions, attach_check, learner/me, level-aware prompts.

Design §5.5, §6, §7.
"""
from datetime import timedelta

import pytest
from sqlmodel import Session, select

from app.learner.checks import choose_item, diagnostic_items, grade, topological
from app.prompts.render import level_partial, style_partial
from app.storage.models import EvidenceLog, utcnow
from tests.conftest import Api

DEV = {"content": {"serve_unreviewed": True}}  # nothing is reviewed yet; the MVP demo runs like this
HBP = "high_blood_pressure"


@pytest.fixture
def dev(make_client):
    with make_client(DEV) as client:
        api = Api(client)
        api.student = api.make_student()
        api.login("alice")
        yield api


def key(api, item_id):
    return api.services.content.item(item_id).answer


def wrong(api, item_id):
    return next(k for k in "ABCD" if k != key(api, item_id))


def ask(api, question="What do the two numbers mean?"):
    r = api.client.post("/api/v1/ask", json={"topic": HBP, "question": question})
    assert r.status_code == 200, r.text
    return r.json()


def onboard(api, consent=True, prefs=None, answers=None):
    body = {"topic": HBP, "consent": consent, "preferences": prefs or {}, "answers": answers or []}
    r = api.client.post("/api/v1/onboarding", json=body)
    assert r.status_code == 200, r.text
    return r.json()


def bands(api):
    prof = api.client.get("/api/v1/learner/me", params={"topic": HBP}).json()
    return {k["kc_id"]: k["band"] for k in prof["topics"][0]["kcs"]}


# ------------------------------------------------------------------------------ unit level
def test_grade_by_key_and_distractor_misconception(dev):
    item = dev.services.content.item("HBP.6-q1")
    assert grade(item, item.answer).correct and grade(item, item.answer).misconception_id is None
    tagged = next(k for k, o in item.options.items() if o.misconception)
    g = grade(item, tagged)
    assert not g.correct and g.correct_choice == item.answer
    assert g.misconception_id == item.options[tagged].misconception


def test_diagnostic_is_one_basic_item_per_kc_prerequisites_first(dev):
    content = dev.services.content
    assert topological(content, HBP) == ["HBP.1", "HBP.2", "HBP.3", "HBP.4", "HBP.5", "HBP.6"]
    items = diagnostic_items(content, HBP)
    assert [i.kc for i in items] == topological(content, HBP)
    assert all(i.level == "basic" for i in items)


def test_choose_item_prefers_unseen_and_never_repeats_within_24h(dev):
    content, repo, sid = dev.services.content, dev.services.learner.repo, dev.student.student_id
    dev.services.learner.set_consent(sid, True)
    first = choose_item(content, repo, sid, "HBP.1", "intermediate")
    assert first.level == "intermediate"  # level match among unseen items
    seen = []
    for _ in range(4):
        item = choose_item(content, repo, sid, "HBP.1", "intermediate")
        assert item and item.id not in seen
        seen.append(item.id)
        dev.client.post("/api/v1/check", json={"item_id": item.id, "choice": item.answer})
    assert choose_item(content, repo, sid, "HBP.1", "intermediate") is None  # all answered in the last 24 h
    with Session(dev.services.engine) as db:  # a day later the oldest one comes back
        row = db.exec(select(EvidenceLog).where(EvidenceLog.item_id == seen[0])).first()
        row.created_at = utcnow() - timedelta(hours=25)
        db.add(row)
        db.commit()
    assert choose_item(content, repo, sid, "HBP.1", "intermediate").id == seen[0]


# --------------------------------------------------------------------------------- onboarding
def test_get_onboarding(dev):
    info = dev.client.get("/api/v1/onboarding", params={"topic": HBP}).json()
    assert "learning profile" in info["consent_text"] and info["consent_given"] is None
    assert [q["id"] for q in info["preference_questions"]] == ["sequencing", "detail"]
    assert [i["kc_id"] for i in info["diagnostic"]] == [f"HBP.{n}" for n in range(1, 7)]
    assert all(set(i) == {"id", "kc_id", "stem", "options"} for i in info["diagnostic"])  # no key
    assert dev.client.get("/api/v1/onboarding", params={"topic": "astrology"}).status_code == 422


def test_onboarding_without_consent_stores_nothing(dev):
    res = onboard(dev, consent=False, prefs={"detail": "detailed"},
                  answers=[{"item_id": "HBP.1-q1", "choice": key(dev, "HBP.1-q1")}])
    assert res == {"personalized": False, "assessed": {}, "skipped": [], "kcs": []}
    assert dev.client.get("/api/v1/learner/me").json() == {"personalized": False, "preferences": None,
                                                             "topics": []}


def test_onboarding_skips_dependents_of_a_missed_prerequisite(dev):
    items = [i.id for i in diagnostic_items(dev.services.content, HBP)]
    answers = [{"item_id": i, "choice": key(dev, i)} for i in items]
    answers[0]["choice"] = wrong(dev, items[0])  # HBP.1 wrong
    res = onboard(dev, prefs={"sequencing": "concept_first", "detail": "detailed"}, answers=answers)
    assert res["assessed"] == {"HBP.1": False}
    assert res["skipped"] == ["HBP.2", "HBP.3", "HBP.4", "HBP.5", "HBP.6"]  # transitively
    assert {k["kc_id"]: k["band"] for k in res["kcs"]}["HBP.2"] == "basic"  # kept the prior
    prof = dev.client.get("/api/v1/learner/me").json()
    assert prof["preferences"]["sequencing"] == "concept_first"
    assert prof["preferences"]["source"] == "onboarding"


def test_onboarding_rejects_items_of_other_topics(dev):
    r = dev.client.post("/api/v1/onboarding", json={"topic": "asthma", "consent": True,
                                                     "answers": [{"item_id": "HBP.1-q1", "choice": "A"}]})
    assert r.status_code == 422


# -------------------------------------------------------------------------------------- check
def test_check_records_strong_evidence_and_misconception(dev):
    onboard(dev)
    item = dev.services.content.item("HBP.6-q1")
    tagged = next(k for k, o in item.options.items() if o.misconception)
    r = dev.client.post("/api/v1/check", json={"item_id": item.id, "choice": tagged}).json()
    assert r["correct"] is False and r["correct_choice"] == item.answer and r["explanation"]
    assert r["kc_id"] == "HBP.6" and r["kc_band"] == "basic" and r["next_kc"]["kc_id"] == "HBP.1"
    log = dev.services.learner.repo.evidence(dev.student.student_id)
    assert (log[-1].kind, log[-1].item_id, log[-1].misconception_id) == ("strong", item.id,
                                                                         item.options[tagged].misconception)


def test_check_without_consent_grades_but_records_nothing(dev):
    r = dev.client.post("/api/v1/check", json={"item_id": "HBP.1-q1", "choice": key(dev, "HBP.1-q1")}).json()
    assert r["correct"] is True and r["kc_level"] is None and r["next_kc"] is None
    assert dev.services.learner.repo.evidence(dev.student.student_id) == []


def test_check_errors(dev, api):
    assert dev.client.post("/api/v1/check", json={"item_id": "NOPE-q1", "choice": "A"}).status_code == 404
    assert dev.client.post("/api/v1/check", json={"item_id": "HBP.1-q1", "choice": "E"}).status_code == 422


def test_unreviewed_items_are_not_served_by_default(api):
    api.make_student()
    api.login("alice")
    assert api.client.post("/api/v1/check", json={"item_id": "HBP.1-q1", "choice": "A"}).status_code == 404
    assert api.client.get("/api/v1/onboarding", params={"topic": HBP}).json()["diagnostic"] == []
    assert ask(api)["check_item"] is None


# --------------------------------------------------------------------------------- learner/me
def test_learner_me_shows_bands_only_and_resets(dev):
    onboard(dev)
    for _ in range(6):
        item = choose_item(dev.services.content, dev.services.learner.repo, dev.student.student_id, "HBP.1",
                           None) or dev.services.content.item("HBP.1-q1")
        dev.client.post("/api/v1/check", json={"item_id": item.id, "choice": item.answer})
    prof = dev.client.get("/api/v1/learner/me").json()
    assert len(prof["topics"]) == 5 and "p_mastery" not in str(prof)
    assert bands(dev)["HBP.1"] in ("advanced", "mastered")
    assert dev.client.delete("/api/v1/learner/me").status_code == 204
    assert bands(dev)["HBP.1"] == "basic"
    assert dev.client.get("/api/v1/learner/me").json()["personalized"] is True  # consent stays


def test_preference_feedback(dev):
    r = dev.client.post("/api/v1/learner/me/preferences", json={"action": "more_detail"})
    assert r.status_code == 409  # no consent yet
    onboard(dev)
    r = dev.client.post("/api/v1/learner/me/preferences", json={"action": "more_detail"})
    assert r.json()["detail"] == "detailed"
    assert dev.client.post("/api/v1/learner/me/preferences", json={"action": "jump"}).status_code == 422


def test_learner_me_requires_a_student(dev):
    dev.client.cookies.clear()
    assert dev.client.get("/api/v1/learner/me").status_code == 401


# ------------------------------------------------------------------------------- end to end
def test_end_to_end_onboarding_ask_check_level_change(dev):
    """onboarding -> ask (check attached) -> wrong check answers lower the level -> basic-level prompt."""
    items = [i.id for i in diagnostic_items(dev.services.content, HBP)]
    res = onboard(dev, prefs={"sequencing": "example_first", "detail": "concise"},
                  answers=[{"item_id": i, "choice": key(dev, i)} for i in items])
    assert all(res["assessed"].values()) and len(res["assessed"]) == 6

    first = ask(dev)
    assert first["kc_level"] == "intermediate"
    assert first["check_item"] and first["check_item"]["kc_id"] == first["next_kc"]["kc_id"]
    sent = dev.local_llm.sent_text()
    assert level_partial("intermediate") in sent and style_partial("example_first", "concise") in sent

    before = bands(dev)
    order = {"basic": 0, "intermediate": 1, "advanced": 2, "mastered": 3}
    for kc in [f"HBP.{n}" for n in range(1, 7)]:
        # wrong answers on items other than the diagnostic one, until the KC is basic (BKT: 1, rule: up to 3)
        level = before[kc]
        for item in [i for i in dev.services.content.items(kc) if i.id not in items]:
            body = {"item_id": item.id, "choice": wrong(dev, item.id)}
            r = dev.client.post("/api/v1/check", json=body).json()
            assert r["correct"] is False and order[r["kc_level"]] <= order[level]  # never goes up
            level = r["kc_level"]
            if level == "basic":
                break
        assert level == "basic", kc
    assert before["HBP.1"] != "basic" and set(bands(dev).values()) == {"basic"}

    dev.local_llm.calls.clear()
    second = ask(dev, "Why does salt matter?")
    assert second["kc_level"] == "basic"
    assert level_partial("basic") in dev.local_llm.sent_text()
    # it follows next_kc; it may be the unanswered first one again, or none when every item of the KC was
    # answered in the last 24 h (the rule model needs more wrong answers to reach basic, using up the items)
    assert second["check_item"] is None or second["check_item"]["kc_id"] == second["next_kc"]["kc_id"]
