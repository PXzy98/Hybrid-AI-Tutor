import re

from presidio_analyzer import Pattern, PatternRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

# nine digits split by single spaces, dots, slashes or hyphens in any grouping: "300 418 277", "300/418/277",
# "3004 18277", "300.418.277"; never part of a longer number (phone numbers, health cards)
SPLIT_DIGITS = r"(?<![\d.,/-])\d(?:[ ./-]?\d){8}(?![\d]|[ ./-]\d)"
# "student number" / "student ID" written with typos or abbreviations: "studnet nmuber", "stdnt #", "stu no."
FUZZY_CONTEXT = (r"\b(?:stu\w{0,6}|std\w{0,4})\b\s*(?:-\s*)?(?:id\b|i\.d\.|n\w{0,6}\b|no\b\.?|#)\s*"
                 r"(?:is\b|was\b|:|=|#)?\s*")
FUZZY_CONTEXT_RE = re.compile(FUZZY_CONTEXT + r"(" + SPLIT_DIGITS + r")", re.I)
# Beta: "my id is 3 0 0 4 1 8 2 7 7" (Presidio's context boost does not fire on "id"), "ID number:
# 300-418-277"
ID_CONTEXT_RE = re.compile(r"\b(?:id|i\.d\.|id number|student\s*(?:no\.?|num(?:ber)?|#)|number|no\.|#)\s*"
                           r"(?:is\b|was\b|:|=|#)?\s*(" + SPLIT_DIGITS + r")", re.I)
# split nine digits starting with 300 (the university's prefix) need no context word; a suffix like "-2" stays
PREFIX_SPLIT_RE = re.compile(r"(?<![\d.,/-])3[ ./-]?0[ ./-]?0(?:[ ./-]?\d){6}(?!\d|[ ./]\d)")
# a letter O typed for a zero: "3OO418277" (at most two)
O_FOR_ZERO_RE = re.compile(r"(?<![\w.,/-])(?=(?:[^Oo\W]*[Oo]){1,2}[^Oo\W]*\b)[\dOo]{9}(?![\w]|[.,/-]\w)")
# Not student numbers (found by scanning open course material): an ISBN, whose ten characters are nine digits
# and a check character that may be X ("ISBN: 072167335X", "0-7216-7335-X"); a run of one repeated digit
# ("111111111" in a figure); and decimal numbers with one decimal place among other separators
# ("30.0-34.9 25.0" in a chart legend). Mixed separators alone are not enough: students write "300-987 654"
# (found by E6).
ISBN_BEFORE_RE = re.compile(r"ISBN(?:-1[03])?\s*:?\s*$", re.I)
# Z25b: identifiers of a reference list (Wikipedia pages as draft sources, V7): "S2CID 23752485",
# "arXiv:1509.05053", "hdl:10092/9691", "ProQuest 301940891"; the label must come right before the number.
# Labels that are also names or titles in an upper-case roster ("ERIC", "MR") are left out.
BIBLIO_BEFORE_RE = re.compile(r"\b(?:ISSN|S2CID|arXiv|hdl|PMID|PMCID|OCLC|ProQuest|JSTOR|Bibcode|LCCN|Zbl|"
                              r"OSTI|SSRN|CiteSeerX|doi)\s*:?\s*$")
ISBN_CHECK_AFTER_RE = re.compile(r"[ -]?[Xx](?![A-Za-z0-9])")
DECIMAL_RE = re.compile(r"\d\.\d(?!\d)")


# Z22c: PDF text extraction joins equation subscripts into digit runs ("0)()()( 152402312 =-+-+- IGeGVeGee").
# A plain run of nine digits inside a formula is not a student number unless a word that names one is close.
FORMULA_CHARS = "=+-−*/()"
OPERATORS = "=+-−*"
FORMULA_NEAR_CHARS = 30  # the formula test looks at this many characters on each side, on the same line
STUDENT_WORD_RE = re.compile(r"(?i)\b(?:student|stu\w*|std\w*|id|i\.d\.|number|num|no\.?)(?!\w)|#|学号")
# words of prose ("same", "Smith"), not formula variables that extraction glued together ("GGGGGG")
LONG_WORD_RE = re.compile(r"\b[A-Za-z][a-z]{3,}\b")


def _in_formula(text: str, start: int, end: int) -> bool:
    """The digits sit in a formula: formula characters right next to them, or a line of mostly formula."""
    if STUDENT_WORD_RE.search(text[max(0, start - 25):start]) or STUDENT_WORD_RE.search(text[end:end + 12]):
        return False
    before = text[max(0, start - FORMULA_NEAR_CHARS):start].rsplit("\n", 1)[-1]
    after = text[end:end + FORMULA_NEAR_CHARS].split("\n", 1)[0]
    alone = not before.strip() and not after.strip()
    if alone:
        # alone on its line, as in a fraction or matrix that extraction laid out one row per line: the lines
        # around it decide, and a few words of the slide's prose there do not outweigh many formula characters
        before = text[max(0, start - 2 * FORMULA_NEAR_CHARS):start]
        after = text[end:end + 2 * FORMULA_NEAR_CHARS]
    left, right = before.rstrip(" ")[-1:], after.lstrip(" ")[:1]
    chars = sum(c in FORMULA_CHARS for c in before + after)
    # an operator on one side and an operator or bracket on the other; "Ann (300123456)" and
    # "Ann / 300123456 / mail" are not formulas
    if left and right and ((left in OPERATORS and right in OPERATORS + "()")
                           or (left in "()" and right in OPERATORS)):
        return True
    words = len(LONG_WORD_RE.findall(before + after))
    return chars >= 6 and (words < 3 or (alone and words < chars // 4))


def _not_a_student_number(text: str, start: int, end: int) -> bool:
    value = text[start:end]
    digits = {c for c in value if c.isdigit()}
    separators = {c for c in value if not c.isalnum()}
    before = text[max(0, start - 12):start]
    return (bool(ISBN_BEFORE_RE.search(before)) or bool(BIBLIO_BEFORE_RE.search(before))
            or bool(ISBN_CHECK_AFTER_RE.match(text, end))
            or len(digits) == 1
            or (len(value) == 9 and value.isdigit() and _in_formula(text, start, end))
            or (len(separators) > 1 and bool(DECIMAL_RE.search(value))))


@pii_recognizers.register("student_id")
class StudentIdRecognizer(PatternRecognizer):
    """9-digit student numbers (e.g. 300418277).

    Split forms ("300 418 277", "300/418/277", "3004 18277") count only next to a context word. A typed or
    misspelled "student number" phrase right before the digits ("studnet nmuber: 300.418.277") counts on its
    own (found by E6: misspelled and split numbers reached the cloud).
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="STUDENT_ID",
            patterns=[
                Pattern("nine digits", r"(?<![\d.,/-])\d{9}(?![\d.,/-]?\d)", 0.6),
                Pattern("split nine digits", SPLIT_DIGITS, 0.3),
            ],
            context=["student", "id", "number", "student number", "student id", "学号"],
        )

    def analyze(self, text, entities, nlp_artifacts=None, regex_flags=None):
        results = list(super().analyze(text, entities, nlp_artifacts, regex_flags) or [])
        for m in FUZZY_CONTEXT_RE.finditer(text):
            results.append(self._result(m.start(1), m.end(1), 0.85, "misspelled context", FUZZY_CONTEXT_RE))
        for m in ID_CONTEXT_RE.finditer(text):
            results.append(self._result(m.start(1), m.end(1), 0.85, "id context", ID_CONTEXT_RE))
        for m in PREFIX_SPLIT_RE.finditer(text):
            results.append(self._result(m.start(), m.end(), 0.6, "300 prefix", PREFIX_SPLIT_RE))
        for m in O_FOR_ZERO_RE.finditer(text):
            if sum(c.isdigit() for c in m.group()) >= 7:
                results.append(self._result(m.start(), m.end(), 0.6, "O for zero", O_FOR_ZERO_RE))
        return [r for r in results if not _not_a_student_number(text, r.start, r.end)]

    def _result(self, start: int, end: int, score: float, name: str, pattern: re.Pattern) -> RecognizerResult:
        # the context enhancer expects the explanation and metadata that pattern results carry
        explanation = self.build_regex_explanation(
            self.name, name, pattern.pattern, score, None, pattern.flags)
        return RecognizerResult("STUDENT_ID", start, end, score, analysis_explanation=explanation,
                                recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                                      RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id})
