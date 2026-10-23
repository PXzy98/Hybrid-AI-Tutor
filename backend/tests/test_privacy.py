"""Privacy filter: recognizers, anonymization, restore (design §7.1 steps 1 and 7, §11 privacy targets)."""
import json
from pathlib import Path

import pytest
from sqlmodel import Session, select

from app.core.config import PrivacyConfig, get_settings
from app.core.schemas import AskRequest, RequestContext
from app.core.services import build_services
from app.pipeline.steps.privacy_filter import PrivacyFilterStep
from app.pipeline.steps.restore import RestoreStep
from app.pipeline.steps.route import RouteStep
from app.privacy.analyzer import Finding, PIIAnalyzer, PrivacyFilterUnavailable, resolve_overlaps
from app.privacy.anonymizer import anonymize, restore
from app.storage.models import RequestLog

pytestmark = pytest.mark.presidio

DATA = Path(__file__).resolve().parents[2] / "data" / "synthetic"
# labelled types in the ai-tutor-bench set -> our entity types; other labels are out of scope for the MVP
COVERED = {"PERSON": "PERSON", "STUDENT_ID": "STUDENT_ID", "GRADE": "GRADE", "EMAIL": "EMAIL_ADDRESS",
           "PHONE": "PHONE_NUMBER", "HEALTH": "HEALTH_DETAIL"}


@pytest.fixture(scope="module")
def analyzer() -> PIIAnalyzer:
    return PIIAnalyzer(PrivacyConfig(spacy_model="en_core_web_sm", score_threshold=0.5, allow_list=["Abbas"]))


def find(analyzer, text):
    return [(f.type, text[f.start:f.end]) for f in analyzer.analyze(text)]


def bench_items():
    lines = (DATA / "ai_tutor_bench_testset.jsonl").read_text("utf-8").splitlines()
    rows = [json.loads(line) for line in lines]
    return [r for r in rows if r["category"] == "pii"]


def test_bench_recall_and_no_over_redaction(analyzer):
    hits, total, misses, out_of_scope = 0, 0, [], []
    for item in bench_items():
        q = item["question"]
        findings = analyzer.analyze(q)
        sanitized, _, _ = anonymize(q, findings)
        for e in item["pii_entities"]:
            if e["type"] not in COVERED:
                out_of_scope.append(e["type"])
                continue
            total += 1
            start = q.find(e["text"])
            covered = sum(max(0, min(f.end, start + len(e["text"])) - max(f.start, start)) for f in findings)
            need = 1 if e["type"] == "HEALTH" else 0.8 * len(e["text"])  # health spans are labelled loosely
            if covered >= need:
                hits += 1
            else:
                misses.append((item["id"], e["type"], e["text"]))
        for term in item["non_pii_terms"]:
            assert term in sanitized, f"{item['id']}: '{term}' was redacted"
    recall = hits / total
    print(f"\nrecall {hits}/{total} = {recall:.2f}; misses: {misses!a}")  # !a: console-safe
    print(f"out of scope for the MVP: {sorted(set(out_of_scope))}")
    assert recall >= 0.85


def test_health_cases_personal_vs_general(analyzer):
    for line in (DATA / "pii_health_cases.jsonl").read_text("utf-8").splitlines():
        case = json.loads(line)
        findings = analyzer.analyze(case["text"])
        sanitized, _, _ = anonymize(case["text"], findings)
        is_health = any(f.type == "HEALTH_DETAIL" for f in findings)
        assert is_health == case["personal"], f"{case['id']}: {sanitized}"
        for value in case["redacted"]:
            assert value not in sanitized, f"{case['id']}: '{value}' survived: {sanitized}"


@pytest.mark.parametrize(("text", "expected"), [
    ("My student number is 300418277.", [("STUDENT_ID", "300418277")]),
    ("ID: 300 418 277 please", [("STUDENT_ID", "300 418 277")]),
    ("call 6135550148123 now", []),  # 13 digits: not a student number
    ("Call me at 613-555-0148.", [("PHONE_NUMBER", "613-555-0148")]),
    ("(613) 555-0148 is my cell", [("PHONE_NUMBER", "(613) 555-0148")]),
    ("sensitivity 0.6135550148", []),
    ("the value is 0.300418277", []),
    ("I got 58/100 on the midterm", [("GRADE", "I got 58/100")]),
    ("I got an A- on the quiz", [("GRADE", "I got an A-")]),
    ("I got a lot of questions wrong", []),
    ("The class average is 62%.", []),
    ("I failed the midterm", [("GRADE", "I failed the midterm")]),
    ("My email is s.nguyen92@gmail.com", [("EMAIL_ADDRESS", "s.nguyen92@gmail.com")]),
    ("Prof. Abbas explained it, and Dr. Abbas's slides too.", []),  # allow-listed course staff
    ("Compute Cohen's kappa and the Brier score.", []),  # eponyms are not people
    ("Can you explain what DICOM metadata contains?", []),
    ("Group: Tom Becker 300477120", [("PERSON", "Tom Becker"), ("STUDENT_ID", "300477120")]),
    # gaps found by E6 (eval/privacy-filter)
    ("My mark on quiz 2 was 13/20.", [("GRADE", "My mark on quiz 2 was 13/20")]),  # a grade, not a reading
    ("I failed my first exam.", [("GRADE", "I failed my first exam")]),
    ("What is the Fick principle?", []),
    ("My postal code is K1N 6N5.", [("POSTAL_CODE", "K1N 6N5")]),
    ("My health card is 1234 567 890 AB.", [("HEALTH_CARD", "1234 567 890 AB")]),
    ("Room 1234 567 890 is booked.", []),  # 10 digits without a health card word
    ("My SIN is 046 454 286.", [("ID_NUMBER", "046 454 286")]),
    ("I was born on March 3, 2001.", [("DATE_OF_BIRTH", "born on March 3, 2001")]),
    ("I live at 75 Laurier Avenue East.", [("ADDRESS", "75 Laurier Avenue")]),
    # gaps found by the E6 held-out set (eval/privacy-filter/holdout_review.md)
    ("I need advice on managing my diabetes diet.", [("HEALTH_DETAIL", "diabetes")]),
    ("My uncle's pneumonia made me worry.", [("HEALTH_DETAIL", "pneumonia")]),
    ("She's on fluticasone now.", [("HEALTH_DETAIL", "fluticasone")]),
    ("I need help with my blood pressure project.", []),
    ("I am struggling with the asthma section.", []),
    ("My grade is D+, sadly.", [("GRADE", "My grade is D+")]),
    ("My GPA is hovering around 3.2.", [("GRADE", "My GPA is hovering around 3.2")]),
])
def test_recognizers(analyzer, text, expected):
    assert find(analyzer, text) == expected


@pytest.mark.parametrize(("text", "types", "cloud_safe"), [
    ("J'ai de l'asthme. Est-ce que je peux courir?", {"HEALTH_DETAIL"}, False),
    ("Je m'appelle Chloé Martin.", {"PERSON"}, True),
    ("J'ai eu 58/100 à l'examen.", {"GRADE"}, True),
    ("Qu'est-ce que l'hypertension?", set(), True),
])
def test_french(analyzer, text, types, cloud_safe):
    found = analyzer.analyze(text)
    assert {f.type for f in found} == types
    assert (not any(f.type in analyzer.cfg.local_only_types for f in found)) == cloud_safe


def test_overlaps_prefer_longer_then_higher_score():
    kept = resolve_overlaps([Finding("PERSON", 0, 5, 0.9), Finding("HEALTH_DETAIL", 0, 12, 0.85),
                             Finding("GRADE", 20, 25, 0.7)])
    assert [(f.type, f.start) for f in kept] == [("HEALTH_DETAIL", 0), ("GRADE", 20)]


def test_person_never_hides_a_local_only_finding():
    """NER tagged "J'ai de l'asthme" as a PERSON longer than the health term (E6)."""
    kept = resolve_overlaps([Finding("PERSON", 0, 16, 0.85), Finding("HEALTH_DETAIL", 9, 16, 0.8)],
                            prefer=("HEALTH_DETAIL",))
    assert [f.type for f in kept] == ["HEALTH_DETAIL"]
    kept = resolve_overlaps([Finding("GRADE", 0, 16, 0.7), Finding("HEALTH_DETAIL", 9, 16, 0.8)],
                            prefer=("HEALTH_DETAIL",))
    assert [f.type for f in kept] == ["GRADE"]  # pattern types keep the length rule


def test_anonymize_numbers_per_type_and_reuses_placeholders():
    text = "Alice met Bob. alice  emailed bob@x.ca and Alice again."
    findings = [Finding("PERSON", 0, 5, 0.9), Finding("PERSON", 10, 13, 0.9), Finding("PERSON", 15, 20, 0.9),
                Finding("EMAIL_ADDRESS", 30, 38, 1.0), Finding("PERSON", 43, 48, 0.9)]
    sanitized, entities, mapping = anonymize(text, findings)
    assert sanitized == ("<PERSON_1> met <PERSON_2>. <PERSON_1>  emailed <EMAIL_ADDRESS_1> "
                         "and <PERSON_1> again.")
    assert mapping == {"<PERSON_1>": "Alice", "<PERSON_2>": "Bob", "<EMAIL_ADDRESS_1>": "bob@x.ca"}
    assert len(entities) == 5
    assert restore(sanitized, mapping) == "Alice met Bob. Alice  emailed bob@x.ca and Alice again."


@pytest.mark.parametrize("variant", ["<PERSON_1>", "<person_1>", "< PERSON_1 >", "[PERSON_1]"])
def test_restore_tolerates_formatting_and_ignores_unknown(variant):
    mapping = {"<PERSON_1>": "Alice", "<STUDENT_ID_1>": "300418277"}
    out = restore(f"Hi {variant}, id <STUDENT_ID_1>, <PERSON_9>", mapping)
    assert out == "Hi Alice, id 300418277, <PERSON_9>"
    assert restore("<PERSON_1>", {}) == "<PERSON_1>"


async def test_step_done_when_example(use_config):
    """'My student ID is 300418277 and I have asthma' -> local only (policy local_only), sanitized."""
    services = build_services(use_config({"routing": {"stub_score": 1.0},
                                          "privacy": {"health_detail_policy": "local_only"}}))
    ctx = RequestContext(request_id="r", request=AskRequest(
        student_id="s", topic="asthma", question="My student ID is 300418277 and I have asthma. What helps?"))
    ctx = await PrivacyFilterStep(services).run(ctx)
    assert ctx.pii.sanitized_text == ("My student ID is <STUDENT_ID_1> and I have <HEALTH_DETAIL_1>. "
                                      "What helps?")
    assert ctx.pii.is_sensitive and not ctx.pii.cloud_safe
    assert ctx.pii_mapping == {"<STUDENT_ID_1>": "300418277", "<HEALTH_DETAIL_1>": "asthma"}
    ctx = await RouteStep(services).run(ctx)
    assert ctx.target == "local" and "forced local: not cloud_safe" in ctx.route.reasons


async def test_clean_question_is_not_sensitive(use_config):
    services = build_services(use_config())
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="asthma",
                                                            question="What triggers an asthma attack?"))
    ctx = await PrivacyFilterStep(services).run(ctx)
    assert ctx.pii.entities == [] and ctx.pii.cloud_safe and not ctx.pii.is_sensitive
    assert ctx.pii.sanitized_text == "What triggers an asthma attack?"


async def test_restore_step_puts_values_back(use_config):
    services = build_services(use_config())
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="asthma", question="q"),
                         answer="Hello <PERSON_1>, see <person_1>.")
    ctx.set_pii_mapping({"<PERSON_1>": "Wei Zhang"})
    ctx = await RestoreStep(services).run(ctx)
    assert ctx.answer == "Hello Wei Zhang, see Wei Zhang."
    assert ctx.pii_mapping  # kept for a possible regeneration in verify; `record` and the API clear it


def test_missing_spacy_model_stops_startup(use_config):
    from app.pipeline.runner import build_runner

    use_config({"privacy": {"spacy_model": "en_core_web_doesnotexist"}})
    with pytest.raises(PrivacyFilterUnavailable, match="spacy download en_core_web_doesnotexist"):
        build_runner(build_services(get_settings()))


# ------------------------------------------------------------------- the student's own identity (E4)
def test_known_identity_values_are_always_found(analyzer):
    text = "this is lucas bergeron, username p.intermediate, and Bergeron again; symptoms differ"
    found = analyzer.analyze(text, names=["Lucas Bergeron", "Lucas", "Bergeron", "Tom"],
                             usernames=["p.intermediate"])
    spans = {(f.type, text[f.start:f.end]) for f in found}
    assert ("PERSON", "lucas bergeron") in spans and ("PERSON", "Bergeron") in spans
    assert ("USERNAME", "p.intermediate") in spans
    assert not any("symptoms" in v or v == "tom" for _, v in spans)  # whole words only


def test_ask_redacts_the_students_own_name_and_username(api):
    api.make_student("p.intermediate", "Lucas Bergeron")
    api.login("p.intermediate")
    r = api.client.post("/api/v1/ask", json={
        "topic": "high_blood_pressure",
        "question": "hi it's lucas bergeron (p.intermediate). What does the bottom number mean?"})
    assert r.status_code == 200, r.text
    sent = api.local_llm.sent_text()  # the local model may see raw text; check what is stored instead
    assert "lucas bergeron" in sent.lower()
    with Session(api.services.engine) as db:
        stored = [row.sanitized_question for row in db.exec(select(RequestLog))]
    assert stored and "bergeron" not in stored[0].lower() and "p.intermediate" not in stored[0]
    assert "<PERSON_1>" in stored[0] and "<USERNAME_1>" in stored[0]
