"""Question understanding (design §5.1 weak evidence, §7.1 step "understand").

The local model tags a question with KC IDs, a question type, a confusion flag and catalogued misconception
IDs. The output is constrained by a JSON schema whose enums are the topic's own IDs, so the model can only
pick from the catalog; anything else is rejected. Only IDs and flags leave this module, never text.

The wire format uses one-letter keys (k, t, c, m): the reply is generated token by token, so short keys
roughly halve the latency of this step (E1, eval/understand-tagging).
"""
import json
import re

from app.core.schemas import Understanding
from app.core.topics import topic_name
from app.learner.content import ContentStore
from app.llm.base import Message

QUESTION_TYPES = ["definition", "how_why", "self_management", "check_my_answer", "other"]
MAX_KCS = 2

INSTRUCTIONS = """You classify a student's question for a health-education tutor. Reply with JSON only:
{"k": [...], "t": "...", "c": true|false, "m": [...]}

- k: the 0-2 knowledge components the question is mainly about, most relevant first; [] when the question
  is not about this topic.
- t: question type. "definition" (what is / what does X mean), "how_why" (how or why something works),
  "self_management" (about the student's own or a relative's health, readings or medicines),
  "check_my_answer" (the student states a belief and asks whether it is right), "other".
- c: true only if the student says they are confused, lost or do not understand.
- m: catalogued misconceptions the student STATES or ASSUMES as true. Asking whether something is true is
  not believing it: "Does X always happen?" -> []. Use [] when none applies."""

FEW_SHOT: list[tuple[str, dict]] = [
    ("I'm lost: what does blood pressure actually measure?",
     {"k": ["HBP.1"], "t": "definition", "c": True, "m": []}),
    ("Since I feel healthy, my blood pressure is surely normal, isn't it?",
     {"k": ["HBP.1"], "t": "check_my_answer", "c": False, "m": ["HBP.MC3"]}),
    ("Does only the top number of a reading matter?",
     {"k": ["HBP.1"], "t": "how_why", "c": False, "m": []}),
    ("What's a good recipe for pancakes?",
     {"k": [], "t": "other", "c": False, "m": []}),
]

# A belief is stated in a declarative sentence ("I only take my pills when…, right?"), not in a plain
# question ("Does X always…?", "Why…?"). Model output for m is kept only for statements (E1: precision).
PLAIN_QUESTION_RE = re.compile(
    r"^\s*(?:does|do|did|is|are|was|were|can|could|should|would|will|has|have|what|why|how|when|which|who|"
    r"where)\b", re.I)
ASSERTION_RE = re.compile(r"\b(?:right|correct|isn'?t it|aren'?t they|true)\s*\?|"
                          r"\bI (?:think|thought|believe)\b|\bso (?:I|my|it|that)\b", re.I)


def states_belief(question: str) -> bool:
    return bool(ASSERTION_RE.search(question)) or not PLAIN_QUESTION_RE.search(question)


def schema(content: ContentStore, topic: str) -> dict:
    """JSON schema for Ollama's `format`: the enums are the topic's KC and misconception IDs."""
    kc_ids = [k.id for k in content.kcs(topic)]
    mc_ids = [m.id for k in kc_ids for m in content.misconceptions(k)]
    mc_items = {"type": "string", "enum": mc_ids} if mc_ids else {"type": "string"}
    return {
        "type": "object",
        "properties": {
            "k": {"type": "array", "items": {"type": "string", "enum": kc_ids}, "maxItems": MAX_KCS},
            "t": {"type": "string", "enum": QUESTION_TYPES},
            "c": {"type": "boolean"},
            "m": {"type": "array", "items": mc_items, "maxItems": 3 if mc_ids else 0},
        },
        "required": ["k", "t", "c", "m"],
    }


def messages(content: ContentStore, topic: str, question: str) -> list[Message]:
    kcs = "\n".join(f"- {k.id}: {k.name}. {k.definition}".strip() for k in content.kcs(topic))
    mcs = "\n".join(f"- {m.id}: {m.statement}"
                    for k in content.kcs(topic) for m in content.misconceptions(k.id))
    system = (f"{INSTRUCTIONS}\n\nTopic: {topic_name(topic)}\n\nKnowledge components:\n{kcs}\n\n"
              f"Catalogued misconceptions:\n{mcs or '- (none)'}")
    out: list[Message] = [{"role": "system", "content": system}]
    if topic == "high_blood_pressure":  # the examples use HBP IDs; other topics rely on the instructions
        for q, a in FEW_SHOT:
            out += [{"role": "user", "content": q}, {"role": "assistant", "content": json.dumps(a)}]
    out.append({"role": "user", "content": question})
    return out


def parse(text: str, content: ContentStore, topic: str, question: str = "") -> Understanding:
    """Validate the model's JSON. Unknown IDs or a malformed reply raise ValueError (the step is skipped)."""
    try:
        data = json.loads(text)
    except json.JSONDecodeError as e:
        raise ValueError("understand: reply is not JSON") from e
    kc_known = {k.id for k in content.kcs(topic)}
    mc_known = {m.id for k in kc_known for m in content.misconceptions(k)}
    kc_ids = list(dict.fromkeys(data.get("k") or []))[:MAX_KCS]
    mc_ids = list(dict.fromkeys(data.get("m") or []))
    if not set(kc_ids) <= kc_known or not set(mc_ids) <= mc_known:
        raise ValueError("understand: unknown KC or misconception ID")
    qtype = data.get("t", "other")
    qtype = qtype if qtype in QUESTION_TYPES else "other"
    if qtype not in ("check_my_answer", "self_management") or not states_belief(question):
        mc_ids = []  # a misconception needs a stated belief, not a question about it
    return Understanding(kc_ids=kc_ids, question_type=qtype, confusion=bool(data.get("c", False)),
                         misconception_ids=mc_ids)
