"""The student's global learning preferences and consent (api-v2.md 3.1; course-structure.md 4; task Z9).

Both are global (one per student, not per course) and go through the learner model's own interface: without
consent nothing is stored, and withdrawing consent forgets the learning profile.
"""
from typing import Literal

from fastapi import APIRouter, HTTPException, Request, status
from pydantic import BaseModel, Field, field_validator

from app.auth.deps import Student
from app.core.schemas import Preferences
from app.learner.preference.interface import PreferenceSignal

router = APIRouter(prefix="/me", tags=["me"])

INSTRUCTION_MAX_CHARS = 300


class PreferencesIn(BaseModel):
    sequencing: Literal["example_first", "concept_first"] | None = None
    detail: Literal["concise", "detailed"] | None = None


class InstructionIO(BaseModel):
    # V15: how answers should be presented, in the student's words; "" removes it
    text: str = Field("", max_length=1000)  # raw bound; 300 counted after collapsing spaces

    @field_validator("text")
    @classmethod
    def _normalized(cls, value: str) -> str:
        value = " ".join(value.split())
        if len(value) > INSTRUCTION_MAX_CHARS:
            raise ValueError(f"at most {INSTRUCTION_MAX_CHARS} characters")
        return value


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
                       422: {"description": "the text contains personal data or the characters < and >"}})
def put_instruction(request: Request, body: InstructionIO, user: Student):
    """Saved with consent only, like the other preferences. It is scanned like a question: text with personal
    data (names, numbers, health details, ...) is refused, never stored. It reaches the local model only,
    after the safety and instructor rules, and never overrides them (Z26)."""
    learner = _learner(request)
    if not learner.has_consent(user.student_id):
        raise HTTPException(status.HTTP_409_CONFLICT, "consent required: give consent first")
    text = body.text
    if "<" in text or ">" in text:  # the text sits inside a tag of the system prompt: it must not close it
        raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                            "remove the characters < and > from the instruction")
    if text:
        # the student's own name and username too, as in the privacy filter: NER misses some of them
        names, usernames = request.app.state.services.accounts.identity_terms(user.student_id)
        found = sorted({e.type for e in _analyzer(request).analyze(text, names, usernames)})
        if found:
            raise HTTPException(status.HTTP_422_UNPROCESSABLE_ENTITY,
                                "remove personal details from the instruction: " + ", ".join(found))
    learner.repo.save_instruction(user.student_id, text)
    return InstructionIO(text=text)


def _analyzer(request: Request):
    """The analyzer of the privacy filter step (built at startup, all recognizers): the instruction belongs to
    no course."""
    for step in request.app.state.services.components.runner.pipeline:
        if step.name == "privacy_filter":
            return step.analyzer
    raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "the privacy filter is not available")


@router.get("/consent", response_model=ConsentOut, operation_id="me_consent_get")
def get_consent(request: Request, user: Student):
    return ConsentOut(given=_learner(request).repo.consent(user.student_id))


@router.put("/consent", response_model=ConsentOut, operation_id="me_consent_update")
def put_consent(request: Request, body: ConsentIn, user: Student):
    """Withdrawing consent also forgets the learning profile (state, evidence, preferences)."""
    _learner(request).set_consent(user.student_id, body.given)
    return ConsentOut(given=_learner(request).repo.consent(user.student_id))
