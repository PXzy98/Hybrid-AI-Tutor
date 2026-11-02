"""Contact details written to dodge simple patterns (Beta, privacy filter upgrade; E6 "hard" cases).

- Obfuscated e-mails: “priya.raman AT uottawa DOT ca”, “maya[at]gmail[dot]com”, “sam (at) mail (dot) com”.
- Phone numbers without separators next to a phone word: “call me at 6135550142”.
- Phone numbers spelled out: “six one three five five five zero one four two” (seven or more digit words).
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

AT = r"(?:\s*[\[({<]\s*at\s*[\])}>]\s*|\s+(?:at|AT)\s+|\s*@\s*)"
DOT = r"(?:\s*[\[({<]\s*dot\s*[\])}>]\s*|\s+(?:dot|DOT)\s+)"
OBFUSCATED_EMAIL_RE = re.compile(r"\b[\w.+-]+" + AT + r"[\w-]+(?:" + DOT + r"[\w-]+)+\b")
PHONE_WORD = r"(?:phone|call|cell|mobile|text|number|tel|reach me|contact)"
BARE_PHONE_RE = re.compile(r"\b" + PHONE_WORD + r"\b[^.?!\n\d]{0,20}(?<!\d)((?:\+?1)?\d{10})(?!\d)", re.I)
# a local seven-digit number next to a phone word: "can i reach dr. smith at 555-0123", "text me: 555 0199"
LOCAL_PHONE_RE = re.compile(r"\b(?:" + PHONE_WORD[3:-1] + r"|reach)\b[^.?!\n\d]{0,25}"
                            r"(?<![\d-])(\d{3}[-. ]\d{4})"
                            r"(?![\d-]|[ .]\d)", re.I)
DIGIT_WORD = r"(?:zero|oh|one|two|three|four|five|six|seven|eight|nine)"
SPELLED_RE = re.compile(r"\b" + DIGIT_WORD + r"(?:[\s,-]+" + DIGIT_WORD + r"){6,}\b", re.I)


@pii_recognizers.register("contact_extra")
class ContactExtraRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["EMAIL_ADDRESS", "PHONE_NUMBER"], name="ContactExtraRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        out = [RecognizerResult("EMAIL_ADDRESS", m.start(), m.end(), 0.8)
               for m in OBFUSCATED_EMAIL_RE.finditer(text)]
        out += [RecognizerResult("PHONE_NUMBER", m.start(1), m.end(1), 0.8)
                for m in BARE_PHONE_RE.finditer(text)]
        out += [RecognizerResult("PHONE_NUMBER", m.start(), m.end(), 0.7) for m in SPELLED_RE.finditer(text)]
        out += [RecognizerResult("PHONE_NUMBER", m.start(1), m.end(1), 0.7)
                for m in LOCAL_PHONE_RE.finditer(text)]
        return out
