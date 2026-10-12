"""Preference Model: how to present, never what to teach (design §5.2). Selected by `learner.preference`."""
from typing import Literal, Protocol, runtime_checkable

from pydantic import BaseModel

from app.core.schemas import Preferences

Dimension = Literal["sequencing", "detail"]
ALLOWED: dict[str, tuple[str, ...]] = {
    "sequencing": ("example_first", "concept_first"),
    "detail": ("concise", "detailed"),
}


class PreferenceSignal(BaseModel):
    dimension: Dimension
    value: str  # one of ALLOWED[dimension]
    explicit: bool  # a button / onboarding answer (applies now) or an inferred hint (needs repetition)
    source: Literal["onboarding", "feedback", "implicit"] = "feedback"

    def model_post_init(self, _) -> None:
        if self.value not in ALLOWED[self.dimension]:
            raise ValueError(f"{self.dimension} must be one of {ALLOWED[self.dimension]}")


@runtime_checkable
class PreferenceModel(Protocol):
    def get(self, student_id: str) -> Preferences: ...

    def update(self, student_id: str, signal: PreferenceSignal) -> Preferences: ...
