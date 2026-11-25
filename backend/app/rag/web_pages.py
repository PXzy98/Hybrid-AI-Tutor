"""Web pages as course material (v5 V7): the only place the app fetches a page an instructor names.

`fetch_page(url)` is the single outbound helper for it:
- https only, no credentials in the address, a public address only: the host is resolved once per request
  and every address is checked (`app.llm.ssrf.PinnedTransport`, trust "external": no loopback, private,
  link-local, cloud metadata or the system's own services), so a name cannot be checked as public and then
  connected as private;
- redirects are followed by hand, at most MAX_REDIRECTS, and every target is checked the same way;
- at most MAX_BYTES of body and TIMEOUT_S seconds for the whole fetch, redirects included (a server that
  keeps sending small pieces is cut off); only HTML, plain text or Markdown.

The page becomes a Markdown material (`web-<host>-<path>-<digest>.md`) whose first line records the address,
so it can be fetched again. Like every upload it is scanned (`index_jobs.check_upload`) before it is stored.
"""
import asyncio
import codecs
import hashlib
import re
from dataclasses import dataclass
from html.parser import HTMLParser
from urllib.parse import urljoin, urlparse

import httpx

from app.llm.ssrf import PinnedTransport, UnsafeEndpoint, _system_addresses, check_endpoint_url

MAX_BYTES = 2_000_000
TIMEOUT_S = 15.0
MAX_REDIRECTS = 3
MAX_FIRST_LINE = 2200  # bytes read to find the source comment: an address is at most 2000 characters
TYPES = ("text/html", "application/xhtml+xml", "text/plain", "text/markdown")
SOURCE_PREFIX = "<!-- source: "  # the first line of a web material: <!-- source: https://... -->
# sites such as Wikipedia refuse an agent without a way to reach its operator (HTTP 403)
USER_AGENT = "ScholarMind-AI-course-material-fetcher/1.0 (+https://github.com/PXzy98/Hybrid-AI-Tutor)"


class PageRefused(ValueError):
    """The address or the page cannot be used (the message is safe to show)."""


@dataclass(frozen=True)
class Page:
    url: str  # the address after redirects
    title: str
    text: str


class _Html(HTMLParser):
    """Visible text with paragraph breaks; the <title>; no scripts, styles or navigation."""

    BLOCK = {"p", "div", "br", "li", "ul", "ol", "blockquote", "h1", "h2", "h3", "h4", "h5", "h6", "tr",
             "section", "article", "pre", "table"}
    CELLS = {"td", "th"}
    HIDDEN = {"script", "style", "nav", "header", "footer", "noscript", "svg", "form"}

    def __init__(self) -> None:
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.title = ""
        self._hidden = 0
        self._in_title = False
        self._title_done = False

    def handle_starttag(self, tag, attrs):
        if tag in self.HIDDEN:
            self._hidden += 1
        elif tag == "title":
            self._in_title = not self._hidden and not self._title_done  # the first one outside hidden content
        elif tag in self.CELLS and not self._hidden:
            self.parts.append(" ")
        elif tag in self.BLOCK:
            self.parts.append("\n\n" if tag != "br" else "\n")
        if tag in {"h1", "h2", "h3"} and not self._hidden:
            self.parts.append("#" * int(tag[1]) + " ")

    def handle_endtag(self, tag):
        if tag in self.HIDDEN and self._hidden:
            self._hidden -= 1
        elif tag == "title":
            if self._in_title:
                self._title_done = True
            self._in_title = False
        elif tag in self.BLOCK:
            self.parts.append("\n\n")

    def handle_data(self, data):
        if self._in_title:
            self.title += data
        elif not self._hidden:
            self.parts.append(data)


def is_https_url(url: str) -> bool:
    """An https address with a host and no credentials (what `check_url` accepts, no DNS check)."""
    try:
        parsed = urlparse((url or "").strip())
        return parsed.scheme == "https" and bool(parsed.hostname) and not (parsed.username or parsed.password)
    except ValueError:
        return False


def check_url(url: str, resolve=None) -> str:
    """The address, or PageRefused: https, no credentials, a public host (checked again at connect time)."""
    parsed = urlparse((url or "").strip())
    if parsed.scheme != "https" or not parsed.hostname:
        raise PageRefused("use an https address, e.g. https://example.org/page")
    if parsed.username or parsed.password:
        raise PageRefused("do not put credentials in the address")
    try:
        check_endpoint_url(url.strip(), trust="external", **({"resolve": resolve} if resolve else {}))
    except UnsafeEndpoint as e:
        raise PageRefused(str(e)) from None
    return url.strip()


def to_text(body: str, content_type: str) -> tuple[str, str]:
    """(title, text) of a page body."""
    if content_type.startswith(("text/plain", "text/markdown")):
        first = next((line.strip("# ").strip() for line in body.splitlines() if line.strip()), "")
        return first[:180], body
    parser = _Html()
    parser.feed(body)
    parser.close()
    text = re.sub(r"[ \t]+", " ", "".join(parser.parts))
    text = re.sub(r"\n\s*\n\s*(\n\s*)+", "\n\n", text).strip()
    return " ".join(parser.title.split())[:180], text


async def fetch_page(url: str, *, resolve=None, inner: httpx.AsyncBaseTransport | None = None) -> Page:
    """Fetch one page under the rules of the module docstring; PageRefused otherwise. `resolve` and `inner`
    (the connection under the pinned transport) are for tests only."""
    await asyncio.to_thread(_system_addresses)  # the system's own addresses: looked up once, then cached
    try:
        async with asyncio.timeout(TIMEOUT_S):  # httpx's timeout is per network operation, this one is total
            current = await asyncio.to_thread(check_url, url, resolve)  # DNS blocks: off the event loop
            return await _fetch(current, resolve, inner)
    except TimeoutError:
        raise PageRefused("the page did not answer in time") from None


async def _fetch(current: str, resolve, inner) -> Page:
    transport = PinnedTransport(trust="external", resolve=resolve, inner=inner)
    client = httpx.AsyncClient(transport=transport, timeout=TIMEOUT_S,
                               follow_redirects=False, headers={"User-Agent": USER_AGENT,
                                                                "Accept": ", ".join(TYPES)})
    async with client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream("GET", current) as response:
                    if response.is_redirect:
                        target = response.headers.get("location", "")
                        current = await asyncio.to_thread(check_url, urljoin(current, target), resolve)
                        continue
                    if response.status_code != 200:
                        raise PageRefused(f"the page answered HTTP {response.status_code}")
                    kind = response.headers.get("content-type", "").split(";")[0].strip().lower()
                    if kind not in TYPES:
                        raise PageRefused("only HTML, plain text or Markdown pages can be added")
                    body = bytearray()
                    async for piece in response.aiter_bytes():
                        body += piece
                        if len(body) > MAX_BYTES:
                            raise PageRefused(f"the page is larger than {MAX_BYTES // 1_000_000} MB")
                    encoding = _encoding(response.charset_encoding, bytes(body[:2048]))
            except UnsafeEndpoint as e:  # the pinned transport refused the resolved address
                raise PageRefused(str(e)) from None
            except httpx.TimeoutException:
                raise PageRefused("the page did not answer in time") from None
            except httpx.HTTPError:
                raise PageRefused("the page could not be fetched") from None
            title, text = to_text(bytes(body).decode(encoding, errors="replace"), kind)
            if not text.strip():
                raise PageRefused("the page has no text")
            return Page(url=current, title=title or urlparse(current).hostname or "web page", text=text)
    raise PageRefused("too many redirects")


def _encoding(declared: str | None, head: bytes) -> str:
    """The charset of the Content-Type header, else of a <meta> tag in the first bytes, else UTF-8."""
    found = declared
    if not found:
        meta = re.search(rb"<meta[^>]+charset\s*=\s*[\"']?\s*([A-Za-z0-9_.:-]+)", head, re.IGNORECASE)
        found = meta.group(1).decode("ascii") if meta else None
    try:
        return codecs.lookup(found).name if found else "utf-8"
    except LookupError:
        return "utf-8"


def material_name(url: str) -> str:
    """`web-<host>-<path>-<digest>.md`, safe as a material file name. The digest of the whole address keeps
    pages apart that differ only in the query, in case or in punctuation, or after the cut."""
    parsed = urlparse(url)
    slug = re.sub(r"[^A-Za-z0-9]+", "-", f"{parsed.hostname}{parsed.path}").strip("-").lower()
    digest = hashlib.sha256(url.encode("utf-8")).hexdigest()[:10]
    return f"web-{slug[:80] or 'page'}-{digest}.md"


def material_text(page: Page) -> str:
    """The Markdown stored as the material: the address on the first line, then the title and the text."""
    return f"{SOURCE_PREFIX}{page.url} -->\n# {page.title}\n\nSource: {page.url}\n\n{page.text}\n"


def source_url(first_line: str) -> str | None:
    """The address recorded on the first line of a web material, or None (also when it is not an https
    address: the first line of an uploaded file is not trusted)."""
    line = first_line.strip()
    if line.startswith(SOURCE_PREFIX) and line.endswith("-->"):
        url = line[len(SOURCE_PREFIX):-3].strip()
        return url if is_https_url(url) else None
    return None
