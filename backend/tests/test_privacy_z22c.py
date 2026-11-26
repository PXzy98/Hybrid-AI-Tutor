"""Course terms that hold a surname are not people, formula digits are not student numbers (task Z22c).

All texts are fictional; the formulas are short imitations of the digit runs a PDF extraction makes from
equation subscripts.
"""
from functools import cache

import pytest
import spacy

from app.core.config import PrivacyConfig
from app.privacy.analyzer import PIIAnalyzer
from app.privacy.profiles import privacy_profile, scan_document

# CI installs the small spaCy model only (as test_privacy.py uses it); production builds the large one, so the
# sentences run with both where the large one is installed. The small model tags two of them differently.
SMALL, LARGE = "en_core_web_sm", "en_core_web_lg"
MODELS = [SMALL, pytest.param(LARGE, marks=pytest.mark.skipif(not spacy.util.is_package(LARGE),
                                                              reason=f"{LARGE} is not installed"))]
SMALL_MODEL_MISSES = {
    "Explain Kirchhoff's laws with an example.",  # tagged "Explain Kirchhoff's", wider than the course term
    "Kirchhoff said the loop rule holds, please check my notes.",  # tagged as an organisation
}


@cache
def _analyzer(model: str) -> PIIAnalyzer:
    return PIIAnalyzer(PrivacyConfig(spacy_model=model))


def _types(text: str, model: str) -> list[str]:
    if model == SMALL and text in SMALL_MODEL_MISSES:
        pytest.skip("the small spaCy model tags this sentence differently")
    return [f.type for f in _analyzer(model).analyze(text)]


@pytest.mark.parametrize("text", [
    "What is Kirchhoff's current law, in two sentences?",
    "State Kirchhoff's voltage law for a loop.",
    "Explain Kirchhoff's laws with an example.",
    "How does Ohm's law apply to a resistor?",
    "Find the Thevenin equivalent of this circuit.",
    "Find the Thévenin equivalent of this circuit.",
    "How do I get the Norton equivalent?",
    "Write Maxwell's equations in integral form.",
    "What does Faraday's law say about induced voltage?",
    "Coulomb's law and Gauss's law are related, right?",
    "How do I compute the Fourier transform of a pulse?",
    "Is a Fourier series the same as a Laplace transform?",
    "How do I read a Bode plot or a Nyquist plot?",
    "Explain Dijkstra's algorithm and Bayes' theorem.",
    "What do Newton's laws say? And Euler's formula?",
    "Is Hardy-Weinberg equilibrium relevant to Mendel's laws?",
    "Where does the Krebs cycle happen, and what does a Gram stain show?",
    "What are the symptoms of Parkinson's disease or Alzheimer's disease?",
    "what is kirchhoff's current law",
])
@pytest.mark.parametrize("model", MODELS)
def test_course_terms_are_not_people(text: str, model: str) -> None:
    assert "PERSON" not in _types(text, model)


@pytest.mark.parametrize("text", [
    "Kirchhoff said the loop rule holds, please check my notes.",
    "My friend Kirchhoff asked me to explain the circuit.",
    "Alex Morgan asked about Ohm's law in the lab.",
    "Please ask Priya Raman about the Fourier transform.",
])
@pytest.mark.parametrize("model", MODELS)
def test_names_next_to_course_terms_are_still_found(text: str, model: str) -> None:
    assert "PERSON" in _types(text, model)


FORMULA_LINES = [
    "0)()()( 152402312 =-+-+- IGeGVeGee",
    "(e1 - e2) 152402312 = (G1 + G2) * 140543231 + (G3 - G4) I1",
    "140543231 )()()( IGVGGGeGe",
    "V1 = 0)()( 231402315 )-( + I2",
    # a fraction laid out one row per line: the digits alone on their line, formula rows around them
    "1e ++++++++\n++++\n=\n()( )( )( )\n5343\n2\n3524232514131\n104321013\n2\n"
    "GGGGGGGGGGGGGGGGG\nIVGGGGVGGe\n++++++++",
]


@pytest.mark.parametrize("line", FORMULA_LINES)
def test_formula_digit_runs_are_not_student_ids(line: str) -> None:
    text = f"Nodal analysis of the circuit.\n{line}\nSolve for the node voltages."
    result = scan_document(text, privacy_profile("ece"))
    assert "STUDENT_ID" not in {f.type for f in result.findings}
    assert result.blocking == ()


@pytest.mark.parametrize("text", [
    "My student number is 300123456, can you check my mark?",
    "300123456",
    "Please look up 300123456 in the roster.",
    "Ann Lee (300123456) is in my group.",
    "Student ID: 300123456 = the one on the card.",
    "e1 + e2 = 0, and my student number is (300123456).",
    "id 300123456 + (G1 - G2)",
    "Class list\nAlice Smith\n300123456\nBob Lee\n300654321\n",
    "Marks (final)\n300123456\nB+ (75)\n=> pass\n",
    # separator lines and table borders are not formula rows (review of Z22c)
    "Class list\n---------\n300123456\n---------\n",
    "Class list\n=========\n300123456\n=========\n",
    "+-----------+\n| 300123456 |\n+-----------+\n| 300654321 |\n+-----------+\n",
    "Class list\n- - - - - - - -\n300123456\n- - - - - - - -\n",
    # a number with the university's prefix is a student number even between formula rows
    "Grades:\nx = (a + b) * (c - d)\n300123456\ny = (e + f) - (g * h)\n",
    "V1 = 0)()( 300123456 )-( + I2",
])
def test_student_numbers_are_still_found(text: str) -> None:
    result = scan_document(text, privacy_profile("ece"))
    assert "STUDENT_ID" in {f.type for f in result.findings}
