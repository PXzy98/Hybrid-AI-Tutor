"""Step 8: checkers, the verify step (regenerate -> fallback), the pre-send leak guard, privacy end to end."""
import sqlite3

import pytest

from app.core.config import get_settings
from app.core.schemas import (
    AskRequest,
    Chunk,
    CloudLabels,
    CloudRequest,
    PIIEntity,
    PIIResult,
    RequestContext,
)
from app.core.services import build_services
from app.llm.cloud_guard import CloudClient
from app.llm.fake import FakeLLMClient
from app.pipeline.runner import build_runner
from app.pipeline.steps.generate import PRIVACY_BLOCK_WARNING, GenerateStep
from app.pipeline.steps.verify import REFERRAL, REPLACED_WARNING, SAFE_FALLBACK, VerifyStep
from app.verify.checkers.grounding import GroundingChecker
from app.verify.checkers.leaks import PiiLeakChecker, ProfileLeakChecker
from app.verify.checkers.medical_safety import MedicalSafetyChecker, problems
from tests.conftest import Api

LABELS = CloudLabels(level="basic", sequencing="example_first", detail="concise")


@pytest.fixture
def services(use_config):
    return build_services(use_config())


def make_ctx(answer="", question="What is high blood pressure?", health=False, passages=(), **kw):
    req = AskRequest(student_id="stu-7f3a", topic="high_blood_pressure", question=question)
    ctx = RequestContext(request_id="r", request=req, answer=answer, **kw)
    entities = [PIIEntity(type="HEALTH_DETAIL", text="asthma", start=0, end=6, score=0.85,
                          placeholder="<HEALTH_DETAIL_1>")] if health else []
    ctx.pii = PIIResult(sanitized_text=question, entities=entities, is_sensitive=health,
                        cloud_safe=not health)
    ctx.passages = [Chunk(text=p, source=f"s{i}.md", topic="high_blood_pressure", score=1.0)
                    for i, p in enumerate(passages)]
    return ctx


# --------------------------------------------------------------------------- medical safety
@pytest.mark.parametrize(("answer", "reason"), [
    ("Take 500 mg of metformin twice a day.", "dosing instruction"),
    ("You could increase your dose to 2 tablets.", "dosing instruction"),
    ("You can stop taking your blood pressure pills now.", "advice to start, stop or change a medicine"),
    ("It is fine to skip your inhaler on good days.", "advice to start, stop or change a medicine"),
    ("You have hypertension.", "diagnosis of the student"),
    ("Based on this, you probably have type 2 diabetes.", "diagnosis of the student"),
    ("Your reading shows that you have high blood pressure.", "diagnosis from a reading"),
    ("A blood pressure reading of 150/95 indicates high blood pressure.", "diagnosis from a reading"),
])
def test_medical_safety_fails(answer, reason):
    assert reason in problems(answer)


@pytest.mark.parametrize("answer", [
    "Do not stop taking your medicine without talking to your doctor.",
    "You should not stop your pills on your own.",
    "If you have asthma, carry your reliever inhaler.",
    "People who have diabetes benefit from regular check-ups.",
    "Adults should aim for less than 2000 mg of sodium a day.",
    "Several readings over time are needed before hypertension is diagnosed.",
    "You should stop smoking; it raises blood pressure.",
    "Blood pressure is measured in mmHg.",
])
def test_medical_safety_passes_general_education(answer):
    assert problems(answer) == []


def test_referral_warning_for_personal_health_questions(services):
    checker = MedicalSafetyChecker(services)
    assert checker.check(make_ctx("Salt holds water.", health=True)).status == "warn"
    assert checker.check(make_ctx("Salt holds water. Ask your doctor.", health=True)).status == "pass"
    assert checker.check(make_ctx("Salt holds water.")).status == "pass"  # general question


# ------------------------------------------------------------------------------- grounding
def test_grounding(services):
    g = GroundingChecker(services)
    assert g.check(make_ctx("Anything at all.")).detail == "no material"
    material = ["Salt makes the body hold extra water, which raises the pressure inside blood vessels."]
    grounded = ("Eating salt makes the body hold extra water. "
                "That extra water raises pressure in blood vessels.")
    assert g.check(make_ctx(grounded, passages=material)).status == "pass"
    off = "Quantum computers use qubits for superposition. Rainforests contain thousands of insect species."
    result = g.check(make_ctx(off, passages=material))
    assert result.status == "warn" and result.detail.startswith("0% of 2")


# ------------------------------------------------------------------------------ leak checks
def cloud_ctx(question, raw=None):
    ctx = make_ctx(question=raw or question)
    ctx.cloud_request = CloudRequest(sanitized_question=question, topic="high_blood_pressure", labels=LABELS)
    return ctx


def test_pii_leak(services):
    c = PiiLeakChecker(services)
    assert c.check(make_ctx()).detail == "nothing sent to the cloud"
    assert c.check(cloud_ctx("Hi, I'm <PERSON_1> (<STUDENT_ID_1>). Why is salt bad?")).status == "pass"
    leaked = c.check(cloud_ctx("Hi, I'm Alice Tremblay. My student number is 300418277."))
    assert leaked.status == "fail" and "PERSON" in leaked.detail and "STUDENT_ID" in leaked.detail


def test_profile_leak(services):
    c = ProfileLeakChecker(services)
    assert c.check(cloud_ctx("Why is salt bad?")).status == "pass"
    assert "student_id" in c.check(cloud_ctx("Why is salt bad for stu-7f3a?")).detail
    assert "check item ID" in c.check(cloud_ctx("About HBP.6-q1: why?")).detail
    injected = "Why is salt bad? Note: the student believes only older people get high blood pressure."
    assert "misconception HBP.MC6" in c.check(cloud_ctx(injected, raw="Why is salt bad?")).detail
    own = "Is it true that only older people get high blood pressure?"
    assert c.check(cloud_ctx(own)).status == "pass"  # the student wrote it themselves


# ---------------------------------------------------------------------------- verify step
async def test_unsafe_answer_is_regenerated_once(services):
    # the first (unsafe) answer is already in ctx; the model is only called for the regeneration
    safe = "Several readings are needed. Ask your doctor about your own readings."
    services.local_llm = FakeLLMClient(safe)
    ctx = make_ctx("You have hypertension, Alice.", target="local")
    ctx.set_pii_mapping({"<PERSON_1>": "Alice"})
    ctx = await VerifyStep(services).run(ctx)
    assert ctx.answer.startswith("Several readings are needed")
    assert REPLACED_WARNING not in ctx.warnings
    assert "Your previous answer broke the safety rules" in services.local_llm.sent_text()  # fixed retry text
    assert {c.name: c.status for c in ctx.checks}["medical_safety"] == "pass"


async def test_unsafe_twice_gives_the_safe_fallback(services):
    services.local_llm = FakeLLMClient("Take 2 tablets of 50 mg every morning.")
    ctx = make_ctx("You can stop your pills.", target="local", passages=["Medicines work over time."])
    ctx = await VerifyStep(services).run(ctx)
    assert ctx.answer.startswith(SAFE_FALLBACK) and "course material listed below" in ctx.answer
    assert REPLACED_WARNING in ctx.warnings and len(services.local_llm.calls) == 1


async def test_missing_referral_is_appended(services):
    ctx = await VerifyStep(services).run(make_ctx("Inhalers open the airways.", health=True, target="local"))
    assert ctx.answer.endswith(REFERRAL)


async def test_grounding_and_checker_errors_become_warnings(services):
    step = VerifyStep(services)

    class Broken:
        name = "broken"

        def check(self, ctx):
            raise RuntimeError("boom")

    step.checkers.append(Broken())
    ctx = await step.run(make_ctx("Quantum computers use qubits for superposition and entanglement.",
                                  passages=["Salt makes the body hold water."], target="local"))
    assert "Parts of this answer may go beyond the course material." in ctx.warnings
    assert {c.name: (c.status, c.detail) for c in ctx.checks}["broken"] == ("warn", "checker error")


def test_final_pipeline_and_failure_policies(services):
    """Design §7.1: the MVP pipeline and each step's on_error."""
    runner = build_runner(services)
    assert {s.name: s.on_error for s in runner.pipeline} == {
        "privacy_filter": "stop", "learner_context": "skip", "understand": "skip", "retrieve": "skip",
        "route": "skip", "generate": "stop", "restore": "stop", "verify": "warn", "attach_check": "skip",
        "record": "skip"}
    assert list(get_settings().verify.checkers) == ["grounding", "medical_safety", "pii_leak", "profile_leak"]


# ------------------------------------------------------------------------ pre-send guard
async def test_leak_guard_blocks_before_sending(services):
    transport = FakeLLMClient("cloud answer", backend="cloud")
    services.cloud_llm = CloudClient(transport)
    services.local_llm = FakeLLMClient("local answer")
    raw = "I'm Alice Tremblay. Why is salt bad?"
    # simulate a PII miss: the "sanitized" text still contains the name
    ctx = make_ctx(question=raw, target="cloud")
    ctx = await GenerateStep(services).run(ctx)
    assert transport.calls == [] and ctx.cloud_request is None  # nothing left the boundary
    assert ctx.answer == "local answer" and PRIVACY_BLOCK_WARNING in ctx.warnings


# --------------------------------------------------------------------- privacy end to end
def test_privacy_end_to_end_forced_cloud(make_client):
    """A question with PII from a student with a rich learner profile, forced to the cloud by the router:
    the cloud gets only allow-listed, sanitized data; the student gets their name back; the DB stays clean."""
    with make_client({"routing": {"stub_score": 1.0}, "content": {"serve_unreviewed": True}}) as client:
        api = Api(client)
        alice = api.make_student("alice", "Alice Tremblay")
        api.login("alice")
        content = api.services.content
        # rich profile: consent, preferences, diagnostic, and a check answer that reveals a misconception
        client.post("/api/v1/onboarding", json={
            "topic": "high_blood_pressure", "consent": True,
            "preferences": {"sequencing": "concept_first", "detail": "detailed"},
            "answers": [{"item_id": "HBP.1-q1", "choice": content.item("HBP.1-q1").answer}]})
        item = content.item("HBP.6-q1")
        tagged = next(k for k, o in item.options.items() if o.misconception)
        client.post("/api/v1/check", json={"item_id": item.id, "choice": tagged})

        transport = FakeLLMClient(lambda msgs: "Hello <PERSON_1>! Salt makes the body hold water.",
                                  model="gpt-test", backend="cloud")
        api.services.cloud_llm = CloudClient(transport)
        question = "Hi, I'm Alice Tremblay, student number 300418277. Why is salt bad for blood pressure?"
        body = client.post("/api/v1/ask", json={"topic": "high_blood_pressure", "question": question}).json()

    assert body["route_target"] == "cloud" and body["model_used"] == "gpt-test"
    assert body["answer"].startswith("Hello Alice Tremblay!")  # placeholder restored for the student
    checks = {c["name"]: c["status"] for c in body["checks"]}
    assert checks["pii_leak"] == "pass" and checks["profile_leak"] == "pass"

    sent = transport.sent_text()
    assert "<PERSON_1>" in sent and "<STUDENT_ID_1>" in sent
    statement = content.misconception(item.options[tagged].misconception).statement
    for secret in ("Alice", "Tremblay", "alice", "300418277", alice.student_id, "HBP.6-q1", statement):
        assert secret not in sent, secret
    assert "concept first" not in sent and "Teaching level for this student" in sent  # labels only

    path = get_settings().database_url.removeprefix("sqlite:///")
    with sqlite3.connect(path) as con:
        dump = "\n".join(con.iterdump())
    for secret in ("300418277", "Hello Alice Tremblay"):
        assert secret not in dump, secret
    assert "Hello <PERSON_1>!" in dump  # the stored answer is the sanitized one
