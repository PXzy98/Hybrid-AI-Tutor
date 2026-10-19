"""Dates of birth and street addresses (E6 gaps).

A date counts only next to "born", "DOB", "date of birth" or "birthday": dates in general ("since March",
"the 2017 guideline") are course content, not personal data. Ages are deliberately NOT redacted: age is
relevant to many health-education answers (blood pressure targets, screening) and is a weak identifier alone.
"""
from presidio_analyzer import Pattern, PatternRecognizer

from app.core.registry import pii_recognizers

_MONTH = (r"(?:Jan(?:uary)?|Feb(?:ruary)?|Mar(?:ch)?|Apr(?:il)?|May|June?|July?|Aug(?:ust)?|"
          r"Sep(?:t(?:ember)?)?|Oct(?:ober)?|Nov(?:ember)?|Dec(?:ember)?|janvier|février|mars|avril|mai|juin|juillet|août|septembre|"
          r"octobre|novembre|décembre)")
_DATE = (r"(?:\d{1,2}\s+" + _MONTH + r"\s+\d{4}|" + _MONTH + r"\s+\d{1,2},?\s+\d{4}|\d{4}-\d{2}-\d{2}|"
         r"\d{1,2}/\d{1,2}/\d{2,4})")
_STREET = (r"(?:Street|St|Avenue|Ave|Road|Rd|Boulevard|Blvd|Drive|Lane|Ln|Crescent|Cres|Way|Court|Ct|"
           r"Place|Pl|Parkway|Pkwy|Terrace|Circle|rue|avenue|boulevard|chemin)")


@pii_recognizers.register("date_of_birth")
class DateOfBirthRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="DATE_OF_BIRTH",
            patterns=[Pattern("dob", r"(?i)\b(?:born(?:\s+on)?|DOB|date of birth|birthday(?:\s+is)?|"
                                     r"né(?:e)?\s+le)\s*[:\-]?\s*" + _DATE, 0.75)],
        )


@pii_recognizers.register("address")
class StreetAddressRecognizer(PatternRecognizer):
    """“75 Laurier Ave E”, “1200 Bank Street, unit 4”, “12 rue Rideau”."""

    def __init__(self) -> None:
        super().__init__(
            supported_entity="ADDRESS",
            patterns=[
                Pattern("number street type",
                        r"\b\d{1,5}\s+(?:[A-Z][\w'.-]*\s+){1,3}" + _STREET + r"\b\.?(?:\s+[NSEW]\b)?"
                        r"(?:,?\s*(?:unit|apt\.?|apartment|suite)\s*\d+)?", 0.6),
                Pattern("french street",
                        r"(?i)\b\d{1,5},?\s+(?:rue|avenue|boulevard|chemin)\s+(?:[\w'-]+\s?){1,3}", 0.6),
            ],
        )
