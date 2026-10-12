from app.core.config import Settings
from app.core.registry import import_submodules, preference_models
from app.learner.preference.interface import PreferenceModel, PreferenceSignal
from app.learner.repository import LearnerRepository

__all__ = ["PreferenceModel", "PreferenceSignal", "load_preference_model"]


def load_preference_model(settings: Settings, repo: LearnerRepository) -> PreferenceModel:
    """The implementation named by learner.preference (simple; later: ils)."""
    import_submodules("app.learner.preference")
    return preference_models.get(settings.learner.preference)(repo, settings)
