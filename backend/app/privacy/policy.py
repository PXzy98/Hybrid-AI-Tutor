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
