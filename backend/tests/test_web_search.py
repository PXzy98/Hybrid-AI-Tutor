"""T13: web search (off / hosted API / SearXNG), allowed sites, cleaning, and the pipeline step (rule 5).

No real network: the HTTP calls go to an httpx.MockTransport. All questions are fictional.
"""
import json

import httpx
import pytest

from app.core.schemas import AskRequest, Chunk, PIIResult, RequestContext, SemanticAnalysis
from app.core.services import build_services
from app.llm.fake import FakeLLMClient
from app.llm.ssrf import UnsafeEndpoint
from app.pipeline.steps import web_search as step_module
from app.pipeline.steps.generate import llm_flags_health
from app.pipeline.steps.web_search import WebSearchStep
from app.privacy.profiles import search_query
from app.rag.sources import source_positions
from app.websearch import (
    WebSearchError,
    allowed_site,
    allowlist_for,
    clean,
    clear_cache,
    engines_for,
    web_search,
)

SITES = ["medlineplus.gov", "nih.gov"]
RESULTS = [
    {"url": "https://medlineplus.gov/news/a.html", "title": "<b>New guideline</b>", "score": 0.9,
     "content": "<p>Updated   advice&nbsp;on salt.</p><script>track()</script>"},
    {"url": "https://www.ncbi.nlm.nih.gov/b", "title": "Study", "content": "A 2026 study."},
    {"url": "https://medlineplus.gov/news/a.html", "title": "Duplicate", "content": "Same page again."},
    {"url": "http://nih.gov/c", "title": "Plain HTTP", "content": "Not https."},
    {"url": "https://example.com/d", "title": "Other site", "content": "Not allowed."},
    {"url": "https://evilnih.gov/e", "title": "Look-alike", "content": "Not a subdomain."},
    {"url": "https://nih.gov/empty", "title": "Empty", "content": "   "},
]


@pytest.fixture(autouse=True)
def _no_cached_results():
    clear_cache()
    yield
    clear_cache()


@pytest.fixture
def settings(use_config, monkeypatch):
    monkeypatch.setattr("app.websearch._check_url", lambda url, trust: None)  # no DNS in tests

    def _make(provider, **extra):
        return use_config({"websearch": {"provider": provider, "max_results": 3, **extra}})
    return _make


def recorder(responses):
    calls: list[httpx.Request] = []

    def handle(request: httpx.Request) -> httpx.Response:
        calls.append(request)
        out = responses(request) if callable(responses) else responses
        return out if isinstance(out, httpx.Response) else httpx.Response(200, json=out)
    return calls, httpx.MockTransport(handle)


# ------------------------------------------------------------------ allowed sites and cleaning
@pytest.mark.parametrize(("url", "ok"), [
    ("https://nih.gov/x", True), ("https://www.ncbi.nlm.nih.gov/x", True), ("https://NIH.gov/x", True),
    ("http://nih.gov/x", False), ("https://evilnih.gov/x", False), ("https://nih.gov.evil.com/x", False),
    ("ftp://nih.gov/x", False), ("not a url", False),
])
def test_allowed_sites(url, ok):
    assert allowed_site(url, SITES) is ok


def test_clean_removes_markup_and_cuts_at_a_word():
    assert clean("<p>Hello&amp;   <b>world</b></p><style>x{}</style>", 100) == "Hello& world"
    cut = clean("one two three four five", 12)
    assert cut == "one two …" and len(cut) <= 12


def test_allowlist_per_course_type(settings):
    cfg = settings("off", allowlist={"medical_science": SITES, "general": ["wikipedia.org"]})
    assert allowlist_for("medical_science", cfg) == SITES
    assert allowlist_for("custom_type", cfg) == ["wikipedia.org"]  # no list of its own: general
    assert allowlist_for(None, cfg) == ["wikipedia.org"]


# ------------------------------------------------------------------ providers
async def test_off_makes_no_request(settings):
    calls, transport = recorder({"results": RESULTS})
    found = await web_search("salt and blood pressure", SITES, settings=settings("off"), transport=transport)
    assert found == []
    assert calls == []


async def test_api_sends_only_the_query_and_the_allow_list(settings, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-test-key")
    calls, transport = recorder({"results": RESULTS})
    found = await web_search("salt and blood pressure", SITES, settings=settings("api"), transport=transport)
    (request,) = calls
    body = json.loads(request.content)
    assert body["query"] == "salt and blood pressure" and body["include_domains"] == SITES
    assert request.headers["Authorization"] == "Bearer fake-test-key"
    assert [c.source for c in found] == ["https://medlineplus.gov/news/a.html", "https://www.ncbi.nlm.nih.gov/b"]
    first = found[0]
    assert first.text == "Updated advice on salt." and first.metadata == {
        "web": True, "title": "New guideline", "url": "https://medlineplus.gov/news/a.html"}
    assert first.score == 0.9 and found[1].score == 0.0


async def test_api_without_a_key_or_with_an_error_fails(settings, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-other-key")  # another provider's key is not used
    _, transport = recorder({"results": RESULTS})
    with pytest.raises(WebSearchError, match="TAVILY_API_KEY"):
        await web_search("q words here", SITES, settings=settings("api"), transport=transport)
    monkeypatch.setenv("TAVILY_API_KEY", "fake-test-key")
    _, broken = recorder(httpx.Response(401, json={"detail": "bad key"}))
    with pytest.raises(WebSearchError, match="401"):
        await web_search("q words here", SITES, settings=settings("api"), transport=broken)


async def test_api_still_reads_the_old_key_name(settings, monkeypatch):
    monkeypatch.setenv("WEBSEARCH_API_KEY", "fake-old-key")
    calls, transport = recorder({"results": RESULTS})
    await web_search("salt and blood pressure", SITES, settings=settings("api"), transport=transport)
    assert calls[0].headers["Authorization"] == "Bearer fake-old-key"


async def test_the_api_must_be_a_public_address(use_config, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-test-key")
    cfg = use_config({"websearch": {"provider": "api", "api_url": "http://10.0.0.5/search"}})
    with pytest.raises(UnsafeEndpoint):  # the real SSRF check (an IP address needs no DNS)
        await web_search("q words here", SITES, settings=cfg)


def _openai_reply() -> dict:
    """A Responses API answer: findings with inline links, cited by url_citation annotations."""
    cdc = "https://www.cdc.gov/rsv/adults.html?utm_source=openai"
    parts = [("**Adults 75 and older** should get one dose ", cdc, "RSV vaccine guidance"),
             ("\n\n- A 2025 study found lower risk ", "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/", "Study"),
             ("\n- Another claim from an outside site ", "https://example.com/x", "Other")]
    text, annotations = "", []
    for words, url, title in parts:
        text += words
        link = f"([{title}]({url}))."
        annotations.append({"type": "url_citation", "url": url, "title": title, "start_index": len(text),
                            "end_index": len(text) + len(link)})
        text += link
    return {"output": [{"type": "web_search_call", "status": "completed"},
                       {"type": "message", "content": [{"type": "output_text", "text": text,
                                                        "annotations": annotations}]}]}


OPENAI_REPLY = _openai_reply()


async def test_openai_sends_only_the_query_and_the_allow_list(settings, monkeypatch):
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    calls, transport = recorder(OPENAI_REPLY)
    found = await web_search("RSV vaccine for older adults", SITES + ["cdc.gov"], settings=settings("openai"),
                             transport=transport)
    body = json.loads(calls[0].content)
    assert calls[0].url == "https://api.openai.com/v1/responses"
    assert body["input"] == "RSV vaccine for older adults" and body["model"] == "gpt-6-luna"
    assert body["tools"] == [{"type": "web_search", "filters": {"allowed_domains": SITES + ["cdc.gov"]}}]
    assert set(body) == {"model", "instructions", "input", "max_output_tokens", "reasoning", "tool_choice",
                         "tools"}  # nothing about the student or the course
    # one passage per cited page on an allowed site, without links, bold markers or tracking parameters
    assert [c.source for c in found] == ["https://www.cdc.gov/rsv/adults.html",
                                         "https://pmc.ncbi.nlm.nih.gov/articles/PMC1/"]
    assert found[0].text == "Adults 75 and older should get one dose ."
    assert found[0].metadata["title"] == "RSV vaccine guidance"


async def test_openai_without_a_key_or_with_an_error_fails(settings, monkeypatch):
    calls, transport = recorder(OPENAI_REPLY)
    for other in ("TAVILY_API_KEY", "WEBSEARCH_API_KEY"):  # other providers' keys are not used
        monkeypatch.setenv(other, "fake-other-key")
    with pytest.raises(WebSearchError, match="OPENAI_API_KEY"):
        await web_search("RSV vaccine for older adults", SITES, settings=settings("openai"),
                         transport=transport)
    assert calls == []  # nothing was sent
    monkeypatch.setenv("OPENAI_API_KEY", "fake-test-key")
    _, down = recorder(httpx.Response(429))
    with pytest.raises(WebSearchError, match="429"):
        await web_search("RSV vaccine for older adults", SITES, settings=settings("openai"), transport=down)


async def test_searxng_asks_each_site_and_takes_them_in_turns(settings):
    def answer(request: httpx.Request):
        site = request.url.params["q"].rsplit("site:", 1)[1]
        assert request.url.path == "/search" and request.url.params["format"] == "json"
        return {"results": [{"url": f"https://{site}/{i}", "title": f"{site} {i}", "content": f"text {i}"}
                            for i in range(3)]}
    calls, transport = recorder(answer)
    found = await web_search("salt and blood pressure", SITES, settings=settings("searxng"),
                             transport=transport)
    assert sorted(r.url.params["q"] for r in calls) == [
        "salt and blood pressure site:medlineplus.gov", "salt and blood pressure site:nih.gov"]
    assert [c.source for c in found] == [
        "https://medlineplus.gov/0", "https://nih.gov/0", "https://medlineplus.gov/1"]


async def test_searxng_keeps_the_sites_that_answered(settings):
    def answer(request: httpx.Request):
        if request.url.params["q"].endswith("site:nih.gov"):
            return httpx.Response(500)
        return {"results": [{"url": "https://medlineplus.gov/a", "title": "A", "content": "text"}]}
    _, transport = recorder(answer)
    found = await web_search("salt and blood pressure", SITES, settings=settings("searxng"),
                             transport=transport)
    assert [c.source for c in found] == ["https://medlineplus.gov/a"]
    _, down = recorder(httpx.Response(503))
    with pytest.raises(WebSearchError):
        await web_search("salt and pepper", SITES, settings=settings("searxng"), transport=down)


async def test_searxng_engines_one_query_and_only_their_results(settings):
    """With engines for the course type: one query to those engines, no site: queries; results of other
    engines (SearXNG falls back to its default engines for an unknown name) are dropped."""
    def answer(request: httpx.Request):
        assert request.url.params["engines"] == "pubmed,semantic scholar"
        return {"results": [
            {"url": "https://pubmed.ncbi.nlm.nih.gov/1", "title": "P", "content": "abstract",
             "engine": "pubmed"},
            {"url": "https://nih.gov/scraped", "title": "G", "content": "scraped", "engine": "google"},
            {"url": "http://arxiv.org/abs/2", "title": "A", "content": "preprint",
             "engine": "semantic scholar"},
        ]}
    calls, transport = recorder(answer)
    found = await web_search("salt and blood pressure", [*SITES, "arxiv.org"],
                             engines=["pubmed", "semantic scholar"], settings=settings("searxng"),
                             transport=transport)
    assert [r.url.params["q"] for r in calls] == ["salt and blood pressure"]
    assert [c.source for c in found] == ["https://pubmed.ncbi.nlm.nih.gov/1", "https://arxiv.org/abs/2"]


async def test_searxng_engines_all_down_is_a_failed_search(settings):
    """SearXNG answers 200 with `unresponsive_engines` when PubMed is suspended after a 429."""
    down = {"results": [], "unresponsive_engines": [["pubmed", "Suspended: too many requests"],
                                                    ["semantic scholar", "parsing error"]]}
    _, transport = recorder(down)
    with pytest.raises(WebSearchError, match="every engine failed"):
        await web_search("salt and blood pressure", SITES, engines=["pubmed", "semantic scholar"],
                         settings=settings("searxng"), transport=transport)
    one_down = {"results": [], "unresponsive_engines": [["pubmed", "Suspended: too many requests"]]}
    _, transport = recorder(one_down)  # the other engine answered and found nothing: an empty search
    assert await web_search("salt and pepper", SITES, engines=["pubmed", "semantic scholar"],
                            settings=settings("searxng"), transport=transport) == []


async def test_results_are_cached_per_query(settings):
    calls, transport = recorder({"results": [{**RESULTS[0], "engine": "pubmed"}]})
    cfg = settings("searxng")
    for query in ("salt and blood pressure", "Salt and blood pressure ", "another question here"):
        await web_search(query, SITES, engines=["pubmed"], settings=cfg, transport=transport)
    assert len(calls) == 2  # the second query is the first one again
    off = settings("searxng", cache_hours=0)  # no cache read either, though the entry is still there
    for _ in range(2):
        await web_search("salt and blood pressure", SITES, engines=["pubmed"], settings=off,
                         transport=transport)
    assert len(calls) == 4


async def test_the_cache_key_holds_the_settings_that_change_results(settings):
    calls, transport = recorder({"results": [{**RESULTS[0], "engine": "pubmed"}]})
    for extra in ({}, {"max_results": 1}, {"max_chars": 300}, {"searxng_url": "http://searxng-2:8080"}):
        await web_search("salt and blood pressure", SITES, engines=["pubmed"],
                         settings=settings("searxng", **extra), transport=transport)
    assert len(calls) == 4


async def test_failures_and_empty_answers_are_not_cached(settings):
    calls, transport = recorder({"results": []})
    cfg = settings("searxng")
    for _ in range(2):
        assert await web_search("salt and blood pressure", SITES, engines=["pubmed"], settings=cfg,
                                transport=transport) == []
    assert len(calls) == 2


def test_engines_per_course_type(settings):
    cfg = settings("searxng", searxng_engines={"ece": ["arxiv"], "general": ["wikipedia"]})
    assert engines_for("ece", cfg) == ["arxiv"]
    assert engines_for("custom_type", cfg) == engines_for(None, cfg) == ["wikipedia"]


async def test_the_api_ignores_engines(settings, monkeypatch):
    monkeypatch.setenv("TAVILY_API_KEY", "fake-test-key")
    calls, transport = recorder({"results": [RESULTS[0]]})
    await web_search("salt and blood pressure", SITES, engines=["pubmed"], settings=settings("api"),
                     transport=transport)
    assert "engines" not in json.loads(calls[0].content)


def test_web_sources_are_named_by_their_page_title():
    web = Chunk(text="t", source="https://nih.gov/a", topic="web", score=0,
                metadata={"web": True, "title": "A page"})
    course = Chunk(text="t", source="lecture_notes.pdf", topic="x", score=0, metadata={"page": 2})
    titles = [p.english_title() for p in source_positions([web, course])]
    assert titles == ["A page", "lecture notes (page 2)"]


# ------------------------------------------------------------------ the pipeline step
ORIGINAL = "I am Ann Lee, student 300418277. What changed in the 2026 salt guideline?"
SANITIZED_GENERAL = "What changed in the 2026 salt guideline?"


MIXED = f"I am <PERSON_1>, student <STUDENT_ID_1>. {SANITIZED_GENERAL}"


def make_ctx(target="cloud", fresh=True, sanitized=MIXED):
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question=ORIGINAL))
    ctx.pii = PIIResult(sanitized_text=sanitized, cloud_safe=True)
    ctx.target = target
    ctx.semantic_analysis = SemanticAnalysis(method="lr", requires_fresh_evidence=fresh, reliable=True)
    ctx.passages = [Chunk(text="course", source="notes.pdf", topic="t", score=1)]
    return ctx


@pytest.fixture
def step(use_config, monkeypatch):
    queries: list[str] = []

    async def fake_search(query, allowlist, *, engines=None, settings=None, transport=None):
        queries.append(query)
        return [Chunk(text="web", source="https://nih.gov/a", topic="web", score=0, metadata={"web": True})]

    monkeypatch.setattr(step_module, "web_search", fake_search)

    def _make(provider="searxng"):
        return WebSearchStep(build_services(use_config({"websearch": {"provider": provider}}))), queries
    return _make


async def test_the_step_searches_with_search_query_only(step):
    run, queries = step()
    ctx = await run.run(make_ctx())
    assert queries == [search_query(make_ctx())] == [SANITIZED_GENERAL]  # never the original question
    assert not any("Ann" in q or "300418277" in q for q in queries)
    assert [c.source for c in ctx.passages] == ["notes.pdf", "https://nih.gov/a"]


@pytest.mark.parametrize("ctx", [
    make_ctx(target="local"),  # local answers never search
    make_ctx(fresh=False),  # the router found no need for recent information
    make_ctx(sanitized="My grade is <GRADE_1>, can I retake it?"),  # nothing general left: no query
])
async def test_the_step_does_not_search(step, ctx):
    run, queries = step()
    out = await run.run(ctx)
    assert queries == [] and [c.source for c in out.passages] == ["notes.pdf"]


async def test_the_step_does_nothing_when_search_is_off(step):
    run, queries = step("off")
    assert [c.source for c in (await run.run(make_ctx())).passages] == ["notes.pdf"] and queries == []


async def test_a_failed_search_keeps_the_course_passages(use_config, monkeypatch):
    async def failing(*args, **kwargs):
        raise WebSearchError("down")
    monkeypatch.setattr(step_module, "web_search", failing)
    run = WebSearchStep(build_services(use_config({"websearch": {"provider": "api"}})))
    assert [c.source for c in (await run.run(make_ctx())).passages] == ["notes.pdf"]


HEALTH_Q = "I have asthma since last week. What triggers asthma attacks in cold air?"


@pytest.mark.parametrize(("reply", "searched"), [
    ('{"personal_health": true}', False),  # the local model flags it: nothing is sent
    ('{"personal_health": false}', True),
    ("not json", False),  # a failed check fails closed
])
async def test_the_local_health_check_runs_before_anything_is_sent(use_config, monkeypatch, reply, searched):
    queries: list[str] = []

    async def fake_search(query, allowlist, *, engines=None, settings=None, transport=None):
        queries.append(query)
        return []
    monkeypatch.setattr(step_module, "web_search", fake_search)
    privacy = {"llm_check": True, "health_detail_policy": "local_only"}
    services = build_services(use_config({"websearch": {"provider": "searxng"}, "privacy": privacy}))
    services.understand_llm = FakeLLMClient(reply)
    ctx = RequestContext(request_id="r", request=AskRequest(student_id="s", topic="t", question=HEALTH_Q))
    ctx.pii = PIIResult(sanitized_text=HEALTH_Q, cloud_safe=True)
    ctx.target = "cloud"
    ctx.semantic_analysis = SemanticAnalysis(method="lr", requires_fresh_evidence=True, reliable=True)
    out = await WebSearchStep(services).run(ctx)
    assert bool(queries) is searched and out.pii.cloud_safe is searched
    assert out.pii.llm_checked and len(services.understand_llm.calls) == 1
    # the generate step reuses this answer instead of asking the local model again
    assert await llm_flags_health(out, services) is False and len(services.understand_llm.calls) == 1


def test_every_course_type_has_its_own_web_sources_in_the_shipped_config():
    """S16 review: a new privacy profile (course type) without its own list would fall back to Wikipedia."""
    from pathlib import Path

    import yaml

    from app.privacy.profiles import profile_names

    config = Path(__file__).resolve().parents[2] / "config.yaml"
    shipped = yaml.safe_load(config.read_text(encoding="utf-8"))
    search = shipped["websearch"]
    for name in profile_names():
        assert name in search["allowlist"] and name in search["searxng_engines"], name
