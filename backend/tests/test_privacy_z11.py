"""Task Z11: credentials and lab details (base layer and ECE profile), scan_document, search_query and the
consent text per course type. Every key here is a fake made for the tests."""
import pytest

from app.core.config import get_settings
from app.core.schemas import AskRequest, PIIResult, RequestContext
from app.privacy.analyzer import PIIAnalyzer
from app.privacy.profiles import (
    CONSENT_BASE,
    SEARCH_QUERY_MAX_CHARS,
    STATISTICS_ONLY_NOTE,
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
    assert consent_text(privacy_profile("general"), statistics_only=True).endswith(STATISTICS_ONLY_NOTE)
    from app.api.v1.onboarding import CONSENT_TEXT

    assert CONSENT_TEXT == CONSENT_BASE  # API v1 keeps the same reviewed text


@pytest.mark.parametrize(("text", "value"), [
    ('config = {"password": "Lab4Pass!2026", "port": 1883}', "Lab4Pass!2026"),
    ("settings = {'api_key': 'FAKE-9f8e7d6c5b4a3210'}", "FAKE-9f8e7d6c5b4a3210"),
    ('{"access_token":"FAKEtoken0000abc"}', "FAKEtoken0000abc"),
])
def test_credentials_with_quoted_names_are_found(text, value):
    assert value in _found("general", text).get("SECRET", [])


# Z22b: shapes the Z22 held-out sets missed (fictional values made for the tests)
@pytest.mark.parametrize(("profile", "text", "kind", "value"), [
    ("general", "AWS_SECRET_ACCESS_KEY=wJalrFAKEnotreal/K7MDENG/bPxRfiCYTESTKEY.", "SECRET",
     "wJalrFAKEnotreal/K7MDENG/bPxRfiCYTESTKEY"),
    ("general", "boto3.client('s3', aws_secret_access_key='fakeSecret+0000notreal/TESTTEST')", "SECRET",
     "fakeSecret+0000notreal/TESTTEST"),
    ("general", "Aws_Secret_Access_Key: fakeSecret+1111notreal", "SECRET", "fakeSecret+1111notreal"),
    ("general", 'export API_TOKEN="tok_FAKE_0a1b2c3d4e5f_notreal" in .bashrc', "SECRET",
     "tok_FAKE_0a1b2c3d4e5f_notreal"),
    ("general", "cfg = {'STRIPE_SECRET': 'fake_live_0000notreal'}", "SECRET", "fake_live_0000notreal"),
    ("general", "DB_PASSWORD=Fake!Pass2026", "SECRET", "Fake!Pass2026"),
    ("general", "headers = {'Authorization': 'Bearer FAKEtoken0123456789notreal'}", "SECRET",
     "FAKEtoken0123456789notreal"),
    ("general", "curl -H 'Authorization: bearer fake.TOKEN-0123456789' gives 401", "SECRET",
     "fake.TOKEN-0123456789"),
    ("general", "My broker is mqtt://sensor_user:Rt7Fake!Pass@broker.example.test:1883", "SECRET",
     "Rt7Fake!Pass"),
    ("general", "postgres://app:Fake2026x@db.example.test/app fails", "SECRET", "Fake2026x"),
    ("general", "My Wi-Fi password for the library is Campus!Fake2026 -- is that OK?", "SECRET",
     "Campus!Fake2026"),
    ("general", "The passcode to the lab door is 4471-FAKE.", "SECRET", "4471-FAKE"),
    ("ece", "I pasted this by accident: AWS_SECRET_ACCESS_KEY=wJalrFAKE/K7MDENG/bPxRfiCYFAKEKEY. Oops",
     "SECRET", "wJalrFAKE/K7MDENG/bPxRfiCYFAKEKEY"),
    ("ece", "The scope is on the lab VLAN at 172.16.8.203.", "INTERNAL_ADDRESS", "172.16.8.203"),
    ("ece", "and the gateway is 172.31.255.1:8443, right?", "INTERNAL_ADDRESS", "172.31.255.1:8443"),
    ("ece", "My Pi is at 192.168.4.20.", "INTERNAL_ADDRESS", "192.168.4.20"),
    ("computer_science", "git remote says git@github.com:jtremblay42/stm32-uart.git", "REPO_URL",
     "git@github.com:jtremblay42/stm32-uart.git"),
    ("computer_science", "push to git@gitlab.example.test:team-7/lab3 is denied", "REPO_URL",
     "git@gitlab.example.test:team-7/lab3"),
])
def test_z22b_credentials_addresses_and_remotes_are_found(profile, text, kind, value):
    assert value in _found(profile, text).get(kind, [])


@pytest.mark.parametrize(("profile", "text"), [
    ("computer_science", "Why is primary_key=True needed on the id field?"),
    ("computer_science", "What does max_tokens=4096 do in the API call?"),
    ("computer_science", "The cache_key: user_profile_settings is built from the id."),
    ("computer_science", "Use sort_key = lambda x: x[1] to sort by the second field."),
    ("computer_science", "Set API_KEY=YOUR_API_KEY_HERE in the .env file."),
    ("computer_science", "The bearer token scheme sends the token in the Authorization header."),
    ("computer_science", "Read it with token_count = len(tokens) first."),
    ("computer_science", "Why does cache_key=request.path miss the query string?"),
    ("computer_science", 'Is primary_key="student.id" valid in this ORM?'),
    ("computer_science", "Is token_count=10000000 too large for one batch?"),
    ("computer_science", "Set sort_key: by_lastname_2026 for the export."),
    ("computer_science", "The partition_key = region-2026-q4 spreads the rows."),
    ("computer_science", "We use max_token = 8192 and page_token = abc123def456 here."),
    ("general", "The password for the quiz is given in class, right?"),
    ("general", "Why must a password for a website be long?"),
    ("general", "Do you know whether the password for the router is required?"),
    ("general", "The password for the router is case-sensitive."),
    ("general", "The password for the lab account is write-protected, isn't it?"),
    ("ece", "Is 172.16.0.0/12 a private range, and what about 172.32.1.1?"),
    ("ece", "Why is 8.8.8.8 used as a DNS server?"),
    ("ece", "Version 3.172.16.4 of the driver is out."),
])
def test_z22b_course_text_without_secrets_is_kept(profile, text):
    assert _found(profile, text) == {}


def test_a_value_on_an_exact_piece_boundary_is_found_once():
    from app.privacy.profiles import SCAN_CHUNK_CHARS

    text = " " * (SCAN_CHUNK_CHARS - 12) + "student 300418277 done"  # the number straddles the first edge
    result = scan_document(text, privacy_profile("general"))
    assert dict((f.type, f.count) for f in result.findings).get("STUDENT_ID") == 1
    overlap = " " * (SCAN_CHUNK_CHARS - 2000) + "student 300418277 " + " " * 30_000  # inside the overlap
    assert dict((f.type, f.count) for f in scan_document(overlap, privacy_profile("general")).findings) \
        .get("STUDENT_ID") == 1


def test_z22b_long_names_without_an_assignment_are_scanned_in_linear_time():
    """A 20,000-character name made of credential words and no "=" (one scan window) must not backtrack."""
    import time

    from app.privacy.recognizers.engineering import SecretTokenRecognizer

    for text in ("token_" * 3333 + "x", "API_SECRET-" * 1800, "a_" * 10000):
        start = time.perf_counter()
        assert list(SecretTokenRecognizer._z22b_values(text)) == []
        assert time.perf_counter() - start < 0.5
