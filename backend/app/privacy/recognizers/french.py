"""French phrasings (uOttawa is bilingual), found as a gap by E6.

spaCy's English model does not find names in “Je m'appelle Chloé Martin”, and the English health-detail rule
does not know “j'ai de l'asthme”. These recognizers cover the self-introduction, personal health and grade
patterns in French. They follow the English rules: a health term counts only when attributed to the student or
a relative, never in a general question (“Qu'est-ce que l'asthme?”).
"""
import re

from presidio_analyzer import EntityRecognizer, Pattern, PatternRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

NAME = r"(?:[A-ZÀ-ÖØ-Ý][\w'’-]+)(?:\s+[A-ZÀ-ÖØ-Ý][\w'’-]+){0,2}"
INTRO_RE = re.compile(r"(?:je m'appelle|je m’appelle|c'est|c’est|je suis|mon ami(?:e)?|ma copine|mon copain)"
                      r"\s+(" + NAME + r")")
FR_TERMS = (r"(?:asthme|asthmatique|diabète|diabétique|migraines?|AVC|hypertension|tension élevée|metformine|"
            r"insuline|cancer|dépression|déprimé(?:e)?|anxiété|pneumonie|allergies?|épilepsie|enceinte|inhalateur|"
            r"antibiotiques?|crise cardiaque)")
FR_ATTR = (r"(?:j'ai|j’ai|je fais|je prends|je suis|j'avais|mon (?:père|frère|fils|ami|copain|grand-père)|"
           r"ma (?:mère|soeur|sœur|fille|amie|copine|grand-mère))")
HEALTH_RE = re.compile(FR_ATTR + r"[^.?!\n]{0,40}?\b(" + FR_TERMS + r")\b", re.I)


@pii_recognizers.register("fr_person")
class FrenchPersonRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["PERSON"], name="FrenchPersonRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        out = []
        for m in INTRO_RE.finditer(text):
            name = m.group(1)
            # "je suis étudiante" / "c'est important": the next word must look like a name (capitalized)
            if name.split()[0].lower() in {"le", "la", "un", "une", "très", "important"}:
                continue
            out.append(RecognizerResult("PERSON", m.start(1), m.end(1), 0.75))
        return out


@pii_recognizers.register("fr_health")
class FrenchHealthRecognizer(EntityRecognizer):
    def __init__(self) -> None:
        super().__init__(supported_entities=["HEALTH_DETAIL"], name="FrenchHealthRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        return [RecognizerResult("HEALTH_DETAIL", m.start(1), m.end(1), 0.8)
                for m in HEALTH_RE.finditer(text)]


@pii_recognizers.register("fr_grade")
class FrenchGradeRecognizer(PatternRecognizer):
    def __init__(self) -> None:
        super().__init__(
            supported_entity="GRADE",
            patterns=[Pattern("j'ai eu", r"(?i)\bj['’]ai (?:eu|obtenu|reçu)\s+\d{1,3}(?:[.,]\d+)?"
                                          r"\s?(?:/\s?\d{1,3}|%|pour cent)", 0.7),
                      Pattern("ma note", r"(?i)\bma (?:note|moyenne)\b[^.?!\n]{0,20}?\d{1,3}(?:[.,]\d+)?"
                                         r"\s?(?:/\s?\d{1,3}|%)?", 0.7),
                      Pattern("j'ai échoué",
                              r"(?i)\bj['’]ai (?:échoué|raté)\s+(?:l'|à l'|mon|ma|le|la)\s?\w+", 0.6)],
        )
