"""Step 13: instructor dashboard API (design §3, §8.3, §9)."""
import uuid
from contextlib import ExitStack

import pytest

from app.admin.summary import suppress
from app.core.schemas import Evidence
from app.learner.knowledge.rule import RuleKnowledgeModel
from app.llm.cloud_guard import CloudClient
from app.llm.fake import FakeLLMClient
from tests.conftest import Api

HBP = "high_blood_pressure"
ADMIN = "/api/v1/admin"


@pytest.fixture
def dash(make_client, tmp_path):
    """`dash(overrides)`: the app with an instructor (logged in) and a student account."""
    with ExitStack() as stack:
        def _make(overrides: dict | None = None) -> Api:
            cfg = {"content": {"serve_unreviewed": True},
                   "rag": {"materials_dir": str(tmp_path / "materials")}, **(overrides or {})}
            api = Api(stack.enter_context(make_client(cfg)))
            api.make_student("alice")
            api.make_instructor("prof")
            api.login("prof")
            return api

        yield _make


def config(api) -> dict:
    r = api.client.get(f"{ADMIN}/config")
    assert r.status_code == 200, r.text
    return r.json()


def put_config(api, expect=200, **changes) -> dict:
    values = {**config(api)["values"], **changes}
    r = api.client.put(f"{ADMIN}/config", json=values)
    assert r.status_code == expect, r.text
    return r.json()


def ask_as_student(api, question="Why is salt bad for blood pressure?") -> dict:
    api.login("alice")
    r = api.client.post("/api/v1/ask", json={"topic": HBP, "question": question})
    assert r.status_code == 200, r.text
    api.login("prof")
    return r.json()


# ------------------------------------------------------------------------------ access
def test_every_admin_route_needs_the_instructor(dash):
    api = dash()
    routes = [(m.upper(), path) for path, ops in api.client.app.openapi()["paths"].items()
              if path.startswith(ADMIN) for m in ops]
    assert len(routes) >= 10
    for who, code in (("alice", 403), (None, 401)):
        if who:
            api.login(who)
        else:
            api.client.cookies.clear()
        for method, path in routes:
            url = path.replace("{account_id}", "1").replace("{topic}", HBP)
            r = api.client.request(method, url, params={"topic": HBP})
            assert r.status_code == code, (who, method, path, r.status_code)


# ------------------------------------------------------------------------------ config
def test_config_shows_the_runtime_subset(dash):
    c = config(dash())
    assert c["values"] == {"routing_threshold": 0.6, "checkers": ["grounding", "medical_safety", "pii_leak",
                                                                  "profile_leak"],
                           "knowledge": c["values"]["knowledge"], "weak_evidence": False,
                           "levels": {"basic_below": 0.4, "advanced_above": 0.7, "hysteresis": 0.05}}
    assert {"bkt", "rule"} <= set(c["options"]["knowledge_models"])
    assert c["options"]["required_checkers"] == ["medical_safety", "pii_leak", "profile_leak"]
    assert c["history"] == []


def test_threshold_change_takes_effect_on_the_next_ask(dash):
    api = dash({"routing": {"stub_score": 0.5}})
    api.services.cloud_llm = CloudClient(FakeLLMClient("Cloud answer.", model="gpt-test", backend="cloud"))
    assert ask_as_student(api)["route_target"] == "local"  # 0.5 < 0.6
    put_config(api, routing_threshold=0.4)
    assert ask_as_student(api)["route_target"] == "cloud"  # no restart


def test_checkers_and_knowledge_model_are_swapped_live(dash):
    api = dash()
    put_config(api, checkers=["medical_safety", "pii_leak", "profile_leak"], knowledge="rule",
               weak_evidence=True)
    assert isinstance(api.services.learner.knowledge, RuleKnowledgeModel)
    assert api.services.settings.learner.weak_evidence is True
    names = [c["name"] for c in ask_as_student(api)["checks"]]
    assert "grounding" not in names and "medical_safety" in names


def test_invalid_changes_are_rejected(dash):
    api = dash()
    put_config(api, 422, checkers=["grounding", "pii_leak", "profile_leak"])  # medical_safety is required
    put_config(api, 422, checkers=["medical_safety", "pii_leak", "profile_leak", "nope"])
    put_config(api, 422, knowledge="magic")
    put_config(api, 422, levels={"basic_below": 0.8, "advanced_above": 0.7, "hysteresis": 0.05})
    put_config(api, 422, routing_threshold=1.5)
    assert config(api)["history"] == []


def test_history_is_recorded_and_survives_a_restart(dash, make_client):
    api = dash()
    put_config(api, routing_threshold=0.75)
    put_config(api, routing_threshold=0.75)  # no change: no new history row
    history = config(api)["history"]
    assert len(history) == 1 and history[0]["changed"] == ["routing_threshold"]
    with make_client({"content": {"serve_unreviewed": True}}) as client:  # same database, new process
        assert client.app.state.services.settings.routing.threshold == 0.75


# ------------------------------------------------------------------------------ class summary
def test_suppression_rules():
    assert suppress({"basic": 7, "intermediate": 0, "advanced": 6}, 5) == {"basic": 7, "intermediate": 0,
                                                                           "advanced": 6}
    # one small cell alone could be computed from the total: the next smallest is suppressed too
    assert suppress({"basic": 7, "intermediate": 2, "advanced": 6}, 5) == {"basic": 7, "intermediate": None,
                                                                           "advanced": None}
    both_small = suppress({"basic": 3, "intermediate": 2, "advanced": 6}, 5)
    assert both_small == {"basic": None, "intermediate": None, "advanced": 6}


def seed_class(api, n: int) -> list[str]:
    """n consenting students: all answered HBP.1 correctly; the first 6 hold MC5 open, the first 2 MC4."""
    learner, sids = api.services.learner, []
    for i in range(n):
        sid = f"stu-{uuid.uuid4().hex[:8]}"
        learner.set_consent(sid, True)
        learner.observe(sid, Evidence(kc_id="HBP.1", kind="diagnostic", correct=True, source="onboarding"))
        if i < 6:
            learner.tracker.distractor_chosen(sid, "HBP.MC5")
        if i < 2:
            learner.tracker.distractor_chosen(sid, "HBP.MC4")
        sids.append(sid)
    return sids


def summary(api) -> dict:
    r = api.client.get(f"{ADMIN}/class-summary", params={"topic": HBP})
    assert r.status_code == 200, r.text
    return r.json()


def test_small_class_is_fully_suppressed(dash):
    api = dash()
    seed_class(api, 3)
    s = summary(api)
    assert s["suppressed"] is True and s["students"] is None and s["kcs"] == [] and s["misconceptions"] == []


def test_class_summary_counts_and_suppression(dash):
    api = dash()
    sids = seed_class(api, 7)
    s = summary(api)
    assert s["suppressed"] is False and s["students"] == 7 and s["min_group"] == 5
    rows = {k["kc_id"]: k["counts"] for k in s["kcs"]}
    assert sum(v for v in rows["HBP.1"].values() if v) == 7 and rows["HBP.1"]["not_assessed"] == 0
    assert rows["HBP.2"] == {"not_assessed": 7, "basic": 0, "intermediate": 0, "advanced": 0, "mastered": 0}
    assert [(m["misconception_id"], m["students"]) for m in s["misconceptions"]] == [("HBP.MC5", 6)]
    assert s["misconceptions_hidden"] == 1  # MC4: only 2 students
    body = api.client.get(f"{ADMIN}/class-summary", params={"topic": HBP}).text
    assert not any(sid in body for sid in sids)


def test_unknown_topic(dash):
    assert dash().client.get(f"{ADMIN}/class-summary", params={"topic": "nope"}).status_code == 404


# ------------------------------------------------------------------------------ logs
def test_logs_are_sanitized_paginated_and_carry_stats(dash):
    api = dash()
    for _ in range(3):
        ask_as_student(api, "Hi, I'm Alice Tremblay. Why is salt bad for blood pressure?")
    r = api.client.get(f"{ADMIN}/logs", params={"page_size": 2})
    assert r.status_code == 200
    page = r.json()
    assert page["total"] == 3 and len(page["entries"]) == 2
    assert page["stats"]["local"] == 3 and page["stats"]["cloud_share"] == 0.0
    assert page["stats"]["latency_p50_ms"] is not None
    entry = page["entries"][0]
    assert "Alice" not in r.text and "<PERSON_1>" in entry["sanitized_question"]
    assert "student_id" not in entry and "session_id" not in entry
    assert api.services.accounts.list_students()[0].student_id not in r.text
    assert len(api.client.get(f"{ADMIN}/logs", params={"page": 2, "page_size": 2}).json()["entries"]) == 1


# ------------------------------------------------------------------------------ content and materials
def upload(api, name="notes.md", data=b"# Salt\nSalt raises blood pressure.", **params):
    return api.client.post(f"{ADMIN}/topics/{HBP}/materials", files={"file": (name, data, "text/markdown")},
                           params=params)


def test_upload_is_stored_and_listed(dash, tmp_path):
    api = dash()
    r = upload(api)
    assert r.status_code == 201, r.text
    assert r.json()["ingested"] is False  # the stub retriever has no ingest()
    assert (tmp_path / "materials" / HBP / "notes.md").read_bytes().startswith(b"# Salt")
    status = api.client.get(f"{ADMIN}/content").json()
    hbp = next(t for t in status["topics"] if t["topic"] == HBP)
    assert [m["name"] for m in hbp["materials"]] == ["notes.md"]
    assert (hbp["kcs"], hbp["items"], hbp["items_reviewed"], hbp["misconceptions"]) == (6, 24, 0, 12)
    assert status["serve_unreviewed"] is True


def test_upload_rules(dash, tmp_path):
    api = dash()
    assert upload(api, "run.exe").status_code == 422
    assert upload(api, "empty.md", b"").status_code == 422
    assert upload(api).status_code == 201
    assert upload(api).status_code == 409
    assert upload(api, replace=True).status_code == 201
    assert upload(api, "../../evil.md").status_code == 201  # the path part is dropped
    assert (tmp_path / "materials" / HBP / "evil.md").exists() and not (tmp_path / "evil.md").exists()
    r = api.client.post(f"{ADMIN}/topics/nope/materials", files={"file": ("a.md", b"x", "text/markdown")})
    assert r.status_code == 404


def test_upload_calls_ingest_when_the_retriever_has_it(dash):
    api = dash()
    calls = []

    class Indexing:
        def retrieve(self, *a, **kw):
            return []

        def ingest(self, topic, path):
            calls.append((topic, path))

    api.services.retriever = Indexing()
    assert upload(api).json()["ingested"] is True
    assert calls and calls[0][0] == HBP and calls[0][1].endswith("notes.md")
