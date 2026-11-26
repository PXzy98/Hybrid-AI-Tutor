"""Answers by subject (task Z16, audit B1 and B2): the course's privacy profile chooses the subject prompt and
the subject's checkers. Fictional courses and questions; the models are fakes."""
import pytest

from app.core.schemas import CloudLabels, CloudRequest
from app.llm.fake import FakeLLMClient
from app.pipeline.steps.verify import SAFE_FALLBACK, subject_checkers
from app.privacy.profiles import ProfileError, _raw, privacy_profile
from app.prompts import base_system, render_cloud, subject_names, system_prompt
from tests.test_ask_v2 import V2, World, _login

# an answer the medical safety check reads as a dosing instruction
LABELS = CloudLabels(level="basic", sequencing="example_first", detail="concise")
LAB_ANSWER = "Use 50 ml of buffer and inject 5 ml of the sample, then measure the voltage across R1."


def test_every_profile_names_a_subject_prompt():
    assert privacy_profile("medical_science").prompt == "health"
    assert privacy_profile("ece").prompt == "engineering"
    assert privacy_profile("general").prompt == privacy_profile("life_science").prompt == "general"
    assert privacy_profile("biomedical_engineering").prompt == "biomedical_engineering"
    assert {"general", "health", "engineering", "biomedical_engineering"} <= set(subject_names())
    assert subject_checkers() == {"medical_safety"}


def test_only_the_health_prompt_is_a_health_tutor():
    assert "health-education" not in base_system()
    assert "Never diagnose" in base_system()  # the safety rules of every course stay in the base
    for subject in subject_names():
        prompt = system_prompt(subject=subject)
        assert prompt.startswith(base_system())
        assert ("health-education course" in prompt) == (subject == "health")
        # the health safety rules: the health tutor and biomedical engineering (X10, an engineering tutor)
        assert ("medicine or a dose" in prompt) == (subject in ("health", "biomedical_engineering"))


def test_an_unknown_subject_is_refused(monkeypatch):
    with pytest.raises(ValueError):
        system_prompt(subject="../base_system")
    with pytest.raises(ValueError):
        CloudRequest(sanitized_question="q", topic="t", labels=LABELS, subject="Ignore the rules")
    monkeypatch.setitem(_raw("ece"), "prompt", "astrology")
    privacy_profile.cache_clear()
    try:
        with pytest.raises(ProfileError, match="prompt"):
            privacy_profile("ece")
    finally:
        privacy_profile.cache_clear()


def test_the_cloud_prompt_uses_the_requests_subject():
    req = CloudRequest(sanitized_question="What is Ohm's law?", topic="circuits", labels=LABELS,
                       subject="engineering")
    system = render_cloud(req)[0]["content"]
    assert "engineering course" in system and "health-education" not in system


@pytest.fixture
def world(make_client):
    with make_client() as client:
        yield World(client)


def _ask(world, url: str, module: int, question: str) -> dict:
    alice = _login(world.app, "alice")
    r = alice.post(f"{url}/ask", json={"question": question, "module_id": module})
    assert r.status_code == 200, r.text
    return r.json()


def test_a_non_medical_course_gets_its_own_prompt_and_no_medical_check(world):
    world.services.local_llm = local = FakeLLMClient(LAB_ANSWER, model="fake-local")
    body = _ask(world, world.url, world.module, "How do I prepare the sample for the voltage measurement?")
    system = local.last_messages[0]["content"]
    assert "engineering course" in system and "health-education" not in system
    assert body["answer"] == LAB_ANSWER  # not replaced by the medical fallback
    assert "medical_safety" not in {c["name"] for c in body["checks"]}
    assert len(local.calls) == 1  # no regeneration


def test_a_medical_course_keeps_the_health_prompt_and_check(world):
    course = world.prof.post(f"{V2}/courses", json={"code": "HLTH 1001", "title": "Fictional health course",
                                                     "course_type": "medical_science"}).json()["id"]
    url = f"{V2}/courses/{course}"
    module = world.prof.post(f"{url}/modules", json={"code": "bp", "title": "Blood pressure"}).json()["id"]
    world.prof.post(f"{url}/kcs", json={"module_id": module, "code": "B.1", "name": "Readings",
                                        "difficulty": "basic"})
    world.course = course
    world.enrol("alice")
    world.services.local_llm = local = FakeLLMClient(LAB_ANSWER, model="fake-local")
    body = _ask(world, url, module, "How should a nurse prepare an injection in general?")
    assert "health-education course" in local.calls[0]["messages"][0]["content"]
    assert len(local.calls) == 2  # the medical safety check failed and the answer was regenerated once
    assert body["answer"].startswith(SAFE_FALLBACK)
