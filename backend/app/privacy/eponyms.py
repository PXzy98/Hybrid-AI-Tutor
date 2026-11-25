"""Fixed course phrases that hold a surname ("Kirchhoff's current law"): eponym_terms.yaml (task Z22c)."""
import re
from functools import cache
from pathlib import Path

import yaml

TERMS_FILE = Path(__file__).resolve().parent / "eponym_terms.yaml"


def _phrase_pattern(phrase: str) -> str:
    """A regex for one phrase: optional possessive after the first word, optional plural of the last word."""
    first, _, rest = phrase.strip().partition(" ")
    parts = [re.escape(first) + (r"(?:['’]s|['’])?" if rest else "")]
    parts += [re.escape(w) for w in rest.split()]
    return r"\s+".join(parts) + r"s?(?![\w])"


@cache
def _terms_re() -> re.Pattern:
    data = yaml.safe_load(TERMS_FILE.read_text(encoding="utf-8")) or {}
    terms = data.get("terms") or []
    if not terms or any(" " not in t.strip() for t in terms):
        raise ValueError("eponym_terms.yaml: fixed phrases of at least two words only, never a bare surname")
    patterns = sorted((_phrase_pattern(t) for t in terms), key=len, reverse=True)
    return re.compile(r"(?<![\w])(?:" + "|".join(patterns) + ")", re.I)


def inside_course_term(text: str, start: int, end: int) -> bool:
    """True when text[start:end] lies inside a fixed phrase of eponym_terms.yaml."""
    lo = max(0, start - 60)
    return any(m.start() <= start and end <= m.end() for m in _terms_re().finditer(text, lo, end + 60))
