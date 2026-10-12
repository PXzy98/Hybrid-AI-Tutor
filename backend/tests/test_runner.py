import pytest

from app.core.schemas import AskRequest, RequestContext
from app.core.services import build_services
from app.pipeline.runner import PipelineConfigError, PipelineError, PipelineRunner, build_runner


class FakeStep:
    def __init__(self, name, on_error="skip", fail=False, calls=None):
        self.name, self.on_error, self.fail = name, on_error, fail
        self.calls = calls if calls is not None else []

    async def run(self, ctx):
        self.calls.append(self.name)
        if self.fail:
            raise ValueError("Alice Tremblay 300418277")  # must never reach logs or responses
        return ctx


def make_ctx() -> RequestContext:
    return RequestContext(request_id="r-1", request=AskRequest(student_id="s", topic="asthma", question="q"))


async def test_runs_steps_in_order_and_times_each():
    calls = []
    runner = PipelineRunner([FakeStep("a", calls=calls), FakeStep("b", calls=calls)])
    ctx = await runner.run(make_ctx())
    assert calls == ["a", "b"]
    assert set(ctx.timings_ms) == {"a", "b"}


async def test_stop_raises_pipeline_error_and_stops(caplog):
    calls = []
    runner = PipelineRunner([FakeStep("a", "stop", fail=True, calls=calls), FakeStep("b", calls=calls)])
    ctx = make_ctx()
    with pytest.raises(PipelineError) as e:
        await runner.run(ctx)
    assert e.value.step == "a" and e.value.reason == "ValueError"
    assert calls == ["a"]
    assert "a" in ctx.timings_ms  # timed even when it fails
    assert "Alice" not in caplog.text and "300418277" not in str(e.value)


async def test_skip_continues_silently():
    calls = []
    runner = PipelineRunner([FakeStep("a", "skip", fail=True, calls=calls), FakeStep("b", calls=calls)])
    ctx = await runner.run(make_ctx())
    assert calls == ["a", "b"] and ctx.warnings == []


async def test_warn_continues_with_generic_warning():
    runner = PipelineRunner([FakeStep("verify", "warn", fail=True), FakeStep("b")])
    ctx = await runner.run(make_ctx())
    assert ctx.warnings == ["verify: could not be completed"]


async def test_post_response_errors_are_swallowed(caplog):
    calls = []
    runner = PipelineRunner([], [FakeStep("p1", fail=True, calls=calls), FakeStep("p2", calls=calls)])
    await runner.run_post(make_ctx())
    assert calls == ["p1", "p2"]
    assert "Alice" not in caplog.text


def test_build_runner_follows_config(use_config):
    use_config()
    runner = build_runner(build_services())
    assert runner.step_names[0] == "privacy_filter" and len(runner.step_names) == 10
    assert [s.name for s in runner.post_response] == ["update_learner"]


@pytest.mark.parametrize("pipeline", [["retrieve", "privacy_filter"], [], ["route"]])
def test_privacy_filter_must_come_first(use_config, pipeline):
    use_config({"pipeline": pipeline})
    with pytest.raises(PipelineConfigError):
        build_runner(build_services())


def test_unknown_step_name_fails_at_startup(use_config):
    use_config({"pipeline": ["privacy_filter", "no_such_step"]})
    with pytest.raises(KeyError, match="no_such_step"):
        build_runner(build_services())
