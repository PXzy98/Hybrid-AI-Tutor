"""Cold start (design §5.5): consent, 2 preference questions, a short diagnostic. Every part is optional."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import ServicesDep
from app.auth.deps import Student
from app.core.schemas import CheckItemPublic, Detail, Sequencing
from app.learner.checks import diagnostic_items
from app.learner.preference import PreferenceSignal

router = APIRouter(prefix="/onboarding", tags=["learner"])

CONSENT_TEXT = (
    "To adapt explanations to you, the tutor keeps a learning profile: an estimate of how well you know each "
    "topic part, which common misunderstandings you may have, and how you like explanations presented "
    "(examples first or ideas first, short or detailed). It does not keep your questions in readable form "
    "with your name. The profile is stored only on the course's own servers and is never sent to external "
    "AI services; they may only receive a coarse level such as 'basic'. You can view or reset your profile "
    "at any time under 'What I know', and the instructor can delete your account and its data. Without "
    "consent the tutor still answers, but does not adapt to you."
)


class Choice(BaseModel):
    value: str
    label: str


class PreferenceQuestion(BaseModel):
    id: Literal["sequencing", "detail"]
    question: str
    options: list[Choice]


PREFERENCE_QUESTIONS = [
    PreferenceQuestion(id="sequencing",
                       question="When you learn something new, what helps you most at first?",
                       options=[Choice(value="example_first", label="A concrete example first"),
                                Choice(value="concept_first", label="The general idea first")]),
    PreferenceQuestion(id="detail", question="How long should explanations usually be?",
                       options=[Choice(value="concise", label="Short and to the point"),
                                Choice(value="detailed", label="Detailed, step by step")]),
]


class OnboardingInfo(BaseModel):
    topic: str
    consent_text: str
    consent_given: bool | None  # None: never asked
    preference_questions: list[PreferenceQuestion]
    diagnostic: list[CheckItemPublic]


class PreferenceAnswers(BaseModel):
    sequencing: Sequencing | None = None
    detail: Detail | None = None


class DiagnosticAnswer(BaseModel):
    item_id: str
    choice: Literal["A", "B", "C", "D"]


class OnboardingBody(BaseModel):
    topic: str
    consent: bool | None = None  # None: leave as it is
    preferences: PreferenceAnswers = PreferenceAnswers()
    answers: list[DiagnosticAnswer] = Field(default_factory=list, max_length=20)


class KcBand(BaseModel):
    kc_id: str
    name: str
    band: str  # basic | intermediate | advanced | mastered


class OnboardingResult(BaseModel):
    personalized: bool
    assessed: dict[str, bool] = {}  # kc_id -> answered correctly
    skipped: list[str] = []  # not assessed because a prerequisite was missed
    kcs: list[KcBand] = []


def _check_topic(services, topic: str) -> None:
    if topic not in services.settings.topics():
        raise HTTPException(422, "unknown topic")


@router.get("", response_model=OnboardingInfo)
def get_onboarding(topic: str, user: Student, services: ServicesDep):
    _check_topic(services, topic)
    return OnboardingInfo(topic=topic, consent_text=CONSENT_TEXT,
                          consent_given=services.learner.repo.consent(user.student_id),
                          preference_questions=PREFERENCE_QUESTIONS,
                          diagnostic=[i.public() for i in diagnostic_items(services.content, topic)])


@router.post("", response_model=OnboardingResult)
def post_onboarding(body: OnboardingBody, user: Student, services: ServicesDep):
    _check_topic(services, body.topic)
    learner, sid = services.learner, user.student_id
    if body.consent is not None:
        learner.set_consent(sid, body.consent)
    if not learner.has_consent(sid):
        return OnboardingResult(personalized=False)  # nothing else is stored without consent
    for dim in ("sequencing", "detail"):
        value = getattr(body.preferences, dim)
        if value:
            learner.update_preferences(sid, PreferenceSignal(dimension=dim, value=value, explicit=True,
                                                             source="onboarding"))
    try:
        assessed, skipped = learner.apply_diagnostic(sid, body.topic,
                                                     [(a.item_id, a.choice) for a in body.answers])
    except ValueError as e:
        raise HTTPException(422, str(e)) from None
    ctx = learner.context(sid, body.topic)
    kcs = [KcBand(kc_id=k.id, name=k.name, band=learner.band(ctx.kc_states[k.id]))
           for k in services.content.kcs(body.topic)]
    return OnboardingResult(personalized=True, assessed=assessed, skipped=skipped, kcs=kcs)
