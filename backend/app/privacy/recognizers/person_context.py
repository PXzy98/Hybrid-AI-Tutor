"""Names the NER model misses in short informal messages (Beta, privacy filter upgrade).

- A single first name after a relation: “my cousin, Sofia”, “my friend Mateo”, “our neighbour Mrs Gupta”.
- A name introduced as someone: “a student like Aiya”, “a guy named Tom”, “my name is kenji sato”.
- A sign-off at the end: “… thanks! - Ayesha S.”, “Cheers, Omar”.
- A name opening the message: “Javier Santos here.”, “Priya here, quick question”.

Only capitalised words that are not common English words, months, days or course terms count (except after
“my name is”, where any word does).
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers
from app.privacy.recognizers.health_context import RELATION

NAME = r"((?:(?:Mr|Mrs|Ms|Miss|Dr)\.?\s+)?[A-Z][\w'’-]+(?:\s+[A-Z][\w'’-]*\.?)?)"
REL_NAME_RE = re.compile(r"\b(?i:my|our|his|her|their)\s+(?i:" + RELATION + r")\s*,?\s+" + NAME, re.U)
INTRO_RE = re.compile(r"\b(?i:student|person|someone|guy|girl|kid|patient|classmate|friend)\s+"
                      r"(?i:named|called|like)\s+" + NAME, re.U)
# not "I'm X": "I'm Canadian", "I'm Worried" would look like names; the NER model handles "I'm Diego Sanchez"
MY_NAME_RE = re.compile(r"\b(?i:my name is|my name's|name's|call me|this is)\s+"
                        r"([A-Za-z][\w'’-]+(?:\s+[A-Za-z][\w'’-]+)?)", re.U)
SIGNOFF_RE = re.compile(r"(?:^|[.!?)]\s*|\n\s*|\s)(?:[-–—~]+\s*|(?i:thanks|thank you|thx|cheers|best|regards|"
                        r"sincerely|cordially)\s*[,!.]?\s*[-–—]?\s*)" + NAME + r"\s*[.!]?\s*$", re.U)
HERE_RE = re.compile(r"^\s*" + NAME + r"\s+here\b", re.U)
# a name addressed at the start: "Zara, I'm totally lost", "Hey Marcus, my migraine ..." (staff on the
# allow-list
# stay). Not before a colon: "Group: Tom Becker", "Note: ..." are labels
VOCATIVE_RE = re.compile(r"^\s*(?:(?i:hi|hey|hello|dear|yo)\s+)?" + NAME + r"\s*[,!]", re.U)
# "Dev's grandma", "Omar's mom": a capitalised word owning a relative is a person
NAME_REL_RE = re.compile(r"\b([A-Z][a-z]+)(?:'s|’s)\s+(?i:" + RELATION + r")\b", re.U)

COMMON = set("""a an the i im ive id me my we our you your he she it they them his her their this that
these those
and or but so if then because as at by for from in into of on to up with without about after before during
hi hey hello dear thanks thank cheers best regards ok okay yes no please sorry quick question also just
what when where which who why how is are was were be been am do does did can could will would should may might
must have has had not any some all every each other another one two three first last next new old good bad
monday tuesday wednesday thursday friday saturday sunday january february march april may june july august
september october november december today tomorrow yesterday week weekend morning evening night
professor prof dr doctor nurse ta instructor teacher class course exam quiz midterm final lab assignment
asthma diabetes migraine migraines pneumonia hypertension blood pressure covid flu canada ontario ottawa
english french type tutor sir madam team everyone guys folks quick urgent help question
ugh um uh oh hmm wow lol omg btw fyi so well wait oops yikes""".split())
NOT_NAME_NEXT = re.compile(r"\s+(?:is|are|was|were|has|have|had|and|or|says|said|told|asked|thinks|"
                           r"needs|wants|got|gets)\b", re.I)


def _is_name(value: str, strict: bool = True) -> bool:
    words = [w.strip(".'’") for w in value.split()]
    if not words or not words[0]:
        return False
    if strict and not words[0][0].isupper():
        return False
    return all(w.lower() not in COMMON for w in words if w)


@pii_recognizers.register("person_context")
class PersonContextRecognizer(EntityRecognizer):
    SCORE = 0.7

    def __init__(self) -> None:
        super().__init__(supported_entities=["PERSON"], name="PersonContextRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        found: set[tuple[int, int]] = set()
        for rx in (REL_NAME_RE, INTRO_RE, SIGNOFF_RE, HERE_RE, NAME_REL_RE, VOCATIVE_RE):
            for m in rx.finditer(text):
                value = m.group(1)
                # "my friend Mateo has ..." keeps only the name; a second word that is a verb is not a surname
                two = value.split()
                if len(two) == 2 and (two[1].lower() in COMMON or NOT_NAME_NEXT.match(" " + two[1])):
                    value = two[0]
                if _is_name(value):
                    found.add((m.start(1), m.start(1) + len(value)))
        for m in MY_NAME_RE.finditer(text):
            value = m.group(1)
            two = value.split()
            if two and two[0].lower() in COMMON:
                continue  # "I'm a student", "this is the question"
            if len(two) == 2 and two[1].lower() in COMMON:
                value = two[0]
            # after "my name is" lower-case names count; after "I'm" only capitalised ones ("I'm tired")
            strict = not re.match(r"(?i)my name|name's|call me", m.group(0).strip())
            if _is_name(value, strict=strict):
                found.add((m.start(1), m.start(1) + len(value)))
        return [RecognizerResult("PERSON", a, b, self.SCORE) for a, b in sorted(found)]
