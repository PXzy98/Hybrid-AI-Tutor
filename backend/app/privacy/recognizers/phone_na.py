from presidio_analyzer import Pattern, PatternRecognizer

from app.core.registry import pii_recognizers


@pii_recognizers.register("phone_na")
class NorthAmericanPhoneRecognizer(PatternRecognizer):
    """613-555-0148, (613) 555-0148, +1 613 555 0148. Separators are required, so decimals never match.

    Presidio's own phone recognizer stays active, but it scores below the threshold without a context word.
    """

    def __init__(self) -> None:
        super().__init__(
            supported_entity="PHONE_NUMBER",
            patterns=[Pattern(
                "NANP with separators",
                r"(?<![\d.])(?:\+?1[ .-])?(?:\(\d{3}\)\s?|\d{3}[ .-])\d{3}[ .-]\d{4}(?![\d.]\d)",
                0.6,
            )],
            context=["phone", "call", "cell", "mobile", "text", "number"],
        )
