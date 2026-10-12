from app.core.registry import import_submodules, retrievers
from app.rag.interface import Retriever


def load_retriever(name: str) -> Retriever:
    """Instantiate the retriever registered under `name` (config: rag.impl)."""
    import_submodules("app.rag")
    return retrievers.get(name)()
