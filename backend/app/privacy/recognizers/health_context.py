"""Personal health details that the attribution rules of `health_detail` miss (Beta, privacy filter upgrade).

Three general shapes, each still requiring that the term is attributed to a real person:

- Someone else, named or described: “Mrs. Gupta has diabetes”, “Kenji's dad had pneumonia”, “my neighbour
  keeps getting migraines”, “Liam's breathing is bad”. The subject is a name found by the NER model, a titled
  name (Mr./Mrs./Ms./Dr. X), or a relation (my classmate, our neighbour, her coworker).
- The student's own condition without “I have / my”: “because of this crazy migraine”, “it might be a major
  migraine” in a first-person sentence. Needs a demonstrative or a severity word right before the term, so
  “what is a migraine?” or “I read about migraines” do not match.
- A term with the student as the object: “the headache is killing me”, “asthma is messing with my sleep”.

Coursework phrases are excluded as in `health_detail` (“the asthma section”, a study verb before the term).
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers
from app.privacy.analyzer import _EPONYM_NOUNS, _NEXT_WORD
from app.privacy.recognizers.health_detail import BLOCKERS_RE, COURSE_AFTER_RE, FAMILY, SENTENCE_RE, TERM_RE

RELATION = (r"(?:" + FAMILY[3:-1] + r"|classmates?|neighbou?rs?|colleagues?|co-?workers?|teammates?|"
            r"lab partner|tutor|coach|boss|landlord|housemates?|flatmates?)")
VITALS = (r"(?:blood pressure|bp|blood sugars?|sugar levels?|glucose(?: levels?)?|breathing|lungs|heart|"
          r"readings)")
# "'s" is left out: after a name it is far more often a possessive ("Cushing's syndrome"), handled by POSS_RE
VERBS = (r"(?:\b(?:is|are|was|were|has|have|had|got|gets|keeps?|kept|takes?|took|taking|uses?|using|"
         r"suffers?|suffered|suffering|deals?|dealt|dealing|struggles?|struggled|struggling|lives|living|went|"
         r"was diagnosed|has been diagnosed|got diagnosed|needs?|needed|started|ended up|landed|"
         r"(?:has|have|had) been(?: having| dealing| struggling| getting| taking)?|"
         r"(?:is|was) (?:having|getting|taking|on|in hospital|hospitali[sz]ed|recovering))\b)")
TITLED_RE = re.compile(r"\b(?:Mr|Mrs|Ms|Miss|Mx|Dr)\.?\s+[A-Z][\w'-]+", re.U)
NAME_REL_RE = re.compile(r"\b([A-Z][a-z]+)(?='s\s|’s\s)(?=(?:'s|’s)\s+(?i:" + FAMILY[3:-1] + r")\b)", re.U)
REL_RE = re.compile(r"\b(?:my|our|his|her|their|a|one of my)\s+" + RELATION + r"\b", re.I)
WINDOW = 60
# "Omar's mom just has", "Elara keeps having", "my neighbour, Kai, has", "Jae-Hoon G. (300987654) is
# struggling"
VERB_RE = re.compile(r"(?:,?\s+[^\s,.?!]+){0,3}?,?\s*" + VERBS, re.I)
# the student's guess about their own condition: "I think this might be pneumonia", "it could be a migraine"
GUESS_RE = re.compile(r"\b(?:it|this|that)\s*(?:'s|’s|\s+is|\s+was|\s+might be|\s+could be|\s+may be|"
                      r"\s+must be|\s+seems? (?:like|to be)|\s+feels? like|\s+sounds? like)\s+"
                      r"(?:a\s+|an\s+)?(?:[\w-]+\s+)?$",
                      re.I)
# a condition's current state: "Asthma symptoms are back", "my migraines are acting up again", "it flared up"
STATE_RE = re.compile(r"\s+(?:\w+\s+)?(?:is|are|has been|have been|keeps?|was|were)?\s*(?:back|acting up|"
                      r"flaring up|flared up|getting worse|worse than usual|worse again|bad again|"
                      r"out of control|through the roof|all over the place|spiking|shooting up|not improving|"
                      r"not going away)\b",
                      re.I)
REL_AFTER_RE = re.compile(r"(?:'s|’s)\s+" + FAMILY + r"\b", re.I)
POSS_RE = re.compile(r"(?:'s|’s)\s+(?:" + FAMILY + r"(?:'s|’s)\s+)?(?:(?:chronic|long-term|recent|severe|bad|"
                     r"new|latest|current)\s+)?(" + VITALS + r"|" + TERM_RE.pattern[5:-3] + r")\b", re.I)

SEVERITY = (r"(?:this|these|that|those|another|such an?|the worst|a (?:really |very |super )?"
            r"(?:bad|terrible|awful|horrible|severe|crazy|intense|major|nasty|killer|massive|huge|brutal|"
            r"constant|chronic|persistent|recurring|sudden)|(?:really |very |super )?"
            r"(?:bad|terrible|awful|horrible|severe|crazy|intense|nasty|killer|massive|brutal|constant|"
            r"persistent|recurring)|worst)")
SEVERITY_BEFORE_RE = re.compile(r"\b" + SEVERITY + r"(?:\s+[\w-]+){0,1}\s*$", re.I)
FIRST_PERSON_RE = re.compile(r"\b(?:I|I'm|I’m|I've|I’ve|I'd|me|my|mine|myself)\b")
WH_GENERAL_RE = re.compile(r"^\s*(?:what|how|why|when|which|who|is|are|does|do|can|should|could)\b"
                           r"[^?]*\?\s*$",
                           re.I)
OBJECT_RE = re.compile(
    r"\s+(?:is|are|has been|have been|keeps?|been|was|were)\s+(?:\w+\s+){0,2}?"
    r"(?:killing|kicking|wrecking|ruining|messing(?: up| with)?|affecting|hurting|destroying|bothering|"
    r"getting to|keeping)\s+(?:me|my)\b", re.I)


def _subjects(text: str, nlp_artifacts) -> list[tuple[int, int]]:
    """Spans that name or describe a real person other than the student."""
    spans = [(m.start(), m.end()) for m in TITLED_RE.finditer(text)]
    spans += [(m.start(), m.end()) for m in REL_RE.finditer(text)]
    # "Dev's grandma" (the NER model may miss Dev)
    spans += [(m.start(1), m.end(1)) for m in NAME_REL_RE.finditer(text)]
    for ent in getattr(nlp_artifacts, "entities", None) or []:
        if ent.label_ == "PERSON":
            nxt = _NEXT_WORD.match(text, ent.end_char)  # "Cushing's syndrome" is an eponym, not a person
            if not (nxt and nxt.group(1).lower() in _EPONYM_NOUNS):
                spans.append((ent.start_char, ent.end_char))
    return spans


def _term_ok(text: str, start: int, t) -> bool:
    return not BLOCKERS_RE.search(text, start, t.start()) and not COURSE_AFTER_RE.match(text, t.end())


@pii_recognizers.register("health_context")
class HealthContextRecognizer(EntityRecognizer):
    SCORE = 0.75

    def __init__(self) -> None:
        super().__init__(supported_entities=["HEALTH_DETAIL"], name="HealthContextRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        found: set[tuple[int, int]] = set()
        for a, b in _subjects(text, nlp_artifacts):
            sent_end = next((m.end() for m in SENTENCE_RE.finditer(text) if m.start() <= a < m.end()),
                            len(text))
            # "Liam's breathing", "Mrs. Patel's blood pressure", "his mom's asthma"
            p = POSS_RE.match(text, b)
            if p and not COURSE_AFTER_RE.match(text, p.end(1)):
                found.add((p.start(1), p.end(1)))
            # the subject itself, or its relative: "Kenji's dad had to get checked for pneumonia"
            rel = REL_AFTER_RE.match(text, b)
            for start in (b, rel.end() if rel else None):
                v = VERB_RE.match(text, start) if start is not None else None
                if not v:
                    continue
                for t in TERM_RE.finditer(text, v.end(), min(sent_end, v.end() + WINDOW)):
                    if _term_ok(text, v.end(), t):
                        found.add((t.start(), t.end()))
        for sent in SENTENCE_RE.finditer(text):
            s, base = sent.group(), sent.start()
            for t in TERM_RE.finditer(s):
                before = s[max(0, t.start() - 40):t.start()]
                if COURSE_AFTER_RE.match(s, t.end()) or BLOCKERS_RE.search(before):
                    continue
                # severity words need a first-person sentence ("I have a question. A severe asthma attack,
                # what happens?" is general); a guess or a state may follow in the next sentence
                first_person = FIRST_PERSON_RE.search(text) and not WH_GENERAL_RE.match(s)
                if FIRST_PERSON_RE.search(s) and first_person and SEVERITY_BEFORE_RE.search(before):
                    found.add((base + t.start(), base + t.end()))
                elif first_person and GUESS_RE.search(before):
                    found.add((base + t.start(), base + t.end()))
                elif OBJECT_RE.match(s, t.end()) or (first_person and STATE_RE.match(s, t.end())):
                    found.add((base + t.start(), base + t.end()))
        return [RecognizerResult("HEALTH_DETAIL", a, b, self.SCORE) for a, b in sorted(found)]
