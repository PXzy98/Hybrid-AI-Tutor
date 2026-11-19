"""v5 V16: an instructor may draft with the cloud model from public course material, only after confirming
that the material goes to it, and never in a local-only course. The local model stays the default. Fakes."""
# ruff: noqa: F811  (the `world` fixture of test_instructor_ai_api is reused as a test argument)
from app.platform import jobs
from tests.test_instructor_ai_api import TIER1, _draft, world  # noqa: F401
from tests.test_web_pages_v7 import _html, _resolver, _site


def _start(world, body):
    return world["prof"].post(f"{world['url']}/ai/drafts", json=body)


def test_the_cloud_model_drafts_only_after_confirmation(world):
    local = world["use"](TIER1)
    world["cloud"].replies = [TIER1]
    assert _start(world, {"kind": "faq", "model": "cloud"}).status_code == 422  # not confirmed
    r = _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True})
    assert r.status_code == 202, r.text
    assert jobs.run_pending(world["services"]) >= 1
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "draft" and draft["sources"].get("model") == "cloud"
    assert len(world["cloud"].calls) == 1 and local.calls == []


def test_the_local_model_stays_the_default(world):
    local = world["use"](TIER1)
    r = _start(world, {"kind": "faq"})
    assert jobs.run_pending(world["services"]) >= 1
    assert _draft(world, r.json()["id"])["status"] == "draft"
    assert len(local.calls) == 1 and world["cloud"].calls == []


def test_a_local_only_course_never_drafts_with_the_cloud(world):
    world["use"](TIER1)
    prof, url = world["prof"], world["url"]
    current = prof.get(f"{url}/settings").json()
    assert prof.put(f"{url}/settings", json={"values": {"local_only": True},
                                             "version": current["version"]}).status_code == 200
    assert _start(world, {"kind": "faq", "model": "cloud", "confirm_cloud": True}).status_code == 409
    world["services"].web_fetch_options = {"resolve": _resolver(), "inner": _site({"example.org/p": _html()})}
    page = {"url": "https://example.org/p", "kind": "faq", "model": "cloud", "confirm_cloud": True}
    assert prof.post(f"{url}/ai/drafts/url", json=page).status_code == 409
    assert world["cloud"].calls == []
