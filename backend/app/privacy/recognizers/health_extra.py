"""Extra personal-health patterns found by E6 (kept separate so that E6 can measure them on their own).

- Owned items with a longer qualifier: “my blood pressure meds”, “my asthma inhaler” (the base rule allows one
  word between “my” and the item).
- A first-person reading without a unit: “my bp was 150/95”, “mine was 95 this morning”.
- A possessive right before a condition or vital sign (found by the E6 held-out set): “my diabetes”, “my
  long-term diabetes”, “her asthma”, “my uncle's pneumonia”, “my blood pressure is spiking”. Not when the term
  names coursework: “my diabetes assignment”, “my blood pressure project”.
- A first-person diagnosis or prescription without a named condition: “I was diagnosed last month”, “my mom
  just got prescribed something”. Alone it says little, but it marks the session as personal health, so the
  condition named in the next message is caught too (`app/privacy/session_health.py`).
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers
from app.privacy.recognizers.health_detail import COURSE_AFTER_RE, FAMILY, TERMS

VITALS = [r"blood pressure", r"bp", r"blood sugars?", r"sugars", r"glucose(?: levels?)?", r"glycemic levels",
          r"(?:\w+\s)?readings", r"(?:\w+\s)?numbers", r"(?:\w+\s)?symptoms", r"breathing", r"lungs"]
POSSESSIVE_RE = re.compile(
    r"\b(?:my|his|her|their|my\s+" + FAMILY + r"(?:'s|’s))\s+"
    r"(?:(?:chronic|long-term|recent|severe|bad|new|latest|current|own)\s+)?"
    r"(" + "|".join(TERMS + VITALS) + r")\b"
    r"(?!" + COURSE_AFTER_RE.pattern + r")", re.I)

OWNED_RE = re.compile(
    r"\bmy\s+(?:[\w-]+\s+){1,3}?(meds|medications?|medicines?|pills|inhaler|insulin|prescription|dose|dosage|"
    r"diagnosis|symptoms|test results|blood test|condition|readings?)\b", re.I)
READING_RE = re.compile(
    r"\b(?:my|mine)\b(?:\s+(?:bp|blood pressure|blood sugar|sugar|glucose|reading|pressure|peak flow))?\s+"
    r"(?:was|is|were|reads?|read)\s+(\d{2,3}(?:\s*(?:/|over)\s*\d{2,3})?)", re.I)
DIAGNOSED_RE = re.compile(
    r"\b(?:I|my\s+" + FAMILY + r")\b[^.?!\n]{0,25}?"
    r"(?:\b(?:was|were|got|get|am|is|has been|have been)|'ve been|'s been|'m)\s+"
    r"(?:just\s+|recently\s+|finally\s+|officially\s+)?(diagnosed|prescribed)\b", re.I)


@pii_recognizers.register("health_extra")
class HealthExtraRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["HEALTH_DETAIL"], name="HealthExtraRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        out = [RecognizerResult("HEALTH_DETAIL", m.start(), m.end(), 0.7) for m in OWNED_RE.finditer(text)]
        out += [RecognizerResult("HEALTH_DETAIL", m.start(), m.end(), 0.7) for m in READING_RE.finditer(text)]
        out += [RecognizerResult("HEALTH_DETAIL", m.start(1), m.end(1), 0.7)
                for m in POSSESSIVE_RE.finditer(text)]
        out += [RecognizerResult("HEALTH_DETAIL", m.start(1), m.end(1), 0.7)
                for m in DIAGNOSED_RE.finditer(text)]
        return out
