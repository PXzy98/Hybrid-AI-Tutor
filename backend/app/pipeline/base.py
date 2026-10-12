"""Protocols for pipeline steps and verification checkers (design §7.1, §9)."""
from typing import TYPE_CHECKING, ClassVar, Literal, Protocol, runtime_checkable

from app.core.schemas import CheckResult, RequestContext

if TYPE_CHECKING:
    from app.core.services import Services

OnError = Literal["stop", "skip", "warn"]


@runtime_checkable
class Step(Protocol):
    name: str
    on_error: OnError  # stop: abort the request · skip: continue · warn: continue + add a warning

    async def run(self, ctx: RequestContext) -> RequestContext: ...


@runtime_checkable
class Checker(Protocol):
    name: str

    def check(self, ctx: RequestContext) -> CheckResult: ...


class BaseStep:
    """Convenience base for steps: registered classes are constructed with the shared Services."""

    name: ClassVar[str]
    on_error: ClassVar[OnError] = "skip"

    def __init__(self, services: "Services") -> None:
        self.services = services

    async def run(self, ctx: RequestContext) -> RequestContext:
        raise NotImplementedError
