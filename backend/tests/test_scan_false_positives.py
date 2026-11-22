"""Course material must not be refused as student data, and student data must still be refused (task Z11).

The false positives were found by scanning the open course packs (data/demo_courses/, MIT OpenCourseWare and
Harvard CS50x); the texts below are short paraphrases of those passages, and every person is fictional.
"""
import pytest

from app.privacy.profiles import privacy_profile, scan_document


def _types(profile: str, text: str) -> set[str]:
    return {f.type for f in scan_document(text, privacy_profile(profile)).findings}


def _blocking(profile: str, text: str) -> tuple[str, ...]:
    return scan_document(text, privacy_profile(profile)).blocking


# ---------------------------------------------------------------- not student data
@pytest.mark.parametrize(("profile", "text"), [
    # ISBN-10 with an X check digit, with or without "ISBN"
    ("medical_science", "Pathologic Basis of Disease. 6th edition. Saunders, 1999. ISBN: 072167335X."),
    ("medical_science", "Comprehensive clinical hepatology. Mosby, 2000. 072343106X. Clinical signs."),
    ("general", "See the textbook (ISBN 0-7216-7335-X) for the figures."),
    # identifiers of a reference list (Wikipedia pages as draft sources)
    ("ece", "Journal of Experimental Algorithmics. 22. Article 1.3. arXiv:1509.05053. doi:10.1145/3053370. "
            "S2CID 23752485."),
    ("ece", "Combinatorics, Probability and Computing. S2CID 125374363. hdl:10092/9691."),
    ("ece", "PhD thesis, Stanford University. ProQuest 301940891."),
    ("medical_science", "Journal of Mathematical Biology. PMID 300418277. OCLC 212649328."),
    # a range of decimal numbers in a chart legend, and a run of one repeated digit in a figure
    ("medical_science", "BMI groups: 30.0-34.9 25.0-29.9 23.0-24.9 <23.0 Key research issues in diet."),
    ("ece", "(d) a_k as in Figure P10.7(b) 111111111 III -8 0 8 16 Figure P10.7"),
    # a placeholder, not a credential
    ("ece", "Request a URL like `https://api.example.com/v1/quote/nflx?token=API_KEY`. Notice the symbol."),
    ("ece", 'Set password = "YOUR_PASSWORD" and api_key: <your-api-key> before you run it.'),
    # blood type alleles in a genetics exercise
    ("ece", "The first parent received an A from the first grandparent and an O from the second grandparent,"
            " so the parent has blood type A."),
    # a proof by induction and a lab technique, not a health detail
    ("ece", "Then A[:i] is sorted by induction, and T(n) = T(n - 1) + O(n)."),
    ("life_science", "Please state whether you are using pronuclear injection or gene targeting techniques."),
])
def test_course_material_is_not_refused(profile, text):
    assert _blocking(profile, text) == ()


@pytest.mark.parametrize("text", [
    # clinical teaching cases: health details of fictional patients, no student identifier
    "CASE DESCRIPTION. A 29 year old male who works at your clinic believes he has diabetes mellitus. His "
    "father and paternal grandfather both developed diabetes.",
    "After the initial visit, she was brought to an emergency room vomiting blood. She said she had stopped "
    "her medication after one week because the pain had resolved.",
    "Despite theophylline and an albuterol inhaler he is still markedly short of breath.",
])
def test_teaching_cases_are_reported_but_do_not_block(text):
    assert "HEALTH_DETAIL" in _types("medical_science", text)  # still found, for the question filter
    assert _blocking("medical_science", text) == ()


# ---------------------------------------------------------------- still student data
@pytest.mark.parametrize("text", [
    "Ann Lee 300123456",
    "student 300418277 got 87% on the midterm",
    "Student number: 300 418 277",
    "ID number: 300-418-277",
    "ID: 300-987 654, asthma flares when I run",  # mixed separators (E6 held-out 5)
    # the reference-list labels are case-sensitive and must come right before the number
    "Eric 300123456",
    "Mr 300123456 asked about the arXiv paper",
    "my student number is 300418277, see doi 10.1145/3053370",
])
def test_student_numbers_still_block(text):
    assert "STUDENT_ID" in _blocking("general", text)


@pytest.mark.parametrize(("text", "kind"), [
    # a grade or a health detail next to a direct identifier of the student
    ("Extension request from student 300418277: I was sick with the flu last week.", "HEALTH_DETAIL"),
    ("From ann.lee@uottawa.ca: I have asthma and missed the lab.", "HEALTH_DETAIL"),
    ("Ann Lee (613-555-0142) says she has had migraines all week.", "HEALTH_DETAIL"),
    ("300418277 Ann Lee, midterm grade: B+", "GRADE"),
    # a grade next to a name: a list of students' results
    ("Results: Ann Lee got a B+ and Omar Haddad got a C on the midterm.", "GRADE"),
])
def test_grades_and_health_details_of_an_identified_student_block(text, kind):
    assert kind in _blocking("medical_science", text)


@pytest.mark.parametrize("text", [
    'password = "LAB_PASS_2026"',
    'password = "<Lab4Pass!2026>"',
    "my password is LAB_PASS_2026",
    "api_key: GHX_LIVE_KEY",
])
def test_constant_like_or_bracketed_credentials_still_block(text):
    assert "SECRET" in _blocking("general", text)


@pytest.mark.parametrize("text", [
    "I hit a B on the midterm about dominant alleles.",
    "My genetics exam grade was an A, the one on recessive genes.",
    "I got an A in the course on inheritance.",
])
def test_grades_in_sentences_about_inheritance_are_still_found(text):
    assert "GRADE" in _types("life_science", text)


def test_a_real_credential_still_blocks_in_every_course():
    for profile in ("general", "ece", "medical_science", "life_science"):
        assert "SECRET" in _blocking(profile, 'password = "Lab4Pass!2026"')
        assert "SECRET" in _blocking(profile, "token=FAKEtoken0000abc")


def test_an_allele_received_from_a_grandparent_is_not_a_grade():
    """Z25: the CS50x pset 5 text (paraphrased) was refused as GRADE: the allele exceptions never matched,
    because three of their patterns ended in a control character instead of a word boundary."""
    text = ("For example, the child in Generation 0 received an O allele from both Generation 1 parents. The "
            "first parent received an A from the first grandparent and a O from the second grandparent. "
            "Similarly, the second parent received an O and a B from their grandparents.\n\n"
            "Child (Generation 0): blood type OO\n    Parent (Generation 1): blood type AO\n")
    assert "GRADE" not in _types("ece", text)
    assert not _blocking("ece", text)
    assert "GRADE" not in _types("ece", "She has an A allele and he has a B allele.")


def test_no_recognizer_pattern_contains_a_control_character():
    """A non-raw "\\b" in a pattern is a backspace, and the pattern silently never matches."""
    from pathlib import Path

    import app.privacy.recognizers as recognizers

    for source in Path(recognizers.__file__).parent.glob("*.py"):
        text = source.read_text(encoding="utf-8")
        bad = [c for c in text if ord(c) < 32 and c not in "\n\r\t"]
        assert not bad, f"{source.name} contains control characters {sorted(set(map(ord, bad)))}"
