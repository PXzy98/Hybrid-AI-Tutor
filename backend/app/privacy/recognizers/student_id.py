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
# a letter O typed for a zero: "3OO418277" (at most two)
O_FOR_ZERO_RE = re.compile(r"(?<![\w.,/-])(?=(?:[^Oo\W]*[Oo]){1,2}[^Oo\W]*\b)[\dOo]{9}(?![\w]|[.,/-]\w)")


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
        for m in O_FOR_ZERO_RE.finditer(text):
            if sum(c.isdigit() for c in m.group()) >= 7:
                results.append(self._result(m.start(), m.end(), 0.6, "O for zero", O_FOR_ZERO_RE))
        return results

    def _result(self, start: int, end: int, score: float, name: str, pattern: re.Pattern) -> RecognizerResult:
        # the context enhancer expects the explanation and metadata that pattern results carry
        explanation = self.build_regex_explanation(
            self.name, name, pattern.pattern, score, None, pattern.flags)
        return RecognizerResult("STUDENT_ID", start, end, score, analysis_explanation=explanation,
                                recognition_metadata={RecognizerResult.RECOGNIZER_NAME_KEY: self.name,
                                                      RecognizerResult.RECOGNIZER_IDENTIFIER_KEY: self.id})
