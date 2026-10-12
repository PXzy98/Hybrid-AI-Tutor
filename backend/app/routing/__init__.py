from app.core.registry import import_submodules, routers
from app.routing.interface import RouteScorer


def load_router(name: str) -> RouteScorer:
    """Instantiate the router registered under `name` (config: routing.impl)."""
    import_submodules("app.routing")
    return routers.get(name)()
