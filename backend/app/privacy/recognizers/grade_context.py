"""Grades the `grade` patterns miss (Beta, privacy filter upgrade).

- A score whose grade word is nearby rather than in the same clause: “Can we talk about my GPA? It's only a
  2.8”,
  “I'm doing okay, like a solid B” after “my grade”, “my average dropped to 3.1”. The grade word must be in
  the
  same or the previous sentence, within a short distance.
- Results of other people and other verbs: “his grade is 89%”, “she got a 3.8”, “I hit a 95% on the lab”.

A grade word nearby is required, so doses and readings (“2.5 mg”, “A1C over 8”, “150/95”) are not grades.
"""
import re

from presidio_analyzer import EntityRecognizer, RecognizerResult

from app.core.registry import pii_recognizers

GRADE_WORD_RE = re.compile(
    r"\b(?:c?gpa|grades?|marks?|scores?|average|midterms?|finals?|exams?|quiz(?:zes)?|tests?|assignments?|"
    r"essays?|labs?|papers?|transcript|courses?|class|semester|term)\b", re.I)
# a value: a letter grade (capital), a GPA (0.0-4.3), a percentage, or x/y
VALUE = (r"(?:(?-i:[ABCDF][+-]?)(?![\w+-])|"
         r"[0-4]\.\d{1,2}(?!\s?(?:mg|mcg|ml|mmol|units?|kg|lbs?|hours?|years?|"
         r"mmhg|%))\b|\d{1,3}(?:\.\d)?\s?(?:%|percent)|\d{1,3}\s?/\s?\d{1,3}(?!\s?(?:mmhg|bpm)))")
LEAD = (r"(?:\b(?:is|was|'s|’s|of|at|around|about|like|to|be|got|get|gets|hit|hits|scored|received|earned|"
        r"pulled|made|ended up with|sitting at|hovering around|down to|up to)\s+|:\s*|=\s*)"
        r"(?:(?:only|just|a|an|solid|weak|low|high|measly|decent|nearly|almost|barely|roughly)\s+){0,3}")
VALUE_RE = re.compile(LEAD + r"(" + VALUE + r")", re.I)
SUBJECT_VALUE_RE = re.compile(
    r"\b(?:I|(?i:he|she|they|we)|[A-Z][a-z]+)\s+(?:\w+\s+){0,2}?(?i:got|get|hit|scored|received|earned|pulled|"
    r"made|ended up with)\s+(?:(?:only|just|a|an)\s+){0,2}(" + VALUE + r")", re.U)
POSSESSIVE_GRADE_RE = re.compile(
    r"\b(?:(?i:his|her|their)|[A-Z][a-z]+(?:'s|’s))\s+(?:\w+\s+)?(?i:gpa|grade|mark|score|average|result)\b"
    r"[^.?!\n]{0,25}?(" + VALUE + r")", re.U)
# "It was 48 percent on the quiz", "got 70% in the final", "41 on the midterm", "bombed the midterm with a 41"
# a bare number needs a lead word: "question 12 on the quiz" is not a grade, "a 41 on the midterm" is
_WORK = (r"\s+(?:on|in|for)\s+(?:the|my|this|that|our|his|her)\s+(?:\w+\s+)?"
         r"(?i:midterm|final|exam|quiz|test|assignment|essay|lab|paper|project)\b")
ON_WORK_RE = re.compile(r"(?<![\w.])(" + VALUE + r")" + _WORK, re.U)
ON_WORK_BARE_RE = re.compile(r"\b(?i:a|an|was|is|got|scored|only|just)\s+(\d{1,3})" + _WORK, re.U)
WITH_RE = re.compile(r"(?i:bombed|aced|failed|passed|finished|did)\s+(?:the|my|this|that)\s+(?:\w+\s+)?"
                     r"(?i:midterm|final|exam|quiz|test|assignment|essay|lab|paper|project)\s+(?i:with)\s+"
                     r"(?:(?i:a|an|only|just)\s+)?(" + VALUE + r"|\d{1,3})\b", re.U)
# a value right after a possessive: "my 88/100 on the quiz", "improve my C-", "her 72%"
MY_VALUE_RE = re.compile(r"\b(?i:my|his|her|their)\s+(" + VALUE + r")", re.U)
# a grade label with its value: "Score of 88%", "grade: B+", "grade 78". A bare number counts only from 40 to
# 100 in a first-person message or next to a student number: "grade 3 hypertension" is a medical grading
# round 3: "asthma score is 45/F", "unit mark dropped to 58.0", "quiz is a solid C (72)", "grade is 78.5"
# (not "test": "my blood test was 7.5%" is a health reading)
SCORE_LETTER = r"\d{1,3}(?:\.\d)?\s?/\s?[A-F][+-]?(?![\w+-])"
LABEL_VALUE_RE = re.compile(r"\b(?i:score|grade|mark|result|quiz|exam|midterm|final)\s*"
                            r"(?i:of|is|was|=|:|dropped to|went (?:up|down) to|came (?:back|in) at|now)?\s*"
                            r"(?i:(?:a|an|only|just|solid|weak|low|high|now)\s+){0,2}"
                            r"(" + SCORE_LETTER + r"|" + VALUE + r"|\d{2,3}(?:\.\d+)?)(?!\d)",
                            re.U)
UNIT_AFTER_RE = re.compile(r"\s?(?:mg|mcg|ml|mmol|units?|kg|lbs?|mmhg|bpm|°|c\b|f\b|degrees|%)", re.I)
PERSONAL_RE = re.compile(r"\b(?:I|I'm|my|me)\b|\b\d{9}\b", re.I)
SENTENCE_RE = re.compile(r"(?:[^.?!\n]|\.(?=\d))+(?:[.?!]+|$)")  # "2.8" does not end a sentence
NEAR = 90  # characters from the grade word to the value
INHERITANCE_RE = re.compile(r"\b(?:alleles?|blood\s+types?|blood\s+groups?|genotypes?|phenotypes?|"
                            r"inherit\w*|grandparents?|chromosomes?|genes?|heterozygous|homozygous|"
                            r"dominant|recessive)\b", re.I)
OWN_GRADE_RE = re.compile(r"\b(?:(?i:my|his|her|their|our)|[A-Z][a-z]+(?:'s|’s))\s+(?:[\w-]+\s+){0,2}?"
                          r"(?i:" + GRADE_WORD_RE.pattern[5:-3] + r")\b", re.U)


@pii_recognizers.register("grade_context")
class GradeContextRecognizer(EntityRecognizer):
    SCORE = 0.7

    def __init__(self) -> None:
        super().__init__(supported_entities=["GRADE"], name="GradeContextRecognizer")

    def load(self) -> None:
        pass

    def analyze(self, text: str, entities: list[str], nlp_artifacts=None) -> list[RecognizerResult]:
        found: set[tuple[int, int]] = set()
        for rx in (SUBJECT_VALUE_RE, POSSESSIVE_GRADE_RE, ON_WORK_RE, ON_WORK_BARE_RE, WITH_RE):
            for m in rx.finditer(text):
                found.add((m.start(1), m.end(1)))
        for m in MY_VALUE_RE.finditer(text):
            found.add((m.start(1), m.end(1)))
        if PERSONAL_RE.search(text):
            for m in LABEL_VALUE_RE.finditer(text):
                v = m.group(1)
                bare = re.fullmatch(r"\d{2,3}(?:\.\d+)?", v)
                if bare and (not 40 <= float(v) <= 100 or UNIT_AFTER_RE.match(text, m.end(1))):
                    continue  # "12.5 mmol/L", "150 mg" are readings and doses, not grades
                found.add((m.start(1), m.end(1)))
        sentences = list(SENTENCE_RE.finditer(text))
        for i, sent in enumerate(sentences):
            prev = sentences[i - 1] if i else None
            ctx_start = prev.start() if prev else sent.start()
            context = text[ctx_start:sent.end()]
            # someone's own result: "my GPA", "his midterm", "Ana's final grade". Not a target or a quiz
            # answer:
            # "What GPA do I need? Is 3.0 enough?", "the quiz says the answer is B"
            words = [ctx_start + w.end() for w in OWN_GRADE_RE.finditer(context)]
            if not words:
                continue
            for m in VALUE_RE.finditer(text, sent.start(), sent.end()):
                if any(0 <= m.start(1) - w <= NEAR for w in words):
                    found.add((m.start(1), m.end(1)))
        return [RecognizerResult("GRADE", a, b, self.SCORE) for a, b in sorted(found)
                if not _blood_type(text, a, b)]


# the letter itself is a blood type or an allele: "blood type A", "type AB", "an A allele", "an A from the
# first grandparent"; a grade word right after it ("a B on the midterm") wins
BLOOD_BEFORE_RE = re.compile(r"(?:blood\s+(?:types?|groups?)|types?|groups?|alleles?|genotypes?)\s+"
                             r"(?:[ABO]{1,2}\s*(?:,|or|and)\s*)*$", re.I)
BLOOD_AFTER_RE = re.compile(r"\s*(?:alleles?|blood|antigens?|genotypes?)", re.I)
FROM_PARENT_RE = re.compile(r"\s+from\s+(?:\w+\s+){0,3}?(?:grand)?(?:parents?|mother|father|mom|dad)",
                            re.I)
GRADE_AFTER_RE = re.compile(r"(?:\W+\w+){0,4}?\W+(?:midterm|exam|quiz|test|final|course|assignment|grade|"
                            r"mark|score|paper|lab|project)s?", re.I)


def _blood_type(text: str, start: int, end: int) -> bool:
    """An A or B that is a blood type or an inherited allele, not a grade (found by scanning open course
    material): "the first parent received an A from the first grandparent". The letter itself must be part
    of the blood type or inheritance wording, in a sentence about inheritance; "I hit a B on the midterm
    about dominant alleles" stays a grade."""
    if text[start:end] not in ("A", "B"):
        return False
    sentence = next((s for s in SENTENCE_RE.finditer(text) if s.start() <= start < s.end()), None)
    if not (sentence and INHERITANCE_RE.search(sentence.group())):
        return False
    if GRADE_AFTER_RE.match(text, end):
        return False
    before = text[max(sentence.start(), start - 40):start]
    return bool(BLOOD_BEFORE_RE.search(before) or BLOOD_AFTER_RE.match(text, end)
                or FROM_PARENT_RE.match(text, end))
