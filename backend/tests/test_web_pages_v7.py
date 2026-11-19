"""v5 V7: web pages as course material and as a draft source. Every fetch goes through `fetch_page`: https,
public addresses only (pinned per request), redirects checked, size and time limits. No real network: the
resolver and the connection are fakes."""
# ruff: noqa: F811  (the `world` fixture of test_instructor_ai_api is reused as a test argument)
import asyncio
import ipaddress

import httpx
import pytest

from app.platform import jobs
from app.rag import web_pages
from tests.conftest import csrf_client
from tests.test_instructor_ai_api import TIER1, _draft, _login, world  # noqa: F401

PUBLIC = ipaddress.ip_address("93.184.216.34")
PAGE = ("<html><head><title>Pull-up resistors explained</title><script>alert(1)</script></head><body>"
        "<nav>Home | About</nav><h1>Pull-up resistors</h1><p>WEB-PASSAGE A pull-up resistor holds an idle "
        "line high.</p></body></html>")


PULLUPS = web_pages.material_name("https://example.org/pullups")


def _resolver(table: dict[str, str] | None = None):
    """Like the real resolver: an address literal is itself, a name is looked up in `table` (else public)."""
    def resolve(host):
        try:
            return [ipaddress.ip_address(host.strip("[]"))]
        except ValueError:
            return [ipaddress.ip_address((table or {}).get(host, str(PUBLIC)))]
    return resolve


def _site(routes: dict[str, httpx.Response]):
    def handler(request: httpx.Request) -> httpx.Response:
        return routes.get(request.headers["host"] + request.url.path, httpx.Response(404))
    return httpx.MockTransport(handler)


def _html(body: str = PAGE) -> httpx.Response:
    return httpx.Response(200, headers={"content-type": "text/html; charset=utf-8"}, text=body)


def fetch(url, routes, table=None):
    return asyncio.run(web_pages.fetch_page(url, resolve=_resolver(table), inner=_site(routes)))


def test_a_public_page_becomes_markdown_with_its_address():
    page = fetch("https://example.org/pullups", {"example.org/pullups": _html()})
    assert page.title == "Pull-up resistors explained" and "WEB-PASSAGE" in page.text
    assert "alert(1)" not in page.text and "Home | About" not in page.text
    text = web_pages.material_text(page)
    assert web_pages.source_url(text.splitlines()[0]) == "https://example.org/pullups"
    assert web_pages.material_name(page.url) == PULLUPS


def test_pages_that_differ_only_in_the_query_get_different_names():
    urls = ("https://example.org/lesson?id=1", "https://example.org/lesson?id=2", "https://example.org/Lesson",
            "https://example.org/lesson")
    names = {web_pages.material_name(u) for u in urls}
    assert len(names) == 4
    assert all(n.startswith("web-example-org-lesson-") and n.endswith(".md") for n in names)


@pytest.mark.parametrize("url", [
    "http://example.org/page",  # not https
    "https://user:secret@example.org/page",  # credentials
    "ftp://example.org/page", "https://",
])
def test_only_https_without_credentials(url):
    with pytest.raises(web_pages.PageRefused):
        fetch(url, {})


@pytest.mark.parametrize("address", ["127.0.0.1", "10.0.0.5", "172.16.3.4", "192.168.1.10", "169.254.169.254",
                                     "::1", "fe80::1", "0.0.0.0"])
def test_private_loopback_and_link_local_addresses_are_refused(address):
    refused = "public address|link-local|special"
    with pytest.raises(web_pages.PageRefused, match=refused):
        fetch("https://inside.example/page", {"inside.example/page": _html()}, {"inside.example": address})
    literal = f"[{address}]" if ":" in address else address
    with pytest.raises(web_pages.PageRefused, match=refused):
        fetch(f"https://{literal}/page", {f"{literal}/page": _html()})


def test_redirects_are_checked_and_limited():
    to_private = {"example.org/a": httpx.Response(302, headers={"location": "https://intranet.example/x"}),
                  "intranet.example/x": _html()}
    with pytest.raises(web_pages.PageRefused, match="public address"):
        fetch("https://example.org/a", to_private, {"intranet.example": "10.1.2.3"})
    to_http = {"example.org/a": httpx.Response(301, headers={"location": "http://example.org/b"})}
    with pytest.raises(web_pages.PageRefused, match="https"):
        fetch("https://example.org/a", to_http)
    loop = {f"example.org/{i}": httpx.Response(302, headers={"location": f"/{i + 1}"}) for i in range(10)}
    with pytest.raises(web_pages.PageRefused, match="redirects"):
        fetch("https://example.org/0", loop)
    ok = {"example.org/old": httpx.Response(301, headers={"location": "/new"}), "example.org/new": _html()}
    assert fetch("https://example.org/old", ok).url == "https://example.org/new"


def test_a_name_that_resolves_differently_at_connect_time_is_refused():
    answers = iter(["93.184.216.34", "10.0.0.7"])  # checked as public, then rebinding to a private address

    def resolve(host):
        return [ipaddress.ip_address(next(answers))]

    with pytest.raises(web_pages.PageRefused, match="public address"):
        asyncio.run(web_pages.fetch_page("https://rebind.example/p", resolve=resolve,
                                         inner=_site({"rebind.example/p": _html()})))


def test_size_type_and_status_limits():
    with pytest.raises(web_pages.PageRefused, match="larger"):
        fetch("https://example.org/big", {"example.org/big": _html("x" * (web_pages.MAX_BYTES + 10))})
    pdf = httpx.Response(200, headers={"content-type": "application/pdf"}, content=b"%PDF-1.4")
    with pytest.raises(web_pages.PageRefused, match="HTML"):
        fetch("https://example.org/f.pdf", {"example.org/f.pdf": pdf})
    with pytest.raises(web_pages.PageRefused, match="404"):
        fetch("https://example.org/missing", {})


def test_a_page_that_never_finishes_is_cut_off(monkeypatch):
    """The time limit covers the whole fetch: small pieces sent just often enough do not keep it open."""
    monkeypatch.setattr(web_pages, "TIMEOUT_S", 0.5)

    async def drip():
        while True:
            await asyncio.sleep(0.05)
            yield b"<p>x</p>"

    slow = httpx.Response(200, headers={"content-type": "text/html"}, content=drip())
    with pytest.raises(web_pages.PageRefused, match="in time"):
        fetch("https://example.org/slow", {"example.org/slow": slow})


def test_the_same_page_twice_with_another_query_can_be_added(world, site):
    prof, url = world["prof"], world["url"]
    for query in ("?id=1", "?id=2"):
        r = prof.post(f"{url}/materials/url", json={"url": f"https://example.org/pullups{query}"})
        assert r.status_code == 201, r.text
    assert len(prof.get(f"{url}/materials").json()["materials"]) == 2


# --------------------------------------------------------------------------------------------- the API
@pytest.fixture
def site(world):
    routes = {"example.org/pullups": _html()}
    world["services"].web_fetch_options = {"resolve": _resolver({"intranet.example": "10.0.0.9"}),
                                           "inner": _site(routes)}
    return routes


def test_an_instructor_adds_a_page_and_fetches_it_again(world, site):
    prof, url = world["prof"], world["url"]
    r = prof.post(f"{url}/materials/url", json={"url": "https://example.org/pullups"})
    assert r.status_code == 201, r.text
    material = r.json()["material"]
    assert material["filename"] == PULLUPS
    assert material["source_url"] == "https://example.org/pullups"
    listed = prof.get(f"{url}/materials").json()["materials"]
    assert [m["source_url"] for m in listed] == ["https://example.org/pullups"]
    assert prof.post(f"{url}/materials/url", json={"url": "https://example.org/pullups"}).status_code == 409
    site["example.org/pullups"] = _html(PAGE.replace("WEB-PASSAGE", "UPDATED-PASSAGE"))
    again = prof.post(f"{url}/materials/{material['id']}/refetch")
    assert again.status_code == 200 and again.json()["job_id"]
    folder = world["tmp"] / "courses" / str(world["course_id"]) / "materials" / "_course"
    stored = folder / material["filename"]
    assert "UPDATED-PASSAGE" in stored.read_text(encoding="utf-8")
    assert prof.post(f"{url}/materials/url", json={"url": "https://intranet.example/x"}).status_code == 422


def test_a_page_with_student_data_is_refused(world, site):
    site["example.org/roster"] = _html("<p>Student 300123456, jane.doe@uottawa.ca, final grade 45%</p>")
    r = world["prof"].post(f"{world['url']}/materials/url", json={"url": "https://example.org/roster"})
    assert r.status_code == 422 and "300123456" not in r.text
    assert world["prof"].get(f"{world['url']}/materials").json()["materials"] == []


def test_a_draft_from_a_web_page(world, site):
    local = world["use"](TIER1)
    r = world["prof"].post(f"{world['url']}/ai/drafts/url", json={
        "url": "https://example.org/pullups", "kind": "custom", "request": "Lab ideas from this page"})
    assert r.status_code == 202, r.text
    assert jobs.run_pending(world["services"]) >= 1
    draft = _draft(world, r.json()["id"])
    assert draft["status"] == "draft" and draft["sources"] == {"upload": PULLUPS}
    assert "WEB-PASSAGE" in local.sent_text() and world["cloud"].calls == []


def test_who_may_add_pages(world, site):
    app, url = world["app"], world["url"]
    page = {"url": "https://example.org/pullups"}
    added = world["prof"].post(f"{url}/materials/url", json=page).json()["material"]["id"]
    draft = {**page, "kind": "faq"}
    for client, code in ((_login(app, "other"), 404), (_login(app, "alice"), 404), (csrf_client(app), 401)):
        assert client.post(f"{url}/materials/url", json=page).status_code == code
        assert client.post(f"{url}/materials/{added}/refetch").status_code == code
        assert client.post(f"{url}/ai/drafts/url", json=draft).status_code == code


def test_a_draft_from_a_web_page_with_student_data_in_the_request_is_refused(world, site):
    leak = "Write feedback for student 300123456 (jane.doe@uottawa.ca), who got 45% on the final."
    r = world["prof"].post(f"{world['url']}/ai/drafts/url", json={
        "url": "https://example.org/pullups", "kind": "custom", "request": leak})
    assert r.status_code == 422 and "300123456" not in r.text
    assert world["prof"].get(f"{world['url']}/ai/drafts").json() == []
