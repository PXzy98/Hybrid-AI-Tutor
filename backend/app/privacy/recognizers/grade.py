from presidio_analyzer import Pattern, PatternRecognizer

from app.core.registry import pii_recognizers

# a score: 58/100, 62%, 62 percent, or a letter grade (case-sensitive, so "I got a lot" is not a grade)
_SCORE = r"(?:\d{1,3}(?:\.\d+)?\s?(?:/\s?\d{1,3}|%|percent)|(?-i:[ABCDF][+-]?)(?![\w+-]))"


@pii_recognizers.register("grade")
class GradeRecognizer(PatternRecognizer):
    """A student's own results: "I got 58/100", "my GPA dropped to 2.9", "I failed the midterm", "61 分"."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="GRADE",
            patterns=[
                Pattern("i got score",
                        r"(?i)\bI\s+(?:\w+\s+){0,2}?(?:got|get|received|scored|earned)\s+(?:an?\s+|only\s+)?"
                        + _SCORE, 0.7),
                Pattern("my grade",
                        r"(?i)\bmy\s+(?:\w+\s+)?(?:gpa|cgpa|grade|grades|mark|marks|score|average|result)\b"
                        r"[^.?!\n]{0,25}?\b\d{1,3}(?:\.\d{1,2})?(?:\s?(?:%|/\s?\d{1,3}|percent))?", 0.7),
                Pattern("i failed", r"(?i)\bI\s+(?:failed|flunked)\s+(?:the|my|this)\s+\w+", 0.6),
                Pattern("zh score", r"\d{1,3}(?:\.\d+)?\s?分", 0.6),
            ],
        )
