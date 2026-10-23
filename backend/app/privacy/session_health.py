"""Personal health details spread over several messages of one session (found by E6).

"I was diagnosed last month." / "It's type 2 diabetes, what should I eat?": each message alone may look general,
but together they describe the student. Once a student turn of the session held a personal health detail (its
stored, sanitized text contains a <HEALTH_DETAIL_n> placeholder), a later question that names a condition or
medicine counts as personal too, and a question that refers back to it ("is it dangerous?") is kept off the
cloud. Only the history the API passes in (`sessions.history_turns`) is considered.
"""
import re

from app.core.schemas import Turn
from app.privacy.analyzer import Finding
from app.privacy.recognizers.health_detail import COURSE_AFTER_RE, TERM_RE, WORD_RE, fuzzy_term

HEALTH_PLACEHOLDER_RE = re.compile(r"<HEALTH_DETAIL_\d+>", re.I)
REFERS_BACK_RE = re.compile(
    r"\b(?:it|this|that|these|those|they|them|"
    r"the\s+(?:condition|diagnosis|disease|illness|medication|medicine|meds|pills|treatment|symptoms?))\b", re.I)
SCORE = 0.8


def had_personal_health(history: list[Turn]) -> bool:
    """True if an earlier student turn of the session held a personal health detail."""
    return any(t.role == "student" and HEALTH_PLACEHOLDER_RE.search(t.text) for t in history)


def follow_up_findings(text: str) -> list[Finding]:
    """Condition and medicine names in a follow-up question, exact or misspelled, outside coursework phrases."""
    found = [Finding("HEALTH_DETAIL", m.start(), m.end(), SCORE)
             for m in TERM_RE.finditer(text) if not COURSE_AFTER_RE.match(text, m.end())]
    found += [Finding("HEALTH_DETAIL", m.start(), m.end(), SCORE)
              for m in WORD_RE.finditer(text) if fuzzy_term(m.group()) and not COURSE_AFTER_RE.match(text, m.end())]
    return found


def refers_back(text: str) -> bool:
    return bool(REFERS_BACK_RE.search(text))
