"""Task Z11: credentials and lab details (base layer and ECE profile), scan_document, search_query and the
consent text per course type. Every key here is a fake made for the tests."""
import pytest

from app.core.config import get_settings
from app.core.schemas import AskRequest, PIIResult, RequestContext
from app.privacy.analyzer import PIIAnalyzer
from app.privacy.profiles import (
    CONSENT_BASE,
    SEARCH_QUERY_MAX_CHARS,
    consent_text,
    privacy_profile,
    scan_document,
    search_query,
)

FAKE_KEY = "sk-proj-FAKEfake0000testKEY1111notreal2222"


def _analyzer(profile: str) -> PIIAnalyzer:
    recognizers = list(privacy_profile(profile).recognizers)
    return PIIAnalyzer(get_settings().privacy.model_copy(update={"recognizers": recognizers}))


def _found(profile: str, text: str) -> dict[str, list[str]]:
    out: dict[str, list[str]] = {}
    for f in _analyzer(profile).analyze(text):
        out.setdefault(f.type, []).append(text[f.start:f.end])
    return out


@pytest.mark.parametrize(("text", "kind", "value"), [
    (f"my key {FAKE_KEY} gives 401", "SECRET", FAKE_KEY),
    ("access key AKIAIOSFODNN7EXAMPLE fails", "SECRET", "AKIAIOSFODNN7EXAMPLE"),
    ("I set password: Lab4Pass!2026 on the broker", "SECRET", "Lab4Pass!2026"),
    ("api_key='FAKE-9f8e7d6c5b4a3210' in my sketch", "SECRET", "FAKE-9f8e7d6c5b4a3210"),
    ("the ESP32 at 192.168.1.42:8080 does not answer", "INTERNAL_ADDRESS", "192.168.1.42:8080"),
    ("my VM gets 10.12.4.77 from DHCP", "INTERNAL_ADDRESS", "10.12.4.77"),
    ("the board's MAC is 3c:71:bf:4a:9e:02", "INTERNAL_ADDRESS", "3c:71:bf:4a:9e:02"),
    ("review github.com/jtremblay42/elg5902-lab3 please", "REPO_URL", "github.com/jtremblay42/elg5902-lab3"),
])
def test_the_ece_profile_finds_credentials_lab_addresses_and_repositories(text, kind, value):
    assert value in _found("ece", text).get(kind, [])


def test_a_private_key_is_found_to_its_end_line():
    key = "-----BEGIN RSA PRIVATE KEY-----\nMIIFAKEKEYFORTESTSONLY0000\n-----END RSA PRIVATE KEY-----"
    assert _found("ece", f"{key} is what ssh-keygen gave me")["SECRET"] == [key]


@pytest.mark.parametrize("text", [
    "What is the difference between 10.0.0.0/8 and 192.168.0.0/16?",
    "Why does a 10 kOhm pull-up resistor work at 3.3 V?",
    "The token expired error appears after an hour, how does token rotation work?",
    "What does the password is required message mean in an HTTP 401 response?",
    "Why is 8.8.8.8 used as a DNS server in examples?",
    "How do I convert 0x1F4A to decimal and binary?",
    "Is github.com free for student projects?",
])
def test_course_terms_are_not_redacted(text):
    assert _found("ece", text) == {}


def test_secrets_are_in_every_course_and_lab_details_only_in_ece():
    text = f"key {FAKE_KEY} on 10.0.3.15 from github.com/nchen/pi-sensor"
    for profile in ("general", "medical_science", "life_science"):
        found = _found(profile, text)
        assert found.get("SECRET") == [FAKE_KEY]
        assert "INTERNAL_ADDRESS" not in found and "REPO_URL" not in found
    assert set(_found("ece", text)) == {"SECRET", "INTERNAL_ADDRESS", "REPO_URL"}


def test_scan_document_reports_types_and_counts_and_what_blocks_indexing():
    text = ("Lecture 3 by Prof. Abbas. Contact: office hours on Monday.\n"
            "Example grades: student 300418277 got 87% on the midterm.\n") * 3
    result = scan_document(text, privacy_profile("general"))
    found = {f.type: f.count for f in result.findings}
    assert result.scanned is True and found["STUDENT_ID"] == 3
    assert "STUDENT_ID" in result.blocking and "PERSON" not in result.blocking
    assert not any("300418277" in str(f) for f in result.findings)  # types and counts, never the text
    clean = scan_document("The Fourier transform of a square wave.\n" * 2000, privacy_profile("ece"))
    assert clean.scanned is True and clean.blocking == ()


def test_scan_document_finds_an_entity_near_a_piece_boundary():
    filler = ("A line about filters and op-amps.\n" * 700)  # more than one 20,000-character piece
    result = scan_document(filler + "student 300418277\n" + filler, privacy_profile("general"))
    assert dict((f.type, f.count) for f in result.findings).get("STUDENT_ID") == 1


def _ctx(sanitized: str, cloud_safe: bool = True, question: str = "original text") -> RequestContext:
    return RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question=question),
                          pii=PIIResult(sanitized_text=sanitized, cloud_safe=cloud_safe))


def test_search_query_comes_only_from_the_sanitized_general_part():
    assert search_query(RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t",
                                                                          question="What is DHCP?"))) is None
    original = "I am Ann. What is a pull-up resistor?"  # never read: only the sanitized text is
    general = "What is a pull-up resistor?"
    assert search_query(_ctx(general, question=original)) == general
    mixed = "I am <PERSON_1>, student <STUDENT_ID_1>. How does DHCP assign a gateway?"
    assert search_query(_ctx(mixed)) == "How does DHCP assign a gateway?"
    assert search_query(_ctx("My grade is <GRADE_1>, can I retake it?")) is None  # nothing general left
    assert search_query(_ctx("What is DHCP?", cloud_safe=False)) is None  # a local-only question
    long = "Explain " + "the frequency response of a band-pass filter " * 20
    assert len(search_query(_ctx(long))) <= SEARCH_QUERY_MAX_CHARS


def test_consent_text_per_course_type():
    assert consent_text(privacy_profile("general")) == CONSENT_BASE
    assert "medical advice" in consent_text(privacy_profile("medical_science"))
    assert "API keys" in consent_text(privacy_profile("ece"))
    from app.api.v1.onboarding import CONSENT_TEXT

    assert CONSENT_TEXT == CONSENT_BASE  # API v1 keeps the same reviewed text


@pytest.mark.parametrize(("text", "value"), [
    ('config = {"password": "Lab4Pass!2026", "port": 1883}', "Lab4Pass!2026"),
    ("settings = {'api_key': 'FAKE-9f8e7d6c5b4a3210'}", "FAKE-9f8e7d6c5b4a3210"),
    ('{"access_token":"FAKEtoken0000abc"}', "FAKEtoken0000abc"),
])
def test_credentials_with_quoted_names_are_found(text, value):
    assert value in _found("general", text).get("SECRET", [])


def test_a_value_on_an_exact_piece_boundary_is_found_once():
    from app.privacy.profiles import SCAN_CHUNK_CHARS

    text = " " * (SCAN_CHUNK_CHARS - 12) + "student 300418277 done"  # the number straddles the first edge
    result = scan_document(text, privacy_profile("general"))
    assert dict((f.type, f.count) for f in result.findings).get("STUDENT_ID") == 1
    overlap = " " * (SCAN_CHUNK_CHARS - 2000) + "student 300418277 " + " " * 30_000  # inside the overlap
    assert dict((f.type, f.count) for f in scan_document(overlap, privacy_profile("general")).findings) \
        .get("STUDENT_ID") == 1
