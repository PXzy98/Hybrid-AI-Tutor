"""pii_leak and profile_leak checkers: audit what was actually sent to the cloud (ctx.cloud_request)."""
from app.core.registry import checkers
from app.core.schemas import CheckResult, RequestContext
from app.privacy.analyzer import PIIAnalyzer
from app.verify.leaks import pii_problems, profile_problems


@checkers.register("pii_leak")
class PiiLeakChecker:
    name = "pii_leak"

    def __init__(self, services) -> None:
        self.analyzer = PIIAnalyzer(services.settings.privacy)

    def check(self, ctx: RequestContext) -> CheckResult:
        if ctx.cloud_request is None:
            return CheckResult(name=self.name, status="pass", detail="nothing sent to the cloud")
        found = pii_problems(self.analyzer, ctx.cloud_request)
        return CheckResult(name=self.name, status="fail" if found else "pass", detail="; ".join(found))


@checkers.register("profile_leak")
class ProfileLeakChecker:
    name = "profile_leak"

    def __init__(self, services) -> None:
        self.content = services.content

    def check(self, ctx: RequestContext) -> CheckResult:
        if ctx.cloud_request is None:
            return CheckResult(name=self.name, status="pass", detail="nothing sent to the cloud")
        found = profile_problems(ctx.cloud_request, ctx, self.content)
        return CheckResult(name=self.name, status="fail" if found else "pass", detail="; ".join(found))
