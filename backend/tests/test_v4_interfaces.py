"""Task Z1: the v4 interfaces exist, their stand-ins are safe, and the v2 API is mounted."""
import asyncio

import pytest
from fastapi import Depends, FastAPI
from fastapi.testclient import TestClient

from app.api.v2 import api_router_v2
from app.api.v2.errors import usage_limit_handler
from app.auth.deps import CurrentUser, require_any
from app.core.config import Settings
from app.core.schemas import AskRequest, CourseRef, RequestContext, SemanticAnalysis
from app.learner.instructor_view import NotVisible, profile_for_instructor
from app.llm.base import LLMUnavailable
from app.llm.fake import FakeLLMClient
from app.llm.gateway import FakeGateway, TrustViolation
from app.main import create_app
from app.platform.access import CourseAccess, FakeCourseDirectory, require_course_role
from app.platform.settings import effective_settings
from app.platform.usage import NoLimits, UsageLimitExceeded
from app.privacy.profiles import privacy_profile, scan_document, search_query
from app.rag.course import FakeCourseRetriever
from app.websearch import web_search

COURSE = CourseRef(id=7, code="ELG 5902", title="Test course", course_type="ece")
StudentAccess = Depends(require_course_role("student"))


def _user(account_id: int, role="student") -> CurrentUser:
    return CurrentUser(account_id, f"user{account_id}", "User", role, "sid" if role == "student" else None,
                       False, "token")


def _app(directory: FakeCourseDirectory | None, user: CurrentUser) -> TestClient:
    app = FastAPI()

    @app.get("/courses/{course_id}/ping")
    def ping(access: CourseAccess = StudentAccess):
        return {"course": access.course.code}

    if directory is not None:
        app.state.course_directory = directory
    app.dependency_overrides[require_any] = lambda: user
    return TestClient(app)


def test_effective_settings_default_to_the_config_file():
    settings = Settings()
    eff = effective_settings(3, settings)
    assert eff.course_id == 3
    assert eff.routing_threshold == settings.routing.threshold
    assert eff.knowledge_model == settings.learner.knowledge
    assert eff.checkers == tuple(settings.verify.checkers)
    assert eff.course_type == "general" and eff.visibility_mode == "A" and not eff.local_only


def test_new_context_fields_are_optional_so_v1_keeps_working():
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question="q"))
    assert ctx.course is None and ctx.module_id is None and ctx.settings is None and ctx.profile is None
    assert SemanticAnalysis(method="lr").question_kind == "concept"


def test_course_role_is_refused_without_a_directory():
    assert _app(None, _user(1)).get("/courses/7/ping").status_code == 404


def test_course_role_needs_membership_in_that_course_and_the_right_role():
    directory = FakeCourseDirectory()
    directory.add(CourseAccess(course=COURSE, account_id=1, role="student", student_id="sid"))
    directory.add(CourseAccess(course=COURSE, account_id=2, role="instructor", student_id=None))
    assert _app(directory, _user(1)).get("/courses/7/ping").json() == {"course": "ELG 5902"}
    assert _app(directory, _user(1)).get("/courses/8/ping").status_code == 404  # another course
    assert _app(directory, _user(3)).get("/courses/7/ping").status_code == 404  # not a member
    assert _app(directory, _user(2, "instructor")).get("/courses/7/ping").status_code == 404  # wrong role


def test_gateway_never_sends_trusted_content_to_an_external_model():
    cloud = FakeLLMClient("cloud", backend="cloud")
    gateway = FakeGateway({"local": FakeLLMClient("local"), "cloud": cloud})
    eff = effective_settings(1, Settings())
    with pytest.raises(TrustViolation):
        asyncio.run(gateway.complete("cloud", [{"role": "user", "content": "x"}], settings=eff,
                                     trust_required="trusted_local"))
    assert cloud.calls == []
    result = asyncio.run(gateway.complete("local", [{"role": "user", "content": "x"}], settings=eff,
                                          trust_required="trusted_local"))
    assert result.text == "local"


def test_gateway_respects_a_local_only_course():
    gateway = FakeGateway({"cloud": FakeLLMClient("cloud", backend="cloud")})
    eff = effective_settings(1, Settings()).model_copy(update={"local_only": True})
    with pytest.raises(LLMUnavailable):
        asyncio.run(gateway.complete("cloud", [{"role": "user", "content": "x"}], settings=eff,
                                     trust_required="external_ok"))


def test_gateway_streams_tokens():
    gateway = FakeGateway({"local": FakeLLMClient("one two")})
    eff = effective_settings(1, Settings())

    async def collect():
        stream = await gateway.complete("local", [{"role": "user", "content": "x"}], settings=eff,
                                        trust_required="trusted_local", stream=True)
        return "".join([t async for t in stream])

    assert asyncio.run(collect()).split() == ["one", "two"]


def test_privacy_stand_ins_are_safe():
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question="I am Ann"))
    assert search_query(ctx) is None  # no query, so no web search
    assert scan_document("Ann Lee 300123456", privacy_profile("general")).scanned is False  # never "clean"
    medical = privacy_profile("medical_science")
    assert "medical_safety" in medical.checkers and medical.medical_disclaimer
    assert privacy_profile("ece").checkers == ()


def test_instructor_view_is_refused_until_s9():
    access = CourseAccess(course=COURSE, account_id=2, role="instructor", student_id=None)
    with pytest.raises(NotVisible):
        profile_for_instructor(access, "sid")


def test_other_stand_ins():
    assert asyncio.run(web_search("query", ["medlineplus.gov"])) == []
    retriever = FakeCourseRetriever()
    assert retriever.retrieve(7, None, "q") == [] and retriever.calls == [(7, None, "q", 4)]
    NoLimits().check_usage("sid", 7, "question")


def test_v2_is_mounted_and_usage_limits_are_429():
    assert api_router_v2.prefix == "/api/v2"
    assert UsageLimitExceeded in create_app().exception_handlers

    app = FastAPI()
    app.add_exception_handler(UsageLimitExceeded, usage_limit_handler)

    @app.get("/limited")
    def limited():
        raise UsageLimitExceeded("question", 30)

    r = TestClient(app).get("/limited")
    assert r.status_code == 429
    assert r.json() == {"detail": "Usage limit reached. Try again later.", "code": "usage_limit",
                        "retry_after_seconds": 30}
