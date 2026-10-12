from app.core.config import Settings
from app.core.registry import preference_models
from app.core.schemas import Preferences
from app.learner.preference.interface import PreferenceSignal
from app.learner.repository import LearnerRepository

IMPLICIT_STREAK = 3  # consistent implicit signals needed before a preference changes


@preference_models.register("simple")
class SimplePreferenceModel:
    """Two dimensions (sequencing, detail). Explicit signals apply at once; implicit ones need a streak of 3
    consistent signals. Any explicit signal resets the streak of its dimension."""

    def __init__(self, repo: LearnerRepository, settings: Settings) -> None:
        self.repo = repo

    def get(self, student_id: str) -> Preferences:
        row = self.repo.preference_row(student_id)
        if row is None:
            return Preferences()
        return Preferences(sequencing=row.sequencing, detail=row.detail, source=row.source)

    def update(self, student_id: str, signal: PreferenceSignal) -> Preferences:
        row = self.repo.preference_row(student_id)
        prefs = self.get(student_id)
        implicit: dict = dict(row.implicit) if row else {}
        dim = signal.dimension
        if signal.explicit:
            source = "onboarding" if signal.source == "onboarding" else "feedback"
            prefs = prefs.model_copy(update={dim: signal.value, "source": source})
            implicit.pop(dim, None)
        else:
            streak = implicit.get(dim, {"value": None, "count": 0})
            count = streak["count"] + 1 if streak["value"] == signal.value else 1
            streak = {"value": signal.value, "count": count}
            if streak["count"] >= IMPLICIT_STREAK and getattr(prefs, dim) != signal.value:
                prefs = prefs.model_copy(update={dim: signal.value, "source": "feedback"})
                streak = {"value": None, "count": 0}
            implicit[dim] = streak
        self.repo.save_preferences(student_id, prefs, implicit)
        return prefs
