"""Canadian identifiers found as gaps by E6: postal codes, Ontario health card numbers, SIN, hospital
record numbers.

Health card and SIN patterns are only reported with a context word ("OHIP", "health card", "SIN"), because a
bare group of 9-10 digits is just as likely a phone number, a student number or a lab value.
"""
from presidio_analyzer import Pattern, PatternRecognizer

from app.core.registry import pii_recognizers

# Canada Post: no D, F, I, O, Q, U; first letter also not W or Z
_POSTAL = r"(?i:\b[ABCEGHJ-NPRSTVXY]\d[ABCEGHJ-NPRSTV-Z][ -]?\d[ABCEGHJ-NPRSTV-Z]\d\b)"


@pii_recognizers.register("postal_code")
class PostalCodeRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entity="POSTAL_CODE",
                         patterns=[Pattern("canadian postal code", _POSTAL, 0.6)],
                         context=["postal", "code", "live", "address"])


@pii_recognizers.register("health_card")
class HealthCardRecognizer(PatternRecognizer):
    """Ontario health card (OHIP): 10 digits, often 4-3-3, optionally a 2-letter version code."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="HEALTH_CARD",
            patterns=[Pattern("ohip", r"(?<![\d-])\d{4}[ -]?\d{3}[ -]?\d{3}(?:[ -]?[A-Z]{2})?(?![\w-])",
                              0.3)],
            # single words: Presidio matches token lemmas
            context=["ohip", "health", "card", "carte", "santé"],
        )


@pii_recognizers.register("id_number")
class IdNumberRecognizer(PatternRecognizer):
    """Social insurance numbers (with context) and hospital medical record numbers."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="ID_NUMBER",
            patterns=[Pattern("sin", r"(?<![\d-])\d{3}[ -]?\d{3}[ -]?\d{3}(?![\d-])", 0.2),
                      Pattern("mrn", r"(?i)\b(?:MRN|medical record|record number)\s*(?:number|no\.?|#|:)?"
                              r"\s*\d{5,10}\b", 0.7)],
            context=["sin", "social", "insurance", "nas"],  # single words: Presidio matches token lemmas
        )
