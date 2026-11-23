"""Routing policy on top of the PII findings (Beta): when must a question stay local although no personal
health detail was found?

`identified_health_topic`: the message identifies a person (a name, student number, e-mail, phone or other ID
was found) AND mentions a health topic (a condition, symptom, medicine or vital sign, even in a general
wording). The identifier is redacted either way, but if the health detail was missed, the cloud would receive
"<PERSON_1> ... diabetes ..." and the link between a person and a condition would only rest on the redaction.
Keeping such questions local trades some answer quality for privacy; it is a setting
(`privacy.local_if_identified_health_topic`), measured in E6 (cloud exposure vs needless local routing).
"""
import re

from app.privacy.analyzer import Finding
from app.privacy.recognizers.health_detail import TERM_RE

IDENTIFIERS = {"PERSON", "STUDENT_ID", "EMAIL_ADDRESS", "PHONE_NUMBER", "USERNAME", "ID_NUMBER",
               "HEALTH_CARD"}
TOPIC_RE = re.compile(
    TERM_RE.pattern + r"|\b(?:blood pressure|bp|blood sugar|glucose|cholesterol|heart rate|breathing|lungs|"
    r"symptoms?|diagnos(?:is|ed)|treatment|doctor|hospital|clinic|sick|ill|illness|health)\b", re.I)


def identified_health_topic(text: str, findings: list[Finding]) -> bool:
    if not any(f.type in IDENTIFIERS for f in findings):
        return False
    # ignore topic words inside a finding (a name such as "Asthma Clinic Ltd" is not a topic mention)
    spans = [(f.start, f.end) for f in findings]
    return any(not any(a <= m.start() < b for a, b in spans) for m in TOPIC_RE.finditer(text))


# Z22d: first-person wordings that may carry a health detail no rule knows, so the local model's check
# (`privacy.llm_check`) also reads them: "I have a <word the rules do not know>", "I got/caught ...",
# "unwell", "medical", "emergency", and reasons for a late or missed piece of work ("I need an extension
# because ..."). Course nouns after "I have a" ("a question", "a bug") do not count, so ordinary course
# questions still skip the check.
COURSE_NOUNS = (
    r"question|questions|doubt|quiz|exam|test|midterm|final|assignment|homework|deadline|lab|project|problem|"
    r"issue|bug|error|idea|suggestion|request|concern|meeting|class|lecture|presentation|job|interview|"
    r"conflict|clash|follow-up|look|chance|copy|draft|version|account|login|grade|mark|score|few|couple|lot|"
    r"bit|hard|good|great|quick|small|simple|general|similar|different|new|second|third|last|list|function|"
    r"program|loop|variable|file|dataset|array|string|matrix|circuit|signal|team|group|partner|tutorial|"
    r"report|paper|thesis|feeling|way|plan|goal|hunch|habit|tendency|laptop|computer|phone"
)
PERSONAL_HINT_RE = re.compile(
    r"\b(?:I|I've|I'd|we)\s+(?:have|had|got|get|'ve got|have got|caught|developed|contracted|picked up)\s+"
    r"(?:a|an|some|this|that)\s+(?!(?:" + COURSE_NOUNS + r")\b)[a-z]"
    r"|\b(?:I'm|I am|I was|I've been|I have been|I feel|I felt|I'm feeling)\s+(?:\w+\s+)?"
    r"(?:unwell|not well|not feeling well|under the weather|in pain|recovering|bedridden|out sick)\b"
    r"|\b(?:medical|emergency|urgent care|er visit|walk-in|prescribed|prescription|appointment|surgeon|"
    r"nurse|physician|specialist|paramedic|ambulance|bed rest|sick note|doctor's note)\b"
    r"|\b(?:extension|late|missed|miss|absent|absence|accommodations?|defer(?:ral|red)?)\b[^.?!\n]{0,80}?"
    r"\b(?:because|due to|since|as)\s+(?:of\s+)?(?:I|my|a|an|the)\b",
    re.I,
)


def may_reveal_health(text: str) -> bool:
    """Whether the local model's second check should read a cloud-bound question: it names a health topic, or
    a first-person wording may carry a health detail the rules do not know."""
    return bool(TOPIC_RE.search(text) or PERSONAL_HINT_RE.search(text))
