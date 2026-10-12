"""Routing score: black box owned by Tongkai. Only this interface is fixed here (design §1, §9)."""
from typing import Protocol, runtime_checkable

from app.core.schemas import RouteInput, RouteScore


@runtime_checkable
class RouteScorer(Protocol):
    """Implementations are classes with a no-argument constructor, registered with
    `@routers.register("<name>")` and selected by `routing.impl` in config.yaml.

    `route_score` must be synchronous, deterministic for the same input, return a score in [0, 1]
    (>= routing.threshold means cloud), and must not raise on unusual input such as an empty question.
    It must use only the fields of RouteInput.
    """

    def route_score(self, x: RouteInput) -> RouteScore: ...
