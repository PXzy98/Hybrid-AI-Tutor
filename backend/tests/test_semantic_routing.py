"""Policy, evidence and integration tests; no remote APIs or model downloads."""

import json
from datetime import UTC, datetime, timedelta

import numpy as np
import pytest

from app.core.config import REPO_ROOT, RoutingConfig
from app.core.schemas import Chunk, PIIResult, RouteInput, SemanticAnalysis
from app.pipeline.steps.generate import CLOUD_MISSING_WARNING, LOCAL_CAPABILITY_NOTE
from app.routing.evidence import assess_evidence, select_passages
from app.routing.semantic import SemanticRouter


def input_for(question="Explain hypertension.", passages=(), method="lr", **kw):
    return RouteInput(
        sanitized_question=question,
        topic="high_blood_pressure",
        pii=PIIResult(sanitized_text=question),
        passage_count=len(passages),
        passages=list(passages),
        method=method,
        retrieval_status="returned",
        **kw,
    )


def analysis(**kw):
    return SemanticAnalysis(method="lr", reliable=True, cloud_probability=0.1, requires_evidence=True, **kw)


def chunk(text="Hypertension means persistently high blood pressure.", **kw):
    return Chunk(text=text, source="lecture.md", topic="high_blood_pressure", score=999, **kw)


def test_empty_passages_never_become_full_coverage():
    result = assess_evidence(input_for(), analysis(), RoutingConfig())
    assert result.status == "empty"
    assert result.coverage == 0 and result.accepted_indices == []


@pytest.mark.parametrize("state", ["disabled", "error", "unknown"])
def test_unavailable_rag_is_explicit(state):
    x = input_for()
    x.retrieval_status = state
    assert assess_evidence(x, analysis(), RoutingConfig()).status == "unavailable"


def test_no_evidence_required_is_not_the_same_as_sufficient():
    a = analysis()
    a.requires_evidence = False
    r = assess_evidence(input_for(), a, RoutingConfig())
    assert r.status == "not_required" and r.coverage == 0


def test_topic_similarity_and_retrieval_score_do_not_prove_support(monkeypatch):
    # Very high retrieval and reranker scores, but low answerability.
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores",
        lambda name, pairs, cfg: np.full(len(pairs), 0.99 if name == cfg.relevance_model else 0.1),
    )
    r = assess_evidence(input_for(passages=[chunk()]), analysis(), RoutingConfig())
    assert r.status == "insufficient" and not r.accepted_indices


def test_partial_support_cannot_be_averaged_into_sufficiency(monkeypatch):
    def score(name, pairs, cfg):
        if name == cfg.relevance_model:
            return np.ones(len(pairs))
        return np.array([0.99 if "systolic" in q.lower() else 0.1 for q, _ in pairs])

    monkeypatch.setattr("app.routing.evidence.pair_scores", score)
    x = input_for("What is systolic pressure? What causes diabetes?", [chunk()])
    r = assess_evidence(x, analysis(), RoutingConfig())
    assert r.coverage == 0.5 and r.status == "insufficient"


def test_supported_course_material_can_enable_local_after_rag_connects(use_config, monkeypatch):
    use_config({"routing": {"impl": "semantic"}})
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores", lambda name, pairs, cfg: np.full(len(pairs), 0.99)
    )
    x = input_for(passages=[chunk()])
    r = SemanticRouter().decide(x, analysis(), 0.6)
    assert r.target == "local" and r.evidence.status == "sufficient"
    assert r.accepted_indices == [0]


def test_capability_failure_cannot_be_overruled_by_good_evidence(use_config):
    use_config({"routing": {"impl": "semantic"}})
    a = analysis()
    a.cloud_probability = 0.95
    r = SemanticRouter().decide(input_for(passages=[chunk()]), a, 0.6)
    assert r.target == "cloud" and not r.accepted_indices


def test_uncertain_and_out_of_distribution_go_cloud(use_config):
    use_config({"routing": {"impl": "semantic"}})
    router = SemanticRouter()
    a = analysis()
    a.requires_evidence = False
    a.cloud_probability = 0.57
    assert router.decide(input_for(), a, 0.6).target == "cloud"
    a.cloud_probability = 0.01
    a.reliable = False
    assert router.decide(input_for(), a, 0.6).target == "cloud"


def test_missing_evidence_models_are_not_a_pass(monkeypatch):
    def fail(*args):
        raise OSError("missing model")

    monkeypatch.setattr("app.routing.evidence.pair_scores", fail)
    r = assess_evidence(input_for(passages=[chunk()]), analysis(), RoutingConfig())
    assert r.status == "uncertain" and r.coverage == 0


@pytest.mark.parametrize(
    "metadata",
    [
        {"approved": False},
        {"valid_until": "2000-01-01"},
        {"valid_until": "not-a-date"},
    ],
)
def test_invalid_or_unapproved_sources_rejected(metadata):
    r = assess_evidence(input_for(passages=[chunk(metadata=metadata)]), analysis(), RoutingConfig())
    assert r.status == "insufficient"


def test_freshness_requires_verified_current_metadata(monkeypatch):
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores", lambda name, pairs, cfg: np.full(len(pairs), 0.99)
    )
    a = analysis(requires_fresh_evidence=True)
    assert assess_evidence(input_for(passages=[chunk()]), a, RoutingConfig()).status == "insufficient"
    recent = datetime.now(UTC).isoformat()
    c = chunk(metadata={"verified_current": True, "verified_at": recent})
    assert assess_evidence(input_for(passages=[c]), a, RoutingConfig()).status == "sufficient"
    c.metadata["verified_at"] = (datetime.now(UTC) - timedelta(days=100)).isoformat()
    assert assess_evidence(input_for(passages=[c]), a, RoutingConfig()).status == "insufficient"


def test_portable_weights_match_calibrated_sklearn():
    from app.routing.models import HEADS, predict_heads
    from app.routing.train import fit_heads, portable_arrays, read_rows

    rows = read_rows(REPO_ROOT / "data/routing/seed.jsonl")
    x = np.random.default_rng(42).normal(size=(len(rows), 6))
    for method in ("lr", "svm"):
        models = fit_heads(x, rows, method)
        arrays = portable_arrays(models, x)
        values = predict_heads(x[0], {"dimension": 6}, arrays)
        for head in HEADS:
            assert values[head] == pytest.approx(models[head].predict_proba(x[:1])[0, 1], abs=1e-10)


PIPELINE = [
    "privacy_filter",
    "understand",
    "learner_context",
    "analyze_route",
    "retrieve",
    "route",
    "generate",
    "restore",
    "verify",
    "attach_check",
    "record",
]


def semantic_api(make_client, monkeypatch, extra=None):
    from tests.conftest import Api

    monkeypatch.setattr(SemanticRouter, "embed", lambda self, question: np.zeros(3))

    def classify(self, vector, method, course_type=None):
        return SemanticAnalysis(
            method=method,
            cloud_probability=0.1,
            evidence_probability=0.1,
            requires_evidence=False,
            reliable=True,
            nearest_similarity=0.9,
        )

    monkeypatch.setattr(SemanticRouter, "classify", classify)
    cm = make_client({"routing": {"impl": "semantic", **(extra or {})}, "pipeline": PIPELINE})
    client = cm.__enter__()
    api = Api(client)
    api.make_student()
    api.login("alice")
    return cm, api


def stream_events(response):
    events = []
    for frame in response.text.split("\n\n"):
        if frame.startswith("event:"):
            lines = frame.splitlines()
            events.append((lines[0][7:], json.loads(lines[1][6:])))
    return events


def test_stream_shows_real_stages_and_requested_method(make_client, monkeypatch):
    cm, api = semantic_api(make_client, monkeypatch)
    try:
        r = api.client.post(
            "/api/v1/ask/stream",
            json={"topic": "high_blood_pressure", "question": "Explain pressure.", "routing_method": "svm"},
        )
        assert r.status_code == 200 and r.headers["x-accel-buffering"] == "no"
        ev = stream_events(r)
        assert ev[0][0] == "meta" and ev[0][1]["method"] == "svm"
        stages = {v["stage"] for k, v in ev if k == "progress"}
        assert {"embedding", "classification", "retrieval", "evidence", "decision", "generation"} <= stages
        reply = next(v for k, v in ev if k == "result")
        assert reply["routing_details"]["method"] == "svm"
        assert reply["route_target"] == "local"
        assert all(v["duration_ms"] >= 0 for k, v in ev if k == "progress" and v["duration_ms"] is not None)
        assert "Explain pressure." not in json.dumps([v for k, v in ev if k == "progress"])
    finally:
        cm.__exit__(None, None, None)


def test_teacher_toggle_is_enforced_server_side_and_persisted(make_client, monkeypatch):
    cm, api = semantic_api(make_client, monkeypatch)
    try:
        api.make_instructor()
        api.login("prof")
        config = api.client.get("/api/v1/admin/config").json()["values"]
        config["show_routing_progress"] = False
        assert api.client.put("/api/v1/admin/config", json=config).status_code == 200
        from app.core.services import build_services

        assert build_services().effective().show_routing_progress is False  # stored: survives a restart
        api.login("alice")
        assert api.client.get("/api/v1/routing/options").json()["show_progress"] is False
        body = {"topic": "high_blood_pressure", "question": "Explain pressure."}
        ev = stream_events(api.client.post("/api/v1/ask/stream", json=body))
        assert not any(k == "progress" for k, _ in ev)
        reply = next(v for k, v in ev if k == "result")
        assert reply["routing_details"] is None and not reply["routing_progress"]
        assert api.client.get("/api/v1/admin/config").status_code == 403
    finally:
        cm.__exit__(None, None, None)


def test_single_method_removal_updates_options_and_rejects_disabled_method(make_client, monkeypatch):
    cm, api = semantic_api(make_client, monkeypatch, {"enabled_methods": ["lr"]})
    try:
        options = api.client.get("/api/v1/routing/options").json()
        assert [m["id"] for m in options["methods"]] == ["lr"]
        body = {"topic": "high_blood_pressure", "question": "Explain pressure.", "routing_method": "svm"}
        assert api.client.post("/api/v1/ask", json=body).status_code == 422
        assert api.client.post("/api/v1/ask/stream", json=body).status_code == 422
    finally:
        cm.__exit__(None, None, None)


def test_cloud_unavailable_answers_locally_and_says_why(make_client, monkeypatch):
    """Team decision (TODO 1.3): no 503 when the cloud is missing; the local model answers and the student is
    told why, and that the router expected the cloud model to do better."""
    cm, api = semantic_api(make_client, monkeypatch)
    try:
        monkeypatch.setattr(
            SemanticRouter,
            "classify",
            lambda self, vector, method, course_type=None: SemanticAnalysis(
                method=method, reliable=True, cloud_probability=0.99
            ),
        )
        ev = stream_events(
            api.client.post(
                "/api/v1/ask/stream", json={"topic": "high_blood_pressure", "question": "Complex case."}
            )
        )
        reply = next(v for k, v in ev if k == "result")
        assert reply["route_target"] == "local" and api.local_llm.calls
        assert CLOUD_MISSING_WARNING in reply["warnings"] and LOCAL_CAPABILITY_NOTE in reply["warnings"]
    finally:
        cm.__exit__(None, None, None)


def test_rag_adapter_filters_evidence_before_prompt_and_sources(make_client, monkeypatch):
    from types import SimpleNamespace

    cm, api = semantic_api(make_client, monkeypatch)
    try:
        monkeypatch.setattr(SemanticRouter, "classify",
                            lambda self, vector, method, course_type=None: analysis())
        monkeypatch.setattr(
            "app.routing.evidence.pair_scores",
            lambda name, pairs, cfg: np.array([0.99 if "VALID" in text else 0.01 for _, text in pairs]),
        )
        # Old-style Chunk records still work without the new metadata field.
        good = chunk(text="VALID course definition of hypertension.")
        bad = chunk(text="REJECTED unrelated text.")
        bad.source = "unrelated.md"
        api.services.settings.rag.impl = "fixture"
        api.services.retriever = SimpleNamespace(retrieve=lambda *args: [good, bad])
        body = {"topic": "high_blood_pressure", "question": "Define hypertension from the course."}
        response = api.client.post("/api/v1/ask", json=body)
        assert response.status_code == 200, response.text
        reply = response.json()
        assert reply["route_target"] == "local"
        assert [s["source"] for s in reply["sources"]] == ["lecture.md"]
        prompt = str(api.local_llm.calls)
        assert "VALID course" in prompt and "REJECTED" not in prompt
    finally:
        cm.__exit__(None, None, None)


def test_method_choice_is_per_question_not_shared_state(make_client, monkeypatch):
    cm, api = semantic_api(make_client, monkeypatch)
    try:
        for method in ["lr", "svm", "lr"]:
            body = {"topic": "high_blood_pressure", "question": "Explain pressure.", "routing_method": method}
            reply = api.client.post("/api/v1/ask", json=body).json()
            assert reply["routing_details"]["method"] == method
        assert api.services.settings.routing.default_method == "lr"
        api.client.cookies.clear()
        assert api.client.post("/api/v1/ask/stream", json=body).status_code == 401
    finally:
        cm.__exit__(None, None, None)


def test_sanitized_history_is_available_to_follow_up_routing():
    from app.core.schemas import AskRequest, RequestContext, Turn
    from app.pipeline.steps.analyze_route import route_input

    ctx = RequestContext(
        request_id="r",
        request=AskRequest(student_id="s", topic="asthma", question="Why?"),
        pii=PIIResult(sanitized_text="Why?"),
        history=[Turn(role="student", text="A complex case with kidney disease and diabetes.")],
    )
    assert "kidney disease" in route_input(ctx).contextual_question
    assert "Current question: Why?" in route_input(ctx).contextual_question


def test_relevant_passages_reach_the_answer_even_without_full_qa_support(monkeypatch):
    """Answerability decides the route; every relevant passage may still teach (not only the best one)."""
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores",
        lambda name, pairs, cfg: np.array(
            [(0.9 if "pressure" in t else 0.05) if name == cfg.relevance_model else 0.2 for _, t in pairs]),
    )
    passages = [chunk(), chunk(text="Salt raises blood pressure."), chunk(text="Unrelated text about lungs.")]
    x = input_for(passages=passages)
    r = assess_evidence(x, analysis(), RoutingConfig())
    assert r.checked and r.status == "insufficient" and r.accepted_indices == []  # routing is unchanged
    assert [c.text for c in select_passages(x, r, RoutingConfig())] == [passages[0].text, passages[1].text]


def test_missing_evidence_models_keep_the_retrieved_passages_unverified(monkeypatch, caplog):
    def broken(name, pairs, cfg):
        raise OSError("model files not found")

    monkeypatch.setattr("app.routing.evidence.pair_scores", broken)
    monkeypatch.setattr("app.routing.evidence._warned_unavailable", False)
    off_topic = chunk(text="Pneumonia is a lung infection.")
    off_topic.topic = "pneumonia"
    draft = chunk(text="Unapproved draft.", metadata={"approved": False})
    x = input_for(passages=[chunk(), draft, off_topic])
    with caplog.at_level("WARNING", logger="app.routing"):
        r = assess_evidence(x, analysis(), RoutingConfig())
    assert not r.checked and "evidence models unavailable" in caplog.text  # not silent any more
    kept = select_passages(x, r, RoutingConfig())
    assert [c.text for c in kept] == [chunk().text]  # provenance and topic checks still apply
    assert kept[0].metadata["evidence_check"] == "unverified"


def test_course_passages_of_the_current_course_are_on_topic(monkeypatch):
    """The course retriever tags passages `course:<id>`; the question's topic is a module code or "general".
    Passages of the request's course are evidence; another course's passages never are."""
    from app.platform import course_scope

    monkeypatch.setattr(
        "app.routing.evidence.pair_scores", lambda name, pairs, cfg: np.array([0.9 for _ in pairs])
    )
    own = chunk().model_copy(update={"topic": "course:7"})
    other = chunk(text="Another course's text about blood pressure.").model_copy(update={"topic": "course:8"})
    x = input_for(passages=[own, other])
    scope = course_scope.CourseScope(course_id=7, content=None, learner=None, retriever=None, sessions=None,
                                     modules={})
    assert assess_evidence(x, analysis(), RoutingConfig()).status == "insufficient"  # no scope: none on topic
    with course_scope.use(scope):
        r = assess_evidence(x, analysis(), RoutingConfig())
        assert r.status == "sufficient" and r.accepted_indices == [0]
        assert [c.text for c in select_passages(x, r, RoutingConfig())] == [own.text]
        unverified = select_passages(x, None, RoutingConfig())  # evidence models skipped
        assert [c.text for c in unverified] == [own.text]


def test_sources_rejected_by_the_freshness_check_are_not_used_as_unverified():
    a = analysis(requires_fresh_evidence=True)
    x = input_for(passages=[chunk()])  # no verified_current metadata: fails the freshness check
    r = assess_evidence(x, a, RoutingConfig())
    assert r.checked and select_passages(x, r, RoutingConfig(), fresh=True) == []


def test_prepare_check_reports_every_missing_asset(monkeypatch, capsys):
    """The Docker build runs `prepare --check` (G1-56): a missing model must fail it, by name."""
    from app.routing import prepare

    def missing(name, cache_dir, local_only):
        assert local_only  # the check never downloads
        if name == RoutingConfig().answerability_model:
            raise OSError("not cached")

    monkeypatch.setattr(prepare, "sentence_encoder", missing)
    monkeypatch.setattr(prepare, "pair_encoder", missing)
    assert prepare.check() == 1
    err = capsys.readouterr().err
    assert "qnli-electra-base" in err and "ms-marco" not in err
    monkeypatch.setattr(prepare, "pair_encoder", lambda *a: None)
    assert prepare.check() == 0  # the committed LR/SVM weights match the configured encoder


def test_a_logistics_question_keeps_retrieved_passages_when_none_is_judged_relevant(monkeypatch):
    """A calendar row ("Lecture 21. KEY DATES: Problem set 4 due") scores low against "when is problem set 4
    due?": a logistics question then uses the retriever's results, unverified, instead of no material."""
    monkeypatch.setattr("app.routing.evidence.pair_scores",
                        lambda name, pairs, cfg: np.array([0.01] * len(pairs)))
    row = chunk(text="Calendar. Lecture 21. KEY DATES: Problem set 4 due")
    notice = chunk(text="Course announcement: Problem set 4 is due with Lecture 22.",
                   metadata={"origin": "announcement"})
    x = input_for(question="When is problem set 4 due?", passages=[row, notice])
    r = assess_evidence(x, analysis(), RoutingConfig())
    assert r.checked and r.relevant_indices == []
    kept = select_passages(x, r, RoutingConfig(), logistics=True)
    assert [c.text for c in kept] == [row.text, notice.text]
    assert all(c.metadata["evidence_check"] == "unverified" for c in kept)

    def calendar_relevant(name, pairs, cfg):
        return np.array([0.9 if "Calendar" in t else 0.01 for _, t in pairs])

    monkeypatch.setattr("app.routing.evidence.pair_scores", calendar_relevant)
    r = assess_evidence(x, analysis(), RoutingConfig())
    assert [c.text for c in select_passages(x, r, RoutingConfig(), logistics=True)] == [row.text, notice.text]
    assert [c.text for c in select_passages(x, r, RoutingConfig())] == [row.text]  # announcements: logistics


def test_the_logistics_fallback_keeps_the_freshness_check(monkeypatch):
    """A question that needs current evidence: passages the evidence step rejected as not verified current
    (and announcements without that check) never come back through the logistics fallback."""
    monkeypatch.setattr("app.routing.evidence.pair_scores",
                        lambda name, pairs, cfg: np.array([0.9] * len(pairs)))
    stale = chunk(text="Calendar. Lecture 21. KEY DATES: Problem set 4 due")
    notice = chunk(text="Course announcement: Problem set 4 is due with Lecture 22.",
                   metadata={"origin": "announcement"})
    x = input_for(question="When is problem set 4 due this week?", passages=[stale, notice])
    a = analysis(requires_fresh_evidence=True)
    r = assess_evidence(x, a, RoutingConfig())
    assert r.checked and r.reason == "No source passed provenance/time checks."
    assert select_passages(x, r, RoutingConfig(), logistics=True, fresh=True) == []
    assert len(select_passages(x, r, RoutingConfig(), logistics=True, fresh=False)) == 2  # not a fresh one


def test_a_question_without_a_relevant_passage_keeps_the_retrieved_passages(monkeypatch):
    """Retest N2 and X2: "summarize the key ideas of this module", or a broad whole-course question, shares no
    words with any passage, so the relevance model accepts none. The passages the panel reported as found
    are still used, unverified, instead of the answer saying that no material was provided."""
    monkeypatch.setattr("app.routing.evidence.pair_scores",
                        lambda name, pairs, cfg: np.array([0.01] * len(pairs)))
    x = input_for(question="Summarize the key ideas of this module", passages=[chunk()])
    r = assess_evidence(x, analysis(), RoutingConfig())
    assert r.checked and r.relevant_indices == []
    kept = select_passages(x, r, RoutingConfig())
    assert [c.text for c in kept] == [chunk().text] and kept[0].metadata["evidence_check"] == "unverified"


def test_the_sources_note_says_whether_the_passages_were_checked():
    # Q1-02: "not checked" only when the relevance check did not run; a check that confirmed none of the kept
    # passages gets its own note, so the answer does not contradict a routing panel that says "checked"
    from app.pipeline.steps.route import UNCONFIRMED_SOURCES_NOTE, UNVERIFIED_SOURCES_NOTE, sources_note

    fallback = [chunk().model_copy(update={"metadata": {"evidence_check": "unverified"}})]
    assert sources_note(fallback, evidence_ran=True, checked=False) == UNVERIFIED_SOURCES_NOTE
    assert sources_note(fallback, evidence_ran=True, checked=True) == UNCONFIRMED_SOURCES_NOTE
    assert sources_note([chunk()], evidence_ran=True, checked=True) is None  # judged relevant
    assert sources_note([], evidence_ran=True, checked=True) is None
    assert sources_note(fallback, evidence_ran=False, checked=False) is None  # no evidence step configured
