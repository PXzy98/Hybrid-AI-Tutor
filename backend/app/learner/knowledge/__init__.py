from app.core.config import Settings
from app.core.registry import import_submodules, knowledge_models
from app.learner.content import ContentStore
from app.learner.knowledge.interface import KnowledgeModel
from app.learner.repository import LearnerRepository


def load_knowledge_model(settings: Settings, repo: LearnerRepository,
                         content: ContentStore) -> KnowledgeModel:
    """The implementation named by learner.knowledge (bkt | rule)."""
    import_submodules("app.learner.knowledge")
    return knowledge_models.get(settings.learner.knowledge)(repo, settings, content)
