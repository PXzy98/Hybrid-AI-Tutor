"""Task Z7: privacy profiles from one file each; the base layer for every course; profile by course type."""
import pytest

from app.core.schemas import AskRequest, RequestContext
from app.pipeline.settings_view import health_detail_policy
from app.privacy import profiles
from app.privacy.analyzer import custom_recognizer_names


@pytest.fixture
def profile_dir(tmp_path, monkeypatch):
    for name in ("base", "general", "medical_science"):
        (tmp_path / f"{name}.yaml").write_text((profiles.PROFILE_DIR / f"{name}.yaml").read_text("utf-8"),
                                               encoding="utf-8")
    monkeypatch.setattr(profiles, "PROFILE_DIR", tmp_path)
    profiles._raw.cache_clear()
    profiles.privacy_profile.cache_clear()
    yield tmp_path
    profiles._raw.cache_clear()
    profiles.privacy_profile.cache_clear()


def test_the_medical_profile_is_the_v3_behaviour_and_others_build_on_the_base_layer():
    medical = profiles.privacy_profile("medical_science")
    ece_only = {"internal_address", "repo_url"}  # task Z11: lab addresses and repositories
    # E6 / demo course unchanged: every recognizer but the ECE-only ones
    assert sorted(medical.recognizers) == sorted(set(custom_recognizer_names()) - ece_only)
    assert ece_only <= set(profiles.privacy_profile("ece").recognizers)
    assert (medical.health_detail_policy, medical.checkers, medical.medical_disclaimer) == (
        "generalize", ("medical_safety",), True)
    for name in ("general", "ece", "life_science"):
        p = profiles.privacy_profile(name)
        assert {"student_id", "grade", "address", "health_detail"} <= set(p.recognizers)
        assert "health_context" not in p.recognizers and p.health_detail_policy == "local_only"
        assert not p.medical_disclaimer and p.checkers == ()
    assert profiles.profile_names() == ["ece", "general", "life_science", "medical_science"]


def test_a_new_profile_needs_one_file_and_becomes_a_course_type(profile_dir):
    (profile_dir / "law.yaml").write_text("extends: base\nrecognizers: []\n", encoding="utf-8")
    assert "law" in profiles.profile_names()
    assert profiles.privacy_profile("law").recognizers == profiles.privacy_profile("general").recognizers
    from app.platform.settings import validate_course

    assert validate_course({"course_type": "law"})["course_type"] == "law"


@pytest.mark.parametrize("content", ["extends: base\nrecognizers: [no_such_recognizer]\n",
                                     "extends: base\ncheckers: [no_such_checker]\n",
                                     "extends: base\ncolour: blue\n",
                                     "", "recognizers: [grade]\n", "extends: general\n"])
def test_invalid_profile_files_are_refused(profile_dir, content):
    (profile_dir / "broken.yaml").write_text(content, encoding="utf-8")
    with pytest.raises(profiles.ProfileError):
        profiles.privacy_profile("broken")


def test_unknown_profiles_and_the_base_layer_are_not_course_types():
    for name in ("base", "astrology"):
        with pytest.raises(profiles.ProfileError):
            profiles.privacy_profile(name)


def test_the_stricter_health_policy_applies(use_config):
    from app.core.services import build_services

    services = build_services(use_config())  # config.yaml: generalize
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question="q"))
    for name, expected in (("medical_science", "generalize"), ("general", "local_only")):
        assert health_detail_policy(ctx.model_copy(update={"profile": profiles.privacy_profile(name)}),
                                    services) == expected
    strict = build_services(use_config({"privacy": {"health_detail_policy": "local_only"}}))
    medical = ctx.model_copy(update={"profile": profiles.privacy_profile("medical_science")})
    assert health_detail_policy(medical, strict) == "local_only"


@pytest.mark.presidio
def test_the_course_type_selects_the_recognizers(use_config):
    import asyncio

    from app.core.services import build_services
    from app.pipeline.steps.privacy_filter import PrivacyFilterStep

    step = PrivacyFilterStep(build_services(use_config()))
    question = "My student number is 300418277. What is a capacitor?"
    for name in ("general", "ece", "medical_science"):
        ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question=question),
                             profile=profiles.privacy_profile(name))
        out = asyncio.run(step.run(ctx))
        assert "300418277" not in out.pii.sanitized_text  # the base layer protects every course
    assert step._by_profile["general"] is not step._by_profile["medical_science"]
