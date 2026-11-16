"""Web search for cloud answers that need recent information (task T13; guide 4.5 step 6a, rule 5).

The query always comes from `app.privacy.profiles.search_query()`; this package never sees the original
question. Chosen when the stack is deployed (`websearch.provider`, docs/WEB_SEARCH.md):
- `off`: no search, `web_search` returns no passages;
- `api`: a hosted search API with the Tavily request format (`WEBSEARCH_API_KEY`); the allow-list is sent as
  `include_domains`;
- `searxng`: the self-hosted SearXNG of the `searxng` Compose profile (JSON API), one `site:` query per
  allowed site.

Every result is checked again here: an https URL on an allowed site (or its subdomain), cleaned to plain text,
cut to `max_chars`, at most `max_results`, no duplicate URLs. Outbound requests go through the model gateway's
SSRF checks (`app.llm.ssrf`): the API must be a public address, SearXNG a deployment-internal one.
"""
import asyncio
import re
from html import unescape
from itertools import chain, zip_longest
from urllib.parse import urlparse

import httpx

from app.core.config import Settings, get_settings
from app.core.schemas import Chunk


class WebSearchError(RuntimeError):
    """The search service failed or answered something unusable (the message is safe to log)."""


def allowed_site(url: str, allowlist: list[str]) -> bool:
    """An https URL on one of the sites or its subdomains ("nih.gov" allows "www.ncbi.nlm.nih.gov")."""
    parsed = urlparse(url)
    host = (parsed.hostname or "").lower().rstrip(".")
    if parsed.scheme != "https" or not host:
        return False
    sites = (s.lower().strip(".") for s in allowlist)
    return any(host == site or host.endswith("." + site) for site in sites)


def clean(text: str, max_chars: int) -> str:
    """Plain text: tags, scripts and repeated whitespace removed, cut at a word before `max_chars`."""
    text = re.sub(r"(?is)<(script|style)[^>]*>.*?</\1>", " ", text or "")
    text = unescape(re.sub(r"(?s)<[^>]+>", " ", text))
    text = re.sub(r"\s+", " ", text).strip()
    if len(text) > max_chars:
        text = text[:max_chars].rsplit(" ", 1)[0] + " …"
    return text


def _passages(raw: list[dict], allowlist: list[str], cfg) -> list[Chunk]:
    seen: set[str] = set()
    out: list[Chunk] = []
    for r in raw:
        url = str(r.get("url") or "").strip()
        text = clean(str(r.get("content") or ""), cfg.max_chars)
        if not text or url in seen or not allowed_site(url, allowlist):
            continue
        seen.add(url)
        title = clean(str(r.get("title") or ""), 200) or urlparse(url).hostname or url
        score = r.get("score")
        out.append(Chunk(text=text, source=url, topic="web",
                         score=float(score) if isinstance(score, int | float) else 0.0,
                         metadata={"web": True, "title": title, "url": url}))
        if len(out) >= cfg.max_results:
            break
    return out


def _check_url(url: str, trust: str) -> None:
    from app.llm.ssrf import check_endpoint_url

    # UnsafeEndpoint: a link-local or system address, or (for the API) a private one
    check_endpoint_url(url, trust=trust)


def _client(url: str, trust: str, timeout: float, transport) -> httpx.AsyncClient:
    from app.llm.ssrf import PinnedTransport

    _check_url(url, trust)
    return httpx.AsyncClient(transport=transport or PinnedTransport(trust=trust), timeout=timeout)


async def _search_api(query: str, allowlist: list[str], settings: Settings, transport) -> list[dict]:
    cfg = settings.websearch
    if settings.websearch_api_key is None:
        raise WebSearchError("websearch.provider is api but WEBSEARCH_API_KEY is not set")
    body = {"query": query, "max_results": cfg.max_results * 2, "include_domains": allowlist,
            "search_depth": "basic", "include_answer": False}
    headers = {"Authorization": f"Bearer {settings.websearch_api_key.get_secret_value()}"}
    async with _client(cfg.api_url, "external", cfg.timeout_s, transport) as client:
        r = await client.post(cfg.api_url, json=body, headers=headers)
    if r.status_code != 200:
        raise WebSearchError(f"search API answered {r.status_code}")
    return list(r.json().get("results") or [])


async def _search_searxng(query: str, allowlist: list[str], settings: Settings, transport) -> list[dict]:
    cfg = settings.websearch
    url = cfg.searxng_url.rstrip("/") + "/search"
    async with _client(cfg.searxng_url, "trusted_local", cfg.timeout_s, transport) as client:
        async def one(site: str) -> list[dict]:
            r = await client.get(url, params={"q": f"{query} site:{site}", "format": "json", "safesearch": 1})
            if r.status_code != 200:
                raise WebSearchError(f"SearXNG answered {r.status_code}")
            return list(r.json().get("results") or [])

        found = await asyncio.gather(*(one(site) for site in allowlist), return_exceptions=True)
    lists = [f for f in found if not isinstance(f, BaseException)]
    if not lists:
        raise WebSearchError("SearXNG failed for every site")
    # take the sites in turns, so one site cannot fill every slot
    return [r for r in chain.from_iterable(zip_longest(*lists)) if r is not None]


async def web_search(query: str, allowlist: list[str], *, settings: Settings | None = None,
                     transport: httpx.AsyncBaseTransport | None = None) -> list[Chunk]:
    """Cleaned passages from allowed sites for `query` (from `search_query()`); [] when search is off."""
    settings = settings or get_settings()
    provider = settings.websearch.provider
    if provider == "off" or not query or not allowlist:
        return []
    search = _search_api if provider == "api" else _search_searxng
    return _passages(await search(query, allowlist, settings, transport), allowlist, settings.websearch)


def allowlist_for(course_type: str | None, settings: Settings | None = None) -> list[str]:
    """The sites searched for a course type (`websearch.allowlist`; `general` when the type has none)."""
    lists = (settings or get_settings()).websearch.allowlist
    return list(lists.get(course_type or "general") or lists.get("general") or [])
