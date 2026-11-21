from app.core.registry import import_submodules, routers
from app.routing.interface import RouteScorer


def load_router(name: str) -> RouteScorer:
    """Instantiate the router registered under `name` (config: routing.impl)."""
    import_submodules("app.routing")
    return routers.get(name)()


def load_type_routers(by_course_type: dict[str, str], default_impl: str) -> dict[str, RouteScorer]:
    """Routers for `routing.by_course_type` (V19): one instance per router name, keyed by course type; a type
    that names the default router is left out (it uses the shared one)."""
    built: dict[str, RouteScorer] = {}
    out: dict[str, RouteScorer] = {}
    for course_type, impl in by_course_type.items():
        if impl == default_impl:
            continue
        if impl not in built:
            built[impl] = load_router(impl)
        out[course_type] = built[impl]
    return out
