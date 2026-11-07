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
                # "My mark on quiz 2 was 13/20": reach the score, not the first number (the longer span wins)
                Pattern("my grade score",
                        r"(?i)\bmy\s+(?:\w+\s+)?(?:grade|grades|mark|marks|score|result)\b"
                        r"[^.?!\n]{0,30}?\b\d{1,3}(?:\.\d{1,2})?\s?(?:%|/\s?\d{1,3}|percent)", 0.7),
                Pattern("i failed", r"(?i)\bI\s+(?:failed|flunked)\s+(?:the|my|this)\s+"
                                    r"(?:(?:first|second|last|final)\s+)?\w+", 0.6),
                # letter grades and GPAs without "I got" (found by the E6 held-out set):
                # "my midterm was a weak C", "My grade is D+", "a 3.8 GPA", "My GPA is hovering around 3.2"
                Pattern("my letter grade",
                        r"(?i:\bmy\s+(?:[\w-]+\s+){0,3}?(?:grade|mark|score|result|midterm|final|exam|quiz|"
                        r"assignment|essay|lab)\b[^.?!\n]{0,20}?\b(?:was|is|=|:)\s+(?:a\s+|an\s+|just\s+an?\s+|"
                        r"only\s+an?\s+|an?\s+(?:weak|solid|low|high)\s+)?)[A-F][+-]?(?![\w+-])", 0.7),
                Pattern("gpa value",
                        r"(?i)\b(?:[0-4]\.\d{1,2}\s?c?gpa\b|"
                        r"c?gpa\s+(?:is|of|was|=|:)?\s*(?:\w+\s+){0,2}?[0-4]\.\d{1,2}\b)", 0.7),
                Pattern("zh score", r"\d{1,3}(?:\.\d+)?\s?分", 0.6),
            ],
        )
