"""Presidio analyzer with our custom recognizers (design §3, step 1). Built once per spaCy model."""
import logging
import re
from dataclasses import dataclass
from functools import cache

import spacy.util
from presidio_analyzer import AnalyzerEngine, RecognizerRegistry, RecognizerResult
from presidio_analyzer.nlp_engine import NlpEngineProvider

from app.core.config import PrivacyConfig
from app.core.registry import import_submodules, pii_recognizers

log = logging.getLogger("app.privacy")
logging.getLogger("presidio-analyzer").setLevel(logging.WARNING)  # its INFO/DEBUG lines can contain text

_TITLES = ("dr. ", "dr ", "prof. ", "prof ", "professor ")


class PrivacyFilterUnavailable(RuntimeError):
    """The NLP model is missing. The app must not start without its privacy filter."""


@cache
def _nlp(spacy_model: str):
    # Presidio would try to DOWNLOAD a missing model at startup; refuse instead, with a clear message
    if not spacy.util.is_package(spacy_model):
        raise PrivacyFilterUnavailable(
            f"spaCy model '{spacy_model}' is not installed: python -m spacy download {spacy_model}")
    try:
        return NlpEngineProvider(nlp_configuration={
            "nlp_engine_name": "spacy",
            "models": [{"lang_code": "en", "model_name": spacy_model}],
        }).create_engine()
    except (OSError, ValueError) as e:
        raise PrivacyFilterUnavailable(
            f"spaCy model '{spacy_model}' is not installed: python -m spacy download {spacy_model}") from e


def custom_recognizer_names() -> list[str]:
    import_submodules("app.privacy.recognizers")
    return pii_recognizers.names()


@cache
def _engine(spacy_model: str, recognizers: tuple[str, ...]) -> AnalyzerEngine:
    """One engine per (model, custom recognizer set); the spaCy model itself is loaded once."""
    nlp = _nlp(spacy_model)
    registry = RecognizerRegistry(supported_languages=["en"])
    registry.load_predefined_recognizers(languages=["en"], nlp_engine=nlp)
    known = custom_recognizer_names()
    for name in recognizers:
        if name not in known:
            raise ValueError(f"unknown PII recognizer '{name}' (registered: {', '.join(known)})")
        registry.add_recognizer(pii_recognizers.get(name)())
    return AnalyzerEngine(registry=registry, nlp_engine=nlp, supported_languages=["en"])


@dataclass(frozen=True)
class Finding:
    type: str
    start: int
    end: int
    score: float


class PIIAnalyzer:
    def __init__(self, cfg: PrivacyConfig) -> None:
        self.cfg = cfg
        names = tuple(cfg.recognizers) if cfg.recognizers is not None else tuple(custom_recognizer_names())
        self.engine = _engine(cfg.spacy_model, names)  # fails at startup if the model is missing
        self.allow = {a.strip().lower() for a in cfg.allow_list}

    def _allowed(self, value: str) -> bool:
        v = value.strip().lower().removesuffix("'s").removesuffix("’s")
        for title in _TITLES:
            v = v.removeprefix(title)
        return v in self.allow

    def analyze(self, text: str, names: list[str] | tuple[str, ...] = (),
                usernames: list[str] | tuple[str, ...] = ()) -> list[Finding]:
        """PII findings. `names` / `usernames` are known identity values of the asking student: every
        whole-word occurrence is a finding, whatever the NER model thinks."""
        known = [Finding(kind, m.start(), m.end(), 1.0)
                 for kind, values in (("PERSON", names), ("USERNAME", usernames))
                 for v in values if v and not self._allowed(v)
                 for m in re.finditer(rf"(?<!\w){re.escape(v)}(?!\w)", text, re.I)]
        results: list[RecognizerResult] = self.engine.analyze(
            text=text, language="en", entities=list(self.cfg.entities),
            score_threshold=self.cfg.score_threshold)
        found = []
        for r in results:
            f = Finding(r.entity_type, r.start, r.end, r.score)
            if f.type == "PERSON":
                f = clean_person(text, f)
            if f and not self._allowed(text[f.start:f.end]):
                found.append(f)
        return resolve_overlaps(found + known, prefer=tuple(self.cfg.local_only_types))


_EPONYM_NOUNS = {"score", "scores", "kappa", "test", "index", "coefficient", "theorem", "rule", "law",
                 "method", "distribution", "correlation", "criterion", "criteria", "curve", "plot", "disease",
                 "syndrome", "sign", "scale", "equation", "formula", "algorithm", "statistic", "ratio",
                 "classification",
                 "unit", "units", "optimizer", "optimiser", "j", "estimator", "model", "network", "loss",
                 "thyroiditis", "effect", "principle", "reflex", "maneuver", "manoeuvre", "phenomenon"}  # E6
_NEXT_WORD = re.compile(r"(?:'s|’s|')?\s+([A-Za-z]+)")
_NAME_WORD = re.compile(r"[A-ZÀ-ÖØ-Ý][\w'’-]+")
# French function words that English NER sometimes glues to a name or tags as one ("J'ai de l'asthme")
_FR_LEAD = re.compile(r"(?i)(?:je m['’]appelle|j['’]ai(?:\s+(?:de|du|des|eu)(?:\s+l['’])?)?|je suis|c['’]est|"
                      r"je|mon|ma|mes|qu['’]est-ce que|l['’])\s*")


def clean_person(text: str, f: Finding) -> Finding | None:
    """Fix common NER mistakes on course text. Returns None if the finding is not a person.

    - "Tom Becker 300477120": cut the span before the first digit (the number is found as STUDENT_ID).
    - "DICOM metadata": spans containing an all-caps acronym are not names.
    - "Cohen's kappa", "Brier score": eponyms of statistics, units and diseases are not people here.
    - "Je m'appelle Chloé Martin", "J'ai de l'asthme": leading French function words are cut; nothing left
      that looks like a name → not a person.
    """
    value = text[f.start:f.end]
    lead = _FR_LEAD.match(value)  # "Je m'appelle Chloé Martin" (English NER on French text)
    if lead:
        f = Finding(f.type, f.start + lead.end(), f.end, f.score)
        value = value[lead.end():]
        if not value.strip():
            return None
    digit = re.search(r"\d", value)
    if digit:
        value = value[:digit.start()].rstrip(" ,;(-")
        if not value:
            return None
        f = Finding(f.type, f.start, f.start + len(value), f.score)
    if any("一" <= ch <= "鿿" for ch in value):
        return f  # Chinese names (zh_person recognizer): the Latin-script rules below do not apply
    words = value.split()
    if not any(_NAME_WORD.fullmatch(w.removesuffix("'s").removesuffix("’s")) for w in words):
        return None  # symbols or lower-case words: "FN=", "−"
    if any(len(w) >= 2 and w.isupper() and w.isalpha() for w in words):
        return None
    nxt = _NEXT_WORD.match(text, f.end)  # "Cohen's kappa", "Compute Cohen's kappa", "Brier score"
    if nxt and nxt.group(1).lower() in _EPONYM_NOUNS:
        return None
    return f


def resolve_overlaps(findings: list[Finding], prefer: tuple[str, ...] = ()) -> list[Finding]:
    """Keep non-overlapping findings, preferring longer spans, then higher scores.

    A PERSON span that overlaps a `prefer` finding (the local-only types) is dropped first: NER sometimes tags
    a whole clause such as "J'ai de l'asthme" as a person, which would otherwise hide the health detail from
    the cloud_safe decision (found by E6). Pattern-based types keep the usual length rule.
    """
    pinned = [p for p in findings if p.type in prefer]
    findings = [f for f in findings
                if not (f.type == "PERSON" and any(f.start < p.end and p.start < f.end for p in pinned))]
    kept: list[Finding] = []
    for f in sorted(findings, key=lambda f: (-(f.end - f.start), -f.score, f.start)):
        if all(f.end <= k.start or f.start >= k.end for k in kept):
            kept.append(f)
    return sorted(kept, key=lambda f: f.start)
