"""`privacy.health_detail_policy: generalize`: turn a personal health question into a general one.

"I have asthma, can I still run?" → "Can a person with asthma run safely?". The local model (inside the
boundary) writes the rewrite from the ORIGINAL question; the rewrite is then checked again, and only a rewrite
that passes every check may go to the cloud. Anything else keeps the question local.

E6 utility experiment (eval/privacy-filter/results/utility.md): placeholders over the health detail score 3.07
of 5 against the original answer, the hypothetical rewrite 4.47. Enabled in config.yaml since 20 Oct 2026,
after the professor approved sending de-identified, generalized health questions to the cloud.
"""
import re

from app.llm.base import LLMClient, LLMError
from app.privacy.analyzer import PIIAnalyzer

PROMPT = (
    "Rewrite the student's message below as ONE general question about a hypothetical person, so that it "
    "says nothing about the student or anyone they know: no names, no 'I', 'my', 'me', no relatives, no "
    "ages, dates, doses or other personal numbers. Describe readings in words instead of numbers (for "
    "example 'a very high blood pressure reading'). Keep the medical topic, the names of conditions and "
    "medicines (including numbers that are part of a name, such as 'type 2 diabetes' or 'GLP-1'), and "
    "what the student wants to know. Reply with the rewritten question only.\n\nMessage: "
)
FIRST_PERSON_RE = re.compile(r"\b(?:I|I'm|I've|I'd|me|my|mine|we|our|us)\b", re.I)
# A specific value that could belong to someone: a reading (160/100), a quantity with a unit (5 mg, 3 weeks,
# 72 years, 2 puffs), a decimal, a number of three or more digits (an ID, a glucose value), a date.
# Numbers inside names stay allowed: "type 2 diabetes", "stage 1", "GLP-1", "SGLT2", "COVID-19", "A1C".
NUMBER_RE = re.compile(
    r"\b\d+\s*(?:/|over)\s*\d+\b"
    r"|\b\d+(?:[.,]\d+)?\s*(?:mg|mcg|µg|g|ml|units?|iu|%|percent|mm\s?hg|mmol|kg|lbs?|pounds?|years?|yrs?|"
    r"months?|weeks?|days?|hours?|minutes?|times|am|pm|bpm|pills?|tablets?|puffs?|doses?|injections?|shots?)\b"
    r"|\b\d+-(?:year|month|week|day)"
    r"|\b\d+[.,]\d+\b|\b\d{3,}\b"
    r"|\b(?:jan|feb|mar|apr|may|jun|jul|aug|sep|oct|nov|dec)[a-z]*\.?\s+\d{1,2}\b",
    re.I,
)
# a grade in the rewrite: a health question does not need it, and the filter can miss free phrasing in the
# original ("like a solid B"; E6 held-out T041)
GRADE_RE = re.compile(r"\b(?-i:[A-F])[+-]?\s+(?:grade|average)\b"  # the letter itself must be upper case
                      r"|\b(?:grade|mark)\s+(?:of\s+)?(?:an?\s+)?(?-i:[A-F])[+-]?(?![\w+-])"
                      r"|\bGPA\b|\bgrade point average\b", re.I)
MAX_CHARS = 300


async def generalize(question: str, llm: LLMClient, analyzer: PIIAnalyzer, names: list[str],
                     usernames: list[str], known_values: list[str] | tuple[str, ...] = ()) -> str | None:
    """The rewritten question, or None if the rewrite failed or did not pass the checks.

    `known_values`: the identifiers found in the original question (names, IDs, contact details, grades).
    A rewrite that repeats any of them is rejected, even if the filter would not find it again out of context
    (a bare "B+" is not a grade to the grade recognizer; found by E6).
    """
    try:
        result = await llm.complete([{"role": "user", "content": PROMPT + question}], max_tokens=120)
    except LLMError:
        return None
    lines = [ln.strip().strip('"“”') for ln in result.text.strip().splitlines() if ln.strip()]
    rewrite = lines[0] if lines else ""
    if not rewrite or len(rewrite) > MAX_CHARS:
        return None
    if FIRST_PERSON_RE.search(rewrite) or NUMBER_RE.search(rewrite) or GRADE_RE.search(rewrite):
        return None  # still personal, or a reading, dose, date, ID or grade
    if any(re.search(rf"(?<!\w){re.escape(v)}(?!\w)", rewrite, re.I) for v in known_values if v.strip()):
        return None  # repeats an identifier of the original question
    if analyzer.analyze(rewrite, names, usernames):
        return None  # any finding at all: a name, a relative's condition, an ID
    return rewrite
