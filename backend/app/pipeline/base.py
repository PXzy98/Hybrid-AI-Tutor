"""Protocols for pipeline steps and verification checkers (design §7.1, §9)."""
from typing import Literal, Protocol, runtime_checkable

from app.core.schemas import CheckResult, RequestContext

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
