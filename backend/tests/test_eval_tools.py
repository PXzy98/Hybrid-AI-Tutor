"""Step 14: the evaluation tools (E2 simulator, E4 auditor, the audit and personalization switches).

The harnesses also run end to end in CI in smoke mode (see .github/workflows/ci.yml).
"""
import json
import sys
from pathlib import Path

import pytest

from app.core.config import get_settings
from app.core.schemas import CloudLabels, CloudRequest
from app.llm.audit import ECHO_ANSWER, RecordingCloudClient
from app.prompts import render_cloud
from tests.conftest import Api

EVAL = Path(__file__).resolve().parents[2] / "eval"
sys.path.insert(0, str(EVAL / "privacy-audit"))
sys.path.insert(0, str(EVAL / "learner-sim"))

import audit  # noqa: E402
import sim  # noqa: E402

REQ = CloudRequest(sanitized_question="Why is salt bad?", topic="high_blood_pressure", passages=[],
                   labels=CloudLabels(level="basic", sequencing="example_first", detail="concise"))
MC2 = "Blood pressure medication can be stopped once readings are normal."
SECRETS = audit.Secrets(identities=["Lucas Bergeron", "Bergeron", "p.intermediate"],
                        student_ids=["stu-abc123"], misconception_texts=[MC2])


def record(req: CloudRequest = REQ, **cloud_request_extra) -> dict:
    return {"cloud_request": {**req.model_dump(mode="json"), **cloud_request_extra}, "safety_retry": False,
            "messages": render_cloud(req)}


def kinds(findings) -> set[str]:
    return {f.kind for f in findings}


# ------------------------------------------------------------------------------ E4 auditor
def test_clean_request_has_no_findings():
    assert audit.analyze([record()], [audit.Ask("p", "Why is salt bad?", [], [0])], SECRETS) == []


@pytest.mark.parametrize(("rec", "kind"), [
    (record(student_id="stu-abc123"), "field"),
    (record(REQ.model_copy(update={"labels": REQ.labels})) | {"messages": [{"role": "user", "content": "x"}]},
     "field"),
    (record(REQ.model_copy(update={"sanitized_question": "Bergeron asks: why is salt bad?"})), "identity"),
    (record(REQ.model_copy(update={"passages": ["see HBP.6-q1"]})), "profile"),
    (record(REQ.model_copy(update={"passages": ["open: HBP.MC2"]})), "profile"),
    (record(REQ.model_copy(update={"passages": [f"Note: {MC2.lower()}"]})), "profile"),
    (record(REQ.model_copy(update={"sanitized_question": "I am 300418277, why?"})), "pii"),
])
def test_planted_leaks_are_found(rec, kind):
    ask = audit.Ask("p", "I am 300418277, why?", ["300418277"], [0])
    assert kind in kinds(audit.analyze([rec], [ask], SECRETS))


def test_a_typed_own_name_counts_as_pii_not_identity():
    rec = record(REQ.model_copy(update={"sanitized_question": "I'm Lucas Bergeron. Why?"}))
    ask = audit.Ask("p", "I'm Lucas Bergeron. Why?", ["Lucas Bergeron"], [0])
    found = audit.analyze([rec], [ask], SECRETS)
    assert kinds(found) == {"pii"}


def test_identity_in_storage_and_whole_words():
    db = "INSERT INTO request_log VALUES ('hi p.intermediate')"
    found = audit.storage_findings(db, "symptoms of Bergeronx", SECRETS, ["300418277"])
    assert [(f.kind, f.where) for f in found] == [("identity", "db")]


# ------------------------------------------------------------------------------ E2 simulator
def test_auc():
    assert sim.auc([(0.9, True), (0.1, False)]) == 1.0
    assert sim.auc([(0.1, True), (0.9, False)]) == 0.0
    assert sim.auc([(0.5, True), (0.5, False)]) == 0.5


@pytest.mark.parametrize("knowledge", ["bkt", "rule"])
def test_tiny_simulation_runs_through_the_real_learner_model(knowledge):
    base = get_settings()
    content = sim.load_content(base)
    assert "high_blood_pressure" in sim.simulated_topics(content)
    students = sim.make_students(content, "high_blood_pressure", 2, seed=1)
    res = sim.run(base, content, "high_blood_pressure", sim.RunConfig(knowledge, knowledge=knowledge,
                                                                      weak_evidence=True),
                  students, interactions=3, noise=0.1, seed=1)
    assert len(res.predictions) == 6 and len(res.abs_errors) == 6 * 3 * 2
    assert 0 <= res.mae <= 1 and 0 <= res.band_accuracy <= 1


# ------------------------------------------------------------------------------ switches
def test_recording_cloud_client_is_installed_through_config(make_client, tmp_path):
    log = tmp_path / "cloud.jsonl"
    with make_client({"llm": {"cloud": {"audit_log": str(log), "audit_echo": True}},
                      "routing": {"stub_score": 1.0}}) as client:
        api = Api(client)
        assert isinstance(api.services.cloud_llm, RecordingCloudClient)
        api.make_student()
        api.login("alice")
        body = client.post("/api/v1/ask", json={"topic": "high_blood_pressure",
                                                "question": "Why is salt bad for blood pressure?"}).json()
    assert body["route_target"] == "cloud" and body["model_used"] == "audit-echo"
    assert body["answer"].startswith(ECHO_ANSWER.split("<")[0])
    rec = json.loads(log.read_text(encoding="utf-8").splitlines()[0])
    assert set(rec["cloud_request"]) == set(CloudRequest.model_fields)
    assert rec["messages"] == render_cloud(CloudRequest.model_validate(rec["cloud_request"]))


def test_without_audit_config_the_plain_cloud_client_is_used(api):
    assert not isinstance(api.services.cloud_llm, RecordingCloudClient)


def test_personalization_switch(make_client):
    with make_client({"learner": {"personalize": False}}) as client:
        api = Api(client)
        api.make_student()
        api.login("alice")
        api.services.learner.set_consent(api.services.accounts.list_students()[0].student_id, True)
        client.post("/api/v1/ask", json={"topic": "high_blood_pressure", "question": "Why two numbers?"})
    assert "Teaching level for this student" not in api.local_llm.last_messages[0]["content"]
