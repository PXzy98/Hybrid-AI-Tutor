from presidio_analyzer import Pattern, PatternRecognizer

from app.core.registry import pii_recognizers


@pii_recognizers.register("student_id")
class StudentIdRecognizer(PatternRecognizer):
    """9-digit student numbers (e.g. 300418277). Spaced forms count only next to context words."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="STUDENT_ID",
            patterns=[
                Pattern("nine digits", r"(?<![\d.,/-])\d{9}(?![\d.,/-]?\d)", 0.6),
                Pattern("spaced nine digits", r"(?<![\d-])\d{3}[ -]\d{3}[ -]\d{3}(?![\d-])", 0.3),
            ],
            context=["student", "id", "number", "student number", "student id", "学号"],
        )
