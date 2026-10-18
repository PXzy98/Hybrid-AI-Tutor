"""Runs the configured steps on one RequestContext (design §7.1).

Failure policy per step: stop -> PipelineError, skip -> continue, warn -> continue + ctx.warnings.
Log lines carry the step name, the exception type and the request id only, never request text.
"""

import logging
from collections.abc import Sequence
from time import perf_counter
from typing import TYPE_CHECKING

from app.core.registry import import_submodules, steps
from app.core.schemas import RequestContext
from app.pipeline.base import Step

if TYPE_CHECKING:
    from app.core.services import Services

log = logging.getLogger("app.pipeline")


class PipelineError(Exception):
    def __init__(self, step: str, reason: str) -> None:
        super().__init__(f"step '{step}' failed: {reason}")
        self.step = step
        self.reason = reason


class PipelineConfigError(ValueError):
    pass


class PipelineRunner:
    def __init__(self, pipeline: Sequence[Step], post_response: Sequence[Step] = ()) -> None:
        self.pipeline = list(pipeline)
        self.post_response = list(post_response)

    @property
    def step_names(self) -> list[str]:
        return [s.name for s in self.pipeline]

    async def run(self, ctx: RequestContext) -> RequestContext:
        for step in self.pipeline:
            t0 = perf_counter()
            progress_stage = {
                "understand": "preparation",
                "generate": "generation",
                "verify": "verification",
            }.get(step.name)
            if progress_stage:
                await ctx.report(progress_stage, "running")
            failed = False
            try:
                ctx = await step.run(ctx) or ctx
            except Exception as e:
                failed = True
                log.warning(
                    "step %s failed (%s), policy=%s, request=%s",
                    step.name,
                    type(e).__name__,
                    step.on_error,
                    ctx.request_id,
                )
                if step.on_error == "stop":
                    raise PipelineError(step.name, type(e).__name__) from e
                if step.on_error == "warn":
                    ctx.warnings.append(f"{step.name}: could not be completed")
            finally:
                ctx.timings_ms[step.name] = round((perf_counter() - t0) * 1000, 2)
                if progress_stage:
                    await ctx.report(
                        progress_stage,
                        "failed" if failed else "completed",
                        duration_ms=ctx.timings_ms[step.name],
                    )
        return ctx

    async def run_post(self, ctx: RequestContext) -> None:
        """Post-response steps (FastAPI background task). Errors are logged only."""
        for step in self.post_response:
            try:
                await step.run(ctx)
            except Exception as e:  # noqa: BLE001
                log.warning(
                    "post-response step %s failed (%s), request=%s",
                    step.name,
                    type(e).__name__,
                    ctx.request_id,
                )


def build_runner(services: "Services") -> PipelineRunner:
    """Build the runner from config.pipeline / config.post_response."""
    settings = services.settings
    if not settings.pipeline or settings.pipeline[0] != "privacy_filter":
        # privacy invariant 5: nothing may see the question before the privacy filter
        raise PipelineConfigError("config.pipeline must start with 'privacy_filter'")
    import_submodules("app.pipeline.steps")
    built = [steps.get(n)(services) for n in settings.pipeline]
    if built[0].on_error != "stop":
        raise PipelineConfigError("privacy_filter must use on_error='stop'")
    post = [steps.get(n)(services) for n in settings.post_response]
    return PipelineRunner(built, post)
