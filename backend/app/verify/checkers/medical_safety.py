"""Medical safety (design §2 principle 8, §7.1 step 8). Rule-based, so it is fast, predictable and testable.

fail: dosing instructions; advice to start, stop or change a medicine; diagnosing the student
      ("you have hypertension", "your reading shows you have high blood pressure").
warn: a personal health question answered without referring to a clinician.
"""
import re

from app.core.registry import checkers
from app.core.schemas import CheckResult, RequestContext
from app.privacy.recognizers.health_detail import TERMS

NAME = "medical_safety"
CONDITION = r"(?:" + "|".join(TERMS) + r")"
SENTENCE_RE = re.compile(r"[^.!?\n]+[.!?]?")

DOSE_AMOUNT_RE = re.compile(
    r"\b\d+(?:\.\d+)?\s?(?:mg|mcg|µg|micrograms?|milligrams?|ml|millilit(?:re|er)s?|units?|iu|puffs?|"
    r"tablets?|pills?|capsules?|drops?)\b", re.I)
DOSE_VERB_RE = re.compile(r"\b(?:take|taking|use|using|dose|dosage|inject|inhale|increase|decrease|reduce|"
                          r"double|start (?:on|with))\b", re.I)
MED_CHANGE_RE = re.compile(
    r"\b(?:you should|you can|you could|you may|you might want to|it is (?:safe|fine|ok|okay) to|"
    r"it's (?:safe|fine|ok|okay) to|go ahead and|feel free to|try to|just)\s+(?:(?!not\b|never\b)\w+\s+)?"
    r"(?:stop|start|quit|skip|reduce|lower|increase|double|halve|cut down|change|switch|come off)\b"
    r"[^.!?\n]{0,50}\b(?:medic\w*|pills?|tablets?|dos(?:e|es|age)|insulin|inhalers?|drugs?|prescriptions?|"
    r"treatment)\b", re.I)
SECOND_PERSON_DX_RE = re.compile(
    r"\byou(?:'ve| have| are| probably have| likely have| may have| might have| could have| seem to have|"
    r" definitely have| clearly have)\s+(?:got\s+)?"
    r"(?:a\s+|an\s+|early\s+|mild\s+|severe\s+|stage\s+\d\s+)?" + CONDITION + r"\b", re.I)
CONDITIONAL_RE = re.compile(
    r"\b(?:if|when|whether|in case|unless|people who|anyone who|someone who)\b[^.!?]*$", re.I)
READING_DX_RE = re.compile(
    r"\b(?:means|indicates?|shows?|confirms?|suggests?)\s+(?:that\s+)?(?:you\s+have\s+)?(?:stage\s+\d\s+)?"
    r"(?:high blood pressure|hypertension|(?:pre)?diabetes|asthma|pneumonia)\b", re.I)
OWN_READING_RE = re.compile(r"\b(?:your|this)\s+(?:\w+\s+)?(?:reading|result|numbers?|level|test)\b|"
                            r"\b\d{2,3}\s*(?:/|over)\s*\d{2,3}\b", re.I)
REFERRAL_RE = re.compile(r"\b(?:doctor|nurse|pharmacist|clinician|physician|gp|specialist|"
                         r"health ?care (?:provider|professional|team))s?\b", re.I)


def problems(answer: str) -> list[str]:
    """Reasons to fail an answer, as short labels (never quoting the answer)."""
    found: list[str] = []
    for sent in SENTENCE_RE.findall(answer):
        if DOSE_AMOUNT_RE.search(sent) and DOSE_VERB_RE.search(sent):
            found.append("dosing instruction")
        if MED_CHANGE_RE.search(sent):
            found.append("advice to start, stop or change a medicine")
        m = SECOND_PERSON_DX_RE.search(sent)
        if m and not CONDITIONAL_RE.search(sent[:m.start()]):
            found.append("diagnosis of the student")
        if READING_DX_RE.search(sent) and OWN_READING_RE.search(sent):
            found.append("diagnosis from a reading")
    return sorted(set(found))


def needs_referral(ctx: RequestContext) -> bool:
    personal = bool(ctx.pii and any(e.type == "HEALTH_DETAIL" for e in ctx.pii.entities))
    self_management = bool(ctx.understanding and ctx.understanding.question_type == "self_management")
    return personal or self_management


@checkers.register(NAME)
class MedicalSafetyChecker:
    name = NAME

    def __init__(self, services) -> None:
        self.services = services

    def check(self, ctx: RequestContext) -> CheckResult:
        answer = ctx.answer or ""
        found = problems(answer)
        if found:
            return CheckResult(name=NAME, status="fail", detail="; ".join(found))
        if needs_referral(ctx) and not REFERRAL_RE.search(answer):
            return CheckResult(name=NAME, status="warn", detail="personal health question without a referral")
        return CheckResult(name=NAME, status="pass")
