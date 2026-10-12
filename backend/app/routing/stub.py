from app.core.config import get_settings
from app.core.registry import routers
from app.core.schemas import RouteInput, RouteScore


@routers.register("stub")
class StubRouter:
    """Fixed score from `routing.stub_score` (default 0.0 = always local).

    Used until the real router exists.
    """

    def __init__(self) -> None:
        self.score = get_settings().routing.stub_score

    def route_score(self, x: RouteInput) -> RouteScore:
        return RouteScore(score=self.score, reasons=["stub router: fixed score"])
