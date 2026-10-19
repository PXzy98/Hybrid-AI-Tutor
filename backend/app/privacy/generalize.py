"""`privacy.health_detail_policy: generalize`: turn a personal health question into a general one.

"I have asthma, can I still run?" → "Can a person with asthma run safely?". The local model (inside the
boundary) writes the rewrite from the ORIGINAL question; the rewrite is then checked again, and only a rewrite
that passes every check may go to the cloud. Anything else keeps the question local.

E6 utility experiment (eval/privacy-filter/results/utility.md): placeholders over the health detail score 3.07
of 5 against the original answer, the hypothetical rewrite 4.47. Off by default: the client and the course's
ethics rules decide whether a de-identified health question may reach the cloud.
"""
import re

from app.llm.base import LLMClient, LLMError
from app.privacy.analyzer import PIIAnalyzer

PROMPT = (
    "Rewrite the student's message below as ONE general question about a hypothetical person, so that it "
    "says nothing about the student or anyone they know: no names, no 'I', 'my', 'me', no relatives, no "
    "ages, dates, readings, doses or other numbers. Keep the medical topic and what the student wants to "
    "know. Reply with the rewritten question only.\n\nMessage: "
)
FIRST_PERSON_RE = re.compile(r"\b(?:I|I'm|I've|I'd|me|my|mine|we|our|us)\b", re.I)
DIGIT_RE = re.compile(r"\d")
MAX_CHARS = 300


async def generalize(question: str, llm: LLMClient, analyzer: PIIAnalyzer, names: list[str],
                     usernames: list[str]) -> str | None:
    """The rewritten question, or None if the rewrite failed or did not pass the checks."""
    try:
        result = await llm.complete([{"role": "user", "content": PROMPT + question}], max_tokens=120)
    except LLMError:
        return None
    lines = [ln.strip().strip('"“”') for ln in result.text.strip().splitlines() if ln.strip()]
    rewrite = lines[0] if lines else ""
    if not rewrite or len(rewrite) > MAX_CHARS:
        return None
    if FIRST_PERSON_RE.search(rewrite) or DIGIT_RE.search(rewrite):
        return None  # still personal, or a reading, dose, date or ID
    if analyzer.analyze(rewrite, names, usernames):
        return None  # any finding at all: a name, a relative's condition, an ID
    return rewrite
