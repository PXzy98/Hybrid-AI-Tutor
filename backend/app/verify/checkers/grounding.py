"""Grounding (design §7.1 step 8): is the answer supported by the retrieved course material?

Heuristic: an answer sentence counts as supported when at least 20% of its content words appear in one
passage. If fewer than half of the sentences are supported, warn. Without passages there is nothing to
check against, so the check passes with "no material".
"""
import re

from app.core.registry import checkers
from app.core.schemas import CheckResult, RequestContext

NAME = "grounding"
SENTENCE_OVERLAP = 0.2
SUPPORTED_SHARE = 0.5
MIN_WORDS = 4  # very short sentences ("Good question!") are ignored
WORD_RE = re.compile(r"[a-z]{3,}")
STOPWORDS = set("""the and for are but not you your with this that from have has had was were will would can
could should may might their there they them then than what when where which who why how all any some
more most less much many also into onto over under about after before because while does did done its
our out own same such too very just only both each few other these those here been being""".split())


def content_words(text: str) -> set[str]:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS}


def supported_share(answer: str, passages: list[str]) -> tuple[float, int]:
    """(share of sentences supported by some passage, number of sentences considered)."""
    sources = [content_words(p) for p in passages]
    considered = supported = 0
    for sentence in re.split(r"(?<=[.!?])\s+|\n+", answer):
        words = content_words(sentence)
        if len(words) < MIN_WORDS:
            continue
        considered += 1
        if any(len(words & src) / len(words) >= SENTENCE_OVERLAP for src in sources):
            supported += 1
    return (supported / considered if considered else 1.0), considered


@checkers.register(NAME)
class GroundingChecker:
    name = NAME

    def __init__(self, services) -> None:
        self.services = services

    def check(self, ctx: RequestContext) -> CheckResult:
        if not ctx.passages:
            return CheckResult(name=NAME, status="pass", detail="no material")
        share, n = supported_share(ctx.answer or "", [c.text for c in ctx.passages])
        detail = f"{share:.0%} of {n} sentences supported"
        return CheckResult(name=NAME, status="pass" if share >= SUPPORTED_SHARE else "warn", detail=detail)
