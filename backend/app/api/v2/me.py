"""The student's global learning preferences and consent (api-v2.md 3.1; course-structure.md 4; task Z9).

Both are global (one per student, not per course) and go through the learner model's own interface: without
consent nothing is stored, and withdrawing consent forgets the learning profile.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field

from app.auth.deps import Student
from app.core.schemas import Preferences
from app.learner.preference.interface import PreferenceSignal

router = APIRouter(prefix="/me", tags=["me"])


class PreferencesIn(BaseModel):
    sequencing: Literal["example_first", "concept_first"] | None = None
    detail: Literal["concise", "detailed"] | None = None


class InstructionIO(BaseModel):
    # V15: how answers should be presented, in the student's words; "" removes it
    text: str = Field("", max_length=300)


class ConsentOut(BaseModel):
    given: bool | None  # None: never asked


class ConsentIn(BaseModel):
    given: bool


def _learner(request: Request):
    return request.app.state.services.learner


@router.get("/preferences", response_model=Preferences, operation_id="me_preferences_get")
def get_preferences(request: Request, user: Student):
    return _learner(request).preferences.get(user.student_id)


@router.put("/preferences", response_model=Preferences, operation_id="me_preferences_update",
            responses={409: {"description": "consent required"}})
def put_preferences(request: Request, body: PreferencesIn, user: Student):
    learner = _learner(request)
    if not learner.has_consent(user.student_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "consent required: give consent first")
    prefs = learner.preferences.get(user.student_id)
    for dimension, value in body.model_dump(exclude_none=True).items():
        signal = PreferenceSignal(dimension=dimension, value=value, explicit=True, source="feedback")
        prefs = learner.update_preferences(user.student_id, signal)
    return prefs


@router.get("/answer-instruction", response_model=InstructionIO, operation_id="me_instruction_get")
def get_instruction(request: Request, user: Student):
    """The student's own answer instruction (V15): only the student reads it, never an instructor."""
    return InstructionIO(text=_learner(request).repo.instruction(user.student_id))


@router.put("/answer-instruction", response_model=InstructionIO, operation_id="me_instruction_update",
            responses={409: {"description": "consent required"},
                       422: {"description": "the text contains personal data"}})
def put_instruction(request: Request, body: InstructionIO, user: Student):
    """Saved with consent only, like the other preferences. It is scanned like a question: text with personal
    data (names, numbers, health details, ...) is refused, never stored. It reaches the local model only,
    after the safety and instructor rules, and never overrides them (Z26)."""
    learner = _learner(request)
    if not learner.has_consent(user.student_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "consent required: give consent first")
    text = " ".join(body.text.split())
    if text:
        found = sorted({e.type for e in _analyzer(request).analyze(text)})
        if found:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "remove personal details from the instruction: " + ", ".join(found))
    learner.repo.save_instruction(user.student_id, text)
    return InstructionIO(text=text)


def _analyzer(request: Request):
    from app.privacy.analyzer import PIIAnalyzer

    services = request.app.state.services
    analyzer = getattr(services, "_instruction_analyzer", None)
    if analyzer is None:  # every recognizer: the instruction belongs to no course
        analyzer = services._instruction_analyzer = PIIAnalyzer(services.settings.privacy)
    return analyzer


@router.get("/consent", response_model=ConsentOut, operation_id="me_consent_get")
def get_consent(request: Request, user: Student):
    return ConsentOut(given=_learner(request).repo.consent(user.student_id))


@router.put("/consent", response_model=ConsentOut, operation_id="me_consent_update")
def put_consent(request: Request, body: ConsentIn, user: Student):
    """Withdrawing consent also forgets the learning profile (state, evidence, preferences)."""
    _learner(request).set_consent(user.student_id, body.given)
    return ConsentOut(given=_learner(request).repo.consent(user.student_id))
