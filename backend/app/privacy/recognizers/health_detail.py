"""Personal health details: the student's (or a relative's) own conditions, medicines, symptoms, readings.

General questions must NOT match: "What is asthma?", "Can you help me understand diabetes?",
"I have a question about migraines". A condition term counts only when it is attributed to the student or
a family member ("I have asthma", "my father was diagnosed with lung cancer", "I've been having panic
attacks"), when it is something the student owns ("my inhaler", "my therapist"), or when a first-person
sentence contains a reading ("my reading was 150 over 95").
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

FAMILY = (r"(?:mother|father|mom|mum|dad|parents?|brother|sister|son|daughter|child|children|kids?|wife|"
          r"husband|partner|boyfriend|girlfriend|grand(?:mother|father|ma|pa|parents?)|aunt|uncle|cousin|"
          r"roommate|friend)")
TERMS = [
    # conditions
    r"asthma(?:tic)?", r"(?:pre)?diabet(?:es|ic)", r"type\s?[12]\s+diabetes", r"hypertensi(?:on|ve)",
    r"high blood pressure", r"low blood pressure", r"migraines?", r"pneumonia", r"(?:\w+\s)?cancer",
    r"tumou?rs?", r"strokes?", r"heart attacks?", r"heart (?:disease|failure|condition)", r"kidney disease",
    r"copd", r"epilep(?:sy|tic)", r"seizures?", r"depress(?:ion|ed)", r"anxiety", r"panic attacks?", r"adhd",
    r"autism", r"ptsd", r"eating disorder", r"covid(?:-19)?", r"the flu", r"infections?", r"appendicitis",
    r"pregnan(?:t|cy)", r"hiv", r"hepatitis", r"arthritis", r"allerg(?:y|ies|ic)", r"surgery",
    r"hospital(?:i[sz]ed)?",
    # symptoms
    r"chest pains?", r"shortness of breath", r"trouble breathing", r"wheez(?:e|ing)", r"dizz(?:y|iness)",
    r"fevers?", r"headaches?", r"nausea", r"(?:high|low) blood sugar",
    # found by the E6 held-out set
    r"(?:high|low) bp", r"cough(?:s|ing)?(?: fits)?", r"chest tightness", r"flare[- ]?ups?", r"fatigue",
    # medicines
    r"metformin", r"insulin", r"lisinopril", r"amlodipine", r"salbutamol", r"albuterol", r"ventolin",
    r"(?:\w+\s)?inhalers?", r"sumatriptan", r"triptans?", r"ibuprofen", r"acetaminophen", r"tylenol",
    r"advil",
    r"statins?", r"antibiotics?", r"antidepressants?", r"steroids?",
    r"fluticasone", r"budesonide", r"prednisone", r"montelukast", r"ceftriaxone", r"amoxicillin",
    r"azithromycin", r"losartan", r"hydrochlorothiazide", r"glipizide", r"semaglutide", r"ozempic",
    r"(?:bp|blood pressure|breathing|heart|sugar) (?:issues|problems)", r"exacerbations?", r"chronic pain",
    r"short(?:ness)? (?:of )?breath(?: episodes)?",
    r"(?:blood pressure|bp)\s+(?:pills|meds|medication|medicine)",
]
TERM_RE = re.compile(r"\b(?:" + "|".join(TERMS) + r")\b", re.I)

# subject + attribution verb: "I have", "I'm", "I've been having", "my dad takes", "my father was diagnosed"
ATTRIBUTION_RE = re.compile(
    r"\b(?:I|she|he|my\s+" + FAMILY + r")\b[^.?!\n]{0,25}?"  # she/he: the person the student just named
    r"(?:'m|'ve been|'d|'s|’s|\b(?:am|is|are|was|were|been|have|has|had|got|get|gets|having|take|takes|"
    r"taking|took|use|uses|using|diagnosed|suffer|suffers|suffering|live|lives|living|went|go|goes|feel|feels|feeling|"
    r"experience[ds]?|experiencing|struggl(?:e|es|ed|ing)|deal|deals|dealing|keep|keeps)\b)",
    re.I,
)
# words that turn "I have ... asthma" into a study question rather than a health detail
BLOCKERS_RE = re.compile(
    r"\b(?:about|question|questions|regarding|learn|learning|understand|explain|study|studying|studied|read|"
    r"reading|notes|lecture|lectures|course|class|exam|quiz|assignment|homework|lab|project|presentation|"
    r"essay|report|topic|chapter|slides|practice|research|definition|mean|means|section|module|unit|"
    r"material|materials)\b",
    re.I,
)
# a term that names coursework: "I'm struggling with the asthma section", "my diabetes assignment"
COURSE_AFTER_RE = re.compile(
    r"\s+(?:assignment|project|quiz|exam|test\b|module|unit|section|chapter|lecture|notes|essay|report|grade|"
    r"score|mark|class|course|presentation|homework|lab\b|case stud)", re.I)
WINDOW = 70  # characters after the verb in which a term still counts

OWNED_RE = re.compile(
    r"\bmy\s+(?:\w+\s+)?(?:therapist|psychiatrist|psychologist|counsell?or|medication|medications|medicine|"
    r"meds|pills|inhaler|insulin|prescription|dose|dosage|diagnosis|symptoms|test results|blood test|"
    r"blood sugar|surgery|condition)\b",
    re.I,
)
FIRST_PERSON_RE = re.compile(r"\b(?:I|I'm|I've|me|my|mine)\b", re.I)
READING_RE = re.compile(r"\b\d{2,3}\s*(?:/|over)\s*\d{2,3}\b", re.I)
# "My mark on quiz 2 was 13/20" is a grade, not a reading (found by E6); the grade recognizer handles it
COURSEWORK_RE = re.compile(r"\b(?:mark|marks|grade|graded|score|scored|quiz|exam|midterm|final|assignment|"
                           r"essay|homework|project|GPA)\b", re.I)
SENTENCE_RE = re.compile(r"[^.?!\n]+")

# Misspelled conditions and medicines ("asthama", "diabetis", "metfromin"; found by E6). Only words of at least
# five letters with the same first letter, at most one edit (two from nine letters on), and only where an exact
# term would count: in an attributed window or after a possessive.
FUZZY_TERMS = [
    "asthma", "diabetes", "diabetic", "hypertension", "migraine", "migraines", "pneumonia", "epilepsy",
    "epileptic", "seizures", "depression", "depressed", "anxiety", "arthritis", "hepatitis", "appendicitis",
    "allergy", "allergies", "allergic", "cancer", "tumour", "tumor", "insulin", "metformin", "lisinopril",
    "amlodipine", "salbutamol", "albuterol", "ventolin", "sumatriptan", "ibuprofen", "acetaminophen", "tylenol",
    "prednisone", "montelukast", "amoxicillin", "azithromycin", "losartan", "ozempic", "semaglutide",
    "fluticasone", "budesonide", "inhaler", "inhalers", "antibiotics", "antidepressants", "headaches",
    "dizziness", "nausea", "wheezing", "pregnant", "pregnancy", "surgery", "infection",
]
WORD_RE = re.compile(r"\b[a-z]{5,}\b", re.I)
POSSESSIVE_FUZZY_RE = re.compile(
    r"\b(?:my|his|her|their|my\s+" + FAMILY + r"(?:'s|’s))\s+"
    r"(?:(?:chronic|long-term|recent|severe|bad|new|latest|current|own)\s+)?([a-z]{5,})\b", re.I)


def _edits(a: str, b: str, limit: int) -> int:
    """Levenshtein distance, stopping early once it exceeds `limit`."""
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    prev = list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i]
        for j, cb in enumerate(b, 1):
            cur.append(min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb)))
        if min(cur) > limit:
            return limit + 1
        prev = cur
    return prev[-1]


def fuzzy_term(word: str) -> bool:
    """True for a misspelling of a condition or medicine (not for the exact term, which TERM_RE handles)."""
    w = word.lower()
    for term in FUZZY_TERMS:
        if w == term or w[0] != term[0]:
            continue
        if _edits(w, term, 2 if len(term) >= 9 else 1) <= (2 if len(term) >= 9 else 1):
            return True
    return False


@pii_recognizers.register("health_detail")
class HealthDetailRecognizer(EntityRecognizer):
    SCORE = 0.85

    def __init__(self) -> None:
        super().__init__(supported_entities=["HEALTH_DETAIL"], name="HealthDetailRecognizer")

    def load(self) -> None:  # nothing to load
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        spans: set[tuple[int, int]] = set()
        for sent in SENTENCE_RE.finditer(text):
            s, base = sent.group(), sent.start()
            for m in ATTRIBUTION_RE.finditer(s):
                window_end = min(len(s), m.end() + WINDOW)
                for t in TERM_RE.finditer(s, m.end(), window_end):
                    if BLOCKERS_RE.search(s, m.end(), t.start()) or COURSE_AFTER_RE.match(s, t.end()):
                        continue
                    spans.add((base + t.start(), base + t.end()))
                for w in WORD_RE.finditer(s, m.end(), window_end):
                    if (fuzzy_term(w.group()) and not BLOCKERS_RE.search(s, m.end(), w.start())
                            and not COURSE_AFTER_RE.match(s, w.end())):
                        spans.add((base + w.start(), base + w.end()))
            for m in POSSESSIVE_FUZZY_RE.finditer(s):
                if fuzzy_term(m.group(1)) and not COURSE_AFTER_RE.match(s, m.end(1)):
                    spans.add((base + m.start(1), base + m.end(1)))
            for m in OWNED_RE.finditer(s):
                spans.add((base + m.start(), base + m.end()))
            if FIRST_PERSON_RE.search(s) and not COURSEWORK_RE.search(s):
                for m in READING_RE.finditer(s):
                    spans.add((base + m.start(), base + m.end()))
        return [RecognizerResult("HEALTH_DETAIL", a, b, self.SCORE) for a, b in sorted(spans)]
