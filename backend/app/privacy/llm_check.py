"""Second check by the local model before a question goes to the cloud (`privacy.llm_check`, on by default
since Z22d).

The rules miss personal health details written in ways they do not know. When the rules would send a
question to the cloud and it may reveal health (`policy.may_reveal_health`: a health topic, or a first-person
wording such as "I have a ..." or a reason for late work), the local model (inside the privacy boundary) reads
the redacted text and answers one yes/no question: does it reveal a health detail of the student or of a real
person they mention? Yes keeps the question local. It sees the redacted text, never the placeholder mapping;
ordinary course questions do not trigger it, so most questions pay no latency. A failure (timeout, bad JSON)
keeps the question local: the check fails closed. The prompt fits every course type (Z22d): a student of a
programming or engineering course mentions health mostly as the reason for late or missed work.
"""
import json

from app.llm.base import LLMClient, LLMError

PROMPT = """You check a student's message to a course tutor before it is sent to an external AI service.
The course can be about any subject (programming, engineering, biology, medicine, ...). Names, numbers and
contact details are already replaced by placeholders such as <PERSON_1>.
Answer true if the message reveals a health condition, injury, symptom, medicine, treatment, test result or
reading of the student or of a specific real person they mention (a relative, friend, classmate or a named
person), even in passing, for example as the reason for late or missed work. Answer false if it is a
general course question, a question about a hypothetical or textbook patient, or about health topics in
general, or if it mentions only non-health reasons (a broken laptop, a busy week, a family trip).
Reply with JSON {"personal_health": true} or {"personal_health": false}.

Message: """
SCHEMA = {"type": "object", "properties": {"personal_health": {"type": "boolean"}},
          "required": ["personal_health"]}


def parse(text: str) -> bool | None:
    try:
        value = json.loads(text).get("personal_health")
    except (ValueError, AttributeError):
        return None
    return value if isinstance(value, bool) else None


async def reveals_personal_health(llm: LLMClient, sanitized_text: str) -> bool:
    """True if the local model says the redacted text reveals personal health, or if the check failed."""
    try:
        result = await llm.complete([{"role": "user", "content": PROMPT + sanitized_text}],
                                    json_schema=SCHEMA, max_tokens=20)
    except LLMError:
        return True
    answer = parse(result.text)
    return True if answer is None else answer
