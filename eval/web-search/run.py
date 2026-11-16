"""T13 / G1-106: web search compared on the four subjects of the demo courses (performance, accuracy, cost).

Arms (docs/WEB_SEARCH.md; plan: notes of 2026-11-16):
- A  no search: the cloud model answers from the prompt alone;
- B  SearXNG with the course type's API-backed engines (`provider: searxng`, app.websearch);
- C  a hosted search API in the Tavily format (`provider: api`, app.websearch);
- D  OpenAI's own `web_search` tool with the same allow-list (domain filter), answer by the same model;
- DL the same as D with the low-cost model.
A, B and C build the prompt with the app's `render_cloud`: the web passages take the place of the course
passages (no course retrieval here: the fresh questions are not in the course material). Every arm searches
every question, also the control questions that need no recent information, to see whether search hurts.

A judge of another family (Claude Sonnet through OpenRouter) grades each answer against the reference answer
(correct / partial / wrong / refused) and, for B and C, whether the answer is supported by the passages; then
compares B with C and C with D pairwise, once in each order (a win counts only when both orders agree).
The privacy part runs the real privacy filter and `search_query()` on fictional questions with personal data
and records what a search request would carry (through a mock transport: nothing is sent).

All questions are fictional (questions.jsonl). Keys come from the environment or the repository's .env:
OPENAI_API_KEY, TAVILY_KEY (or WEBSEARCH_API_KEY), OPENROUTER_API_KEY; SearXNG from --searxng-url.
Answers are cached in <out>/runs.jsonl, judgements in <out>/judge.jsonl: a rerun only asks what is missing.

    .venv\\Scripts\\python eval\\web-search\\run.py --searxng-url http://<host>:<port> --out <dir>
    .venv\\Scripts\\python eval\\web-search\\run.py --smoke --out <dir>      # fakes only, no network (CI)
"""
import argparse
import asyncio
import json
import math
import os
import re
import statistics
import sys
import time
from pathlib import Path
from urllib.parse import urlparse

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

ANSWER_MODEL = "gpt-6.1-terra"
LOW_COST_MODEL = "gpt-6-luna"
JUDGE = "anthropic/claude-sonnet-5.5"
OPENAI_URL = "https://api.openai.com/v1/responses"
OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
# USD per million tokens (input, output) and per call, from the official price pages on 2026-11-16
PRICES = {"gpt-6.1-terra": (1.00, 5.00), "gpt-6-luna": (0.10, 0.50)}
OPENAI_SEARCH_CALL = 0.010
TAVILY_CALL = 0.008  # pay as you go; the first 1,000 a month are free
ARMS = ("A", "B", "C", "D", "DL")
LABELS = {"A": "A no search", "B": "B SearXNG", "C": "C Tavily", "D": f"D OpenAI search ({ANSWER_MODEL})",
          "DL": f"D OpenAI search ({LOW_COST_MODEL})"}
SUBJECTS = {"medical": "Medical science", "life": "Life science", "ece": "ECE", "cs": "Computer science"}
TOPIC = {"medical": "pharmacology_and_pathology", "life": "genetics_and_biology",
         "ece": "circuits_and_signals",
         "cs": "algorithms_and_programming"}
VERDICTS = ("correct", "partial", "wrong", "refused")

GRADE_SYSTEM = (
    "You grade a tutor's answer to a student's question against a reference answer that was checked on the "
    "web. Decide whether the answer states the reference answer's key facts: correct (all key facts, nothing "
    "contradicting them), partial (some key facts, or correct but vague), wrong (contradicts them or misses "
    "them), refused (says it cannot answer or does not know). Ignore style and length. "
    "If passages are given, "
    'also say whether the answer\'s main claims are supported by them. Reply with JSON only: {"verdict": '
    '"correct" | "partial" | "wrong" | "refused", "supported": "yes" | "no" | "na", '
    '"reason": "<one sentence>"}.')
PAIR_SYSTEM = (
    "You compare two answers to a student's question, given a reference answer checked on the web. Judge "
    "correctness against the reference first, then completeness, then clarity. Reply with JSON only: "
    '{"winner": "A" | "B" | "tie", "reason": "<one sentence>"}.')


# ------------------------------------------------------------------ data
def load_env(path: Path | None = None) -> dict[str, str]:
    env = dict(os.environ)
    path = path or ROOT / ".env"
    if path.exists():
        for line in path.read_text(encoding="utf-8").splitlines():
            if "=" in line and not line.lstrip().startswith("#"):
                k, v = line.split("=", 1)
                env.setdefault(k.strip(), v.strip().strip('"').strip("'").strip("`"))
    return env


def load_jsonl(path: Path) -> list[dict]:
    if not path.exists():
        return []
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def append_jsonl(path: Path, row: dict) -> None:
    with path.open("a", encoding="utf-8") as f:
        f.write(json.dumps(row, ensure_ascii=False) + "\n")


def host(url: str) -> str:
    return (urlparse(url).hostname or "").lower().removeprefix("www.")


def page_key(url: str) -> tuple:
    """The same paper or page under its different addresses: a PubMed record by PMID
    (pubmed.ncbi.nlm.nih.gov/N
    and www.ncbi.nlm.nih.gov/pubmed/N), an arXiv paper by its id without version (abs or pdf)."""
    h, path = host(url), urlparse(url).path.rstrip("/").lower()
    m = re.search(r"(?:^|/)pubmed/(\d+)$", path) if h.endswith("ncbi.nlm.nih.gov") else None
    if h == "pubmed.ncbi.nlm.nih.gov" and re.fullmatch(r"/\d+", path):
        return ("pubmed", path[1:])
    if m:
        return ("pubmed", m.group(1))
    m = re.fullmatch(r"/(?:abs|pdf)/(\d{4}\.\d{4,5})(?:v\d+)?(?:\.pdf)?", path) if h == "arxiv.org" else None
    if m:
        return ("arxiv", m.group(1))
    return (h, path)


def same_page(a: str, b: str) -> bool:
    return bool(a and b) and page_key(a) == page_key(b)


def site(url: str) -> str:
    """The registrable domain: nih.gov for www.ncbi.nlm.nih.gov, ebi.ac.uk for www.ebi.ac.uk."""
    parts = host(url).split(".")
    n = 3 if len(parts) >= 3 and parts[-2] in ("ac", "co", "gov", "org") and len(parts[-1]) == 2 else 2
    return ".".join(parts[-n:])


def reference_hit(ref: str, urls: list[str]) -> dict:
    """Whether the search found the reference page itself, or another page on its site."""
    if not ref:
        return {"page": None, "site": None}
    return {"page": any(same_page(ref, u) for u in urls),
            "site": any(site(u) == site(ref) for u in urls if host(u))}


# ------------------------------------------------------------------ model calls
class OpenAI:
    def __init__(self, key: str, client: httpx.AsyncClient) -> None:
        self.h = {"Authorization": f"Bearer {key}"}
        self.client = client

    async def respond(self, model: str, messages: list[dict], *, allowlist: list[str] | None = None) -> dict:
        body = {"model": model, "input": messages, "max_output_tokens": 900, "reasoning": {"effort": "none"}}
        if allowlist is not None:
            body["tools"] = [{"type": "web_search", "filters": {"allowed_domains": allowlist}}]
            body["include"] = ["web_search_call.action.sources"]
        t0 = time.perf_counter()
        r = await self.client.post(OPENAI_URL, headers=self.h, json=body, timeout=180)
        seconds = time.perf_counter() - t0
        if r.status_code != 200:
            raise RuntimeError(f"OpenAI answered {r.status_code}: {r.text[:200]}")
        d = r.json()
        text, cited, sources, searches = "", [], [], 0
        for item in d.get("output", []):
            if item.get("type") == "web_search_call":
                searches += 1
                for s in ((item.get("action") or {}).get("sources") or []):
                    if s.get("url"):
                        sources.append(s["url"])
            for c in item.get("content") or []:
                if c.get("type") == "output_text":
                    text += c.get("text", "")
                for a in c.get("annotations") or []:
                    if a.get("type") == "url_citation" and a.get("url") not in cited:
                        cited.append(a["url"])
        u = d.get("usage") or {}
        tin, tout = u.get("input_tokens", 0), u.get("output_tokens", 0)
        pin, pout = PRICES[model]
        cost = tin * pin / 1e6 + tout * pout / 1e6 + searches * OPENAI_SEARCH_CALL
        return {"text": text.strip(), "seconds": seconds, "input_tokens": tin, "output_tokens": tout,
                "searches": searches, "cited": cited, "sources": sources, "cost": cost,
                "status": d.get("status")}


class Judge:
    def __init__(self, key: str, client: httpx.AsyncClient) -> None:
        self.h = {"Authorization": f"Bearer {key}"}
        self.client = client

    async def ask(self, system: str, user: str) -> dict:
        body = {"model": JUDGE, "temperature": 0, "max_tokens": 300, "usage": {"include": True},
                "messages": [{"role": "system", "content": system}, {"role": "user", "content": user}]}
        for attempt in range(3):
            r = await self.client.post(OPENROUTER_URL, headers=self.h, json=body, timeout=120)
            if r.status_code == 200:
                break
            await asyncio.sleep(2 * (attempt + 1))
        else:
            raise RuntimeError(f"OpenRouter answered {r.status_code}")
        d = r.json()
        return {"text": d["choices"][0]["message"]["content"] or "",
                "cost": (d.get("usage") or {}).get("cost")}


def parse_json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        return {}


# ------------------------------------------------------------------ arms
def settings_for(provider: str, a, env: dict):
    from pydantic import SecretStr

    from app.core.config import Settings

    s = Settings()
    ws = s.websearch.model_copy(update={"provider": provider, "cache_hours": 0, "timeout_s": a.search_timeout,
                                        **({"searxng_url": a.searxng_url} if a.searxng_url else {})})
    key = env.get("WEBSEARCH_API_KEY") or env.get("TAVILY_KEY")
    return s.model_copy(update={"websearch": ws, **({"websearch_api_key": SecretStr(key)} if key else {})})


def prompt(q: dict, passages: list[str]) -> list[dict]:
    from app.core.schemas import CloudRequest, LearnerContext
    from app.prompts import render_cloud

    req = CloudRequest(sanitized_question=q["question"], topic=TOPIC[q["subject"]], passages=passages,
                       labels=LearnerContext().to_cloud_labels())
    return render_cloud(req)


async def run_arm(arm: str, q: dict, api: OpenAI, settings: dict, search=None) -> dict:
    """One question in one arm. `search(query, allowlist, engines, settings)` is app.websearch.web_search."""
    from app.websearch import allowlist_for, engines_for

    allow = allowlist_for(q["course_type"], settings.get("B") or settings.get("C"))
    row = {"arm": arm, "id": q["id"], "subject": q["subject"], "needs_fresh": q["needs_fresh"]}
    try:
        if arm in ("D", "DL"):
            out = await api.respond(ANSWER_MODEL if arm == "D" else LOW_COST_MODEL, prompt(q, []),
                                    allowlist=allow)
            urls = list(dict.fromkeys(out["cited"] + out["sources"]))
            row.update(answer=out["text"], urls=urls, cited=out["cited"], passages=[], search_s=None,
                       total_s=out["seconds"], input_tokens=out["input_tokens"],
                       output_tokens=out["output_tokens"], searches=out["searches"], cost=out["cost"],
                       search_cost=out["searches"] * OPENAI_SEARCH_CALL)
            return row
        found, search_s, search_error = [], None, None
        if arm in ("B", "C"):
            s = settings[arm]
            t0 = time.perf_counter()
            try:
                found = await search(q["question"], allow, engines=engines_for(q["course_type"], s),
                                     settings=s)
            except Exception as e:  # the app skips a failed search; so does the evaluation
                search_error = f"{type(e).__name__}: {e}"[:200]
            search_s = time.perf_counter() - t0
        passages = [c.text for c in found]
        out = await api.respond(ANSWER_MODEL, prompt(q, passages))
        search_cost = TAVILY_CALL if arm == "C" else 0.0
        row.update(answer=out["text"], urls=[c.source for c in found], cited=[], passages=passages,
                   search_s=search_s, search_error=search_error, total_s=(search_s or 0) + out["seconds"],
                   input_tokens=out["input_tokens"], output_tokens=out["output_tokens"],
                   searches=int(arm != "A"),
                   cost=out["cost"] + search_cost, search_cost=search_cost)
    except Exception as e:
        row.update(error=f"{type(e).__name__}: {e}"[:300])
    return row


# ------------------------------------------------------------------ judging
def grade_prompt(q: dict, row: dict) -> str:
    parts = [f"Question: {q['question']}", f"Reference answer: {q['reference_answer']}"]
    if row.get("passages"):
        parts.append("Passages the tutor was given:\n" + "\n\n".join(
            f"[{i}] {p}" for i, p in enumerate(row["passages"], 1)))
    parts.append(f"Tutor's answer:\n{row.get('answer') or '(no answer)'}")
    return "\n\n".join(parts)


def pair_prompt(q: dict, first: str, second: str) -> str:
    return (f"Question: {q['question']}\n\nReference answer: {q['reference_answer']}\n\n"
            f"Answer A:\n{first or '(no answer)'}\n\nAnswer B:\n{second or '(no answer)'}")


async def judge_all(questions, runs, judge: Judge, judged: dict, path: Path, pairs, limit: asyncio.Semaphore):
    by = {(r["arm"], r["id"]): r for r in runs}
    tasks = []

    async def grade(q, row):
        key = f"grade|{row['arm']}|{q['id']}"
        if key in judged:
            return
        async with limit:
            out = await judge.ask(GRADE_SYSTEM, grade_prompt(q, row))
        v = parse_json(out["text"])
        rec = {"key": key, "verdict": v.get("verdict") if v.get("verdict") in VERDICTS else "unparsed",
               "supported": v.get("supported"), "reason": v.get("reason"), "cost": out["cost"]}
        judged[key] = rec
        append_jsonl(path, rec)

    async def pair(q, x, y, order):
        key = f"pair|{x}|{y}|{order}|{q['id']}"
        if key in judged:
            return
        first, second = (by[(x, q["id"])], by[(y, q["id"])]) if order == "xy" else \
            (by[(y, q["id"])], by[(x, q["id"])])
        async with limit:
            out = await judge.ask(PAIR_SYSTEM, pair_prompt(q, first.get("answer"), second.get("answer")))
        w = parse_json(out["text"]).get("winner")
        winner = {"A": first["arm"], "B": second["arm"], "tie": "tie"}.get(w, "unparsed")
        rec = {"key": key, "winner": winner, "cost": out["cost"]}
        judged[key] = rec
        append_jsonl(path, rec)

    for q in questions:
        for arm in ARMS:
            row = by.get((arm, q["id"]))
            if row and "error" not in row:
                tasks.append(grade(q, row))
        if q["needs_fresh"]:
            for x, y in pairs:
                if (x, q["id"]) in by and (y, q["id"]) in by:
                    tasks += [pair(q, x, y, "xy"), pair(q, x, y, "yx")]
    await asyncio.gather(*tasks)


# ------------------------------------------------------------------ privacy
async def privacy_check(items: list[dict], settings) -> list[dict]:
    """The real privacy filter and search_query(); the would-be request is caught by a mock transport."""
    from app.core.schemas import AskRequest, PIIResult, RequestContext
    from app.privacy.analyzer import PIIAnalyzer
    from app.privacy.anonymizer import anonymize
    from app.privacy.profiles import search_query
    from app.websearch import allowlist_for, web_search

    analyzer = PIIAnalyzer(settings.privacy)
    local_only = set(settings.privacy.local_only_types)
    out = []
    for item in items:
        findings = analyzer.analyze(item["question"])
        sanitized, entities, _ = anonymize(item["question"], findings)
        ctx = RequestContext(request_id="eval", request=AskRequest(student_id="eval", topic="t",
                                                                   question=item["question"]))
        ctx.pii = PIIResult(entities=entities, cloud_safe=not any(e.type in local_only for e in entities),
                            sanitized_text=sanitized)
        query = search_query(ctx)
        sent: list[str] = []

        def record(request: httpx.Request, sent=sent) -> httpx.Response:
            sent.append(str(request.url) + " " + request.content.decode("utf-8", "replace"))
            return httpx.Response(200, json={"results": []})

        if query:
            import app.websearch as ws

            real = ws._check_url
            ws._check_url = lambda url, trust: None  # nothing leaves: the mock transport answers
            try:
                await web_search(query, allowlist_for(item["course_type"], settings), settings=settings,
                                 transport=httpx.MockTransport(record))
            finally:
                ws._check_url = real
        blob = " ".join(sent).lower()
        leaked = [p for p in item["pii"] if p.lower() in blob or p.lower().replace(" ", "+") in blob]
        out.append({"id": item["id"], "searched": bool(query), "query": query, "leaked": leaked})
    return out


# ------------------------------------------------------------------ report
def pct(values: list[float], p: float) -> float | None:
    if not values:
        return None
    s = sorted(values)
    return s[min(len(s) - 1, math.ceil(p * len(s)) - 1)]


def wilson(k: int, n: int) -> tuple[float, float]:
    if n == 0:
        return (0.0, 0.0)
    z, phat = 1.96, k / n
    d = 1 + z * z / n
    c = phat + z * z / (2 * n)
    r = z * math.sqrt(phat * (1 - phat) / n + z * z / (4 * n * n))
    return ((c - r) / d, (c + r) / d)


def sign_test(wins: int, losses: int) -> float:
    n = wins + losses
    if n == 0:
        return 1.0
    k = min(wins, losses)
    p = sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n
    return min(1.0, 2 * p)


def f(v, digits=2) -> str:
    return "-" if v is None else f"{v:.{digits}f}"


def report(questions, runs, judged, privacy, pairs, searxng_repeat=None) -> str:
    qs = {q["id"]: q for q in questions}
    arms = [a for a in ARMS if any(r["arm"] == a for r in runs)]
    lines = ["# Web search comparison (T13 / G1-106)", "",
             f"{len(questions)} fictional questions ({sum(q['needs_fresh'] for q in questions)} need recent "
             f"information), four subjects; answer model `{ANSWER_MODEL}` (reasoning effort none), low-cost "
             f"`{LOW_COST_MODEL}`; judge `{JUDGE}`.", ""]

    def rows(arm, subject=None, fresh=None):
        return [r for r in runs if r["arm"] == arm and (subject is None or r["subject"] == subject)
                and (fresh is None or r["needs_fresh"] == fresh)]

    # performance
    lines += ["## Performance", "",
              "| Arm | Questions | Errors | Search failed | 0 results | Search p50 / p95 / max (s) | "
              "Total p50 / p95 (s) |", "|---|---|---|---|---|---|---|"]
    for arm in arms:
        rs = rows(arm)
        ok = [r for r in rs if "error" not in r]
        srch = [r["search_s"] for r in ok if r.get("search_s") is not None]
        tot = [r["total_s"] for r in ok]
        failed = sum(1 for r in ok if r.get("search_error"))
        empty = sum(1 for r in ok if arm != "A" and not r.get("search_error") and not r.get("urls"))
        lines.append(f"| {LABELS[arm]} | {len(rs)} | {len(rs) - len(ok)} | "
                     f"{failed if arm in 'BC' else '-'} | "
                     f"{empty if arm != 'A' else '-'} | {f(pct(srch, .5))} / {f(pct(srch, .95))} / "
                     f"{f(max(srch) if srch else None)} | {f(pct(tot, .5))} / {f(pct(tot, .95))} |")
    errors = sorted({r.get("search_error") or r.get("error") for r in runs
                     if r.get("search_error") or r.get("error")})
    if errors:
        lines += ["", "Errors seen: " + "; ".join(f"`{e[:120]}`" for e in errors[:8])]
    if searxng_repeat:
        lines += ["", searxng_repeat]

    # accuracy
    def grade(arm, qid):
        return (judged.get(f"grade|{arm}|{qid}") or {}).get("verdict")

    lines += ["", "## Accuracy: questions that need recent information", "",
              "Correct answers out of the questions (95% Wilson interval); partial in brackets.", "",
              "| Arm | " + " | ".join(SUBJECTS.values()) + " | All |", "|---|" + "---|" * (len(SUBJECTS) + 1)]
    for arm in arms:
        cells = []
        for subject in [*SUBJECTS, None]:
            ids = [r["id"] for r in rows(arm, subject, True)]
            n = len([q for q in questions
                     if q["needs_fresh"] and (subject is None or q["subject"] == subject)])
            k = sum(grade(arm, i) == "correct" for i in ids)
            part = sum(grade(arm, i) == "partial" for i in ids)
            lo, hi = wilson(k, n)
            cells.append(f"{k}/{n} ({part}) [{lo:.0%}–{hi:.0%}]")
        lines.append(f"| {LABELS[arm]} | " + " | ".join(cells) + " |")

    lines += ["", "## Control questions (no recent information needed)", "",
              "| Arm | Correct | Partial | Wrong or refused |", "|---|---|---|---|"]
    for arm in arms:
        ids = [r["id"] for r in rows(arm, None, False)]
        vs = [grade(arm, i) for i in ids]
        lines.append(f"| {LABELS[arm]} | {vs.count('correct')} | {vs.count('partial')} | "
                     f"{vs.count('wrong') + vs.count('refused')} |")

    lines += ["", "## Retrieval", "",
              "Reference page or its site among the returned URLs (fresh questions); passages "
              "that support the "
              "answer (judge); URLs outside the allow-list.", "",
              "| Arm | Reference page | Reference site | Answer supported by passages | Outside allow-list |",
              "|---|---|---|---|---|"]
    from app.websearch import allowed_site, allowlist_for
    for arm in [a for a in arms if a != "A"]:
        fr = [r for r in rows(arm, None, True) if "error" not in r]
        hits = [reference_hit(qs[r["id"]]["reference_url"], r.get("urls") or []) for r in fr]
        sup = [(judged.get(f"grade|{arm}|{r['id']}") or {}).get("supported") for r in rows(arm)
               if r.get("passages")]
        outside = sum(1 for r in rows(arm) for u in (r.get("urls") or [])
                      if not allowed_site(u.replace("http://", "https://", 1),
                                          allowlist_for(qs[r["id"]]["course_type"])))
        lines.append(f"| {LABELS[arm]} | {sum(h['page'] for h in hits)}/{len(hits)} | "
                     f"{sum(h['site'] for h in hits)}/{len(hits)} | "
                     f"{(str(sup.count('yes')) + '/' + str(len(sup))) if sup else '-'} | {outside} |")

    # pairwise
    lines += ["", "## Pairwise (fresh questions, both orders must agree)", "",
              "| Pair | Wins first | Wins second | Tie or disagreement | Sign test p |",
              "|---|---|---|---|---|"]
    for x, y in pairs:
        wx = wy = other = 0
        for q in questions:
            if not q["needs_fresh"]:
                continue
            a = (judged.get(f"pair|{x}|{y}|xy|{q['id']}") or {}).get("winner")
            b = (judged.get(f"pair|{x}|{y}|yx|{q['id']}") or {}).get("winner")
            if a is None or b is None:
                continue
            if a == b == x:
                wx += 1
            elif a == b == y:
                wy += 1
            else:
                other += 1
        lines.append(f"| {LABELS[x]} vs {LABELS[y]} | {wx} | {wy} | {other} | {sign_test(wx, wy):.3f} |")

    # cost
    lines += ["", "## Cost (measured)", "",
              "| Arm | Total (USD) | Per question | Search part per question | Input tokens per question |",
              "|---|---|---|---|---|"]
    for arm in arms:
        ok = [r for r in rows(arm) if "error" not in r]
        if not ok:
            continue
        tot = sum(r["cost"] for r in ok)
        lines.append(f"| {LABELS[arm]} | {tot:.3f} | {tot / len(ok):.4f} | "
                     f"{sum(r['search_cost'] for r in ok) / len(ok):.4f} | "
                     f"{statistics.mean(r['input_tokens'] for r in ok):.0f} |")
    jc = [v.get("cost") for v in judged.values() if v.get("cost")]
    lines += ["", f"Judge: {len(judged)} calls, {sum(jc):.3f} USD. Tavily is billed at {TAVILY_CALL} USD a "
              "search after the free 1,000 a month (counted here as if paid)."]

    # privacy
    if privacy:
        leaked = [p for p in privacy if p["leaked"]]
        lines += ["", "## Privacy", "",
                  f"{len(privacy)} fictional questions with personal data through the real privacy "
                  f"filter and "
                  f"`search_query()`: {sum(p['searched'] for p in privacy)} produced a query, "
                  f"**{len(leaked)} carried personal data** into the search request.", "",
                  "| Id | Searched | Query sent | Leaked |", "|---|---|---|---|"]
        for p in privacy:
            lines.append(f"| {p['id']} | {'yes' if p['searched'] else 'no'} | {p['query'] or '-'} | "
                         f"{', '.join(p['leaked']) or 'none'} |")
    return "\n".join(lines) + "\n"


# ------------------------------------------------------------------ main
async def main_async(a) -> int:
    env = load_env(Path(a.env_file) if a.env_file else None)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    questions = load_jsonl(Path(a.questions))
    if a.only:
        questions = [q for q in questions if q["id"] in set(a.only.split(","))]
    privacy_items = load_jsonl(Path(a.privacy))
    if a.smoke:
        questions = questions[:2] + [q for q in questions if not q["needs_fresh"]][:1]
    arms = [x for x in a.arms.split(",") if x]
    pairs = [("B", "C"), ("C", "D")]
    runs_path, judge_path = out / "runs.jsonl", out / "judge.jsonl"
    runs = load_jsonl(runs_path)
    done = {(r["arm"], r["id"]) for r in runs if "error" not in r}

    from app.websearch import web_search
    async with httpx.AsyncClient(transport=a.transport) as client:
        api = a.openai or OpenAI(env.get("OPENAI_API_KEY", ""), client)
        judge = a.judge or Judge(env.get("OPENROUTER_API_KEY", ""), client)
        settings = {"B": settings_for("searxng", a, env), "C": settings_for("api", a, env)}
        search = a.search or web_search
        for arm in arms:
            todo = [q for q in questions if (arm, q["id"]) not in done]
            limit = asyncio.Semaphore(1 if arm == "B" else a.concurrency)  # B: one search at a time, as a
            # single course would send them

            async def one(q, arm=arm, limit=limit):
                async with limit:
                    row = await run_arm(arm, q, api, settings, search)
                append_jsonl(runs_path, row)
                print(f"{arm:2} {q['id']:8} {'ERROR ' + row['error'][:80] if 'error' in row else 'ok'}",
                      flush=True)
            await asyncio.gather(*(one(q) for q in todo))
        runs = [r for r in load_jsonl(runs_path) if "error" not in r or (r["arm"], r["id"]) not in done]
        # the newest row per (arm, id)
        latest = {}
        for r in runs:
            latest[(r["arm"], r["id"])] = r
        runs = list(latest.values())
        judged = {r["key"]: r for r in load_jsonl(judge_path)}
        if not a.no_judge:
            await judge_all(questions, runs, judge, judged, judge_path, pairs,
                            asyncio.Semaphore(a.concurrency))
    privacy = await privacy_check(privacy_items, settings["C"]) if privacy_items and not a.smoke else []
    repeat = None
    rep_path = out / "searxng_repeat.json"
    if rep_path.exists():
        repeat = json.loads(rep_path.read_text(encoding="utf-8")).get("summary")
    text = report(questions, [r for r in runs if r["arm"] in ARMS], judged, privacy, pairs, repeat)
    (out / "report.md").write_text(text, encoding="utf-8")
    (out / "privacy.json").write_text(json.dumps(privacy, indent=1, ensure_ascii=False), encoding="utf-8")
    print(f"report: {out / 'report.md'}")
    return 0


async def searxng_repeat(a) -> int:
    """B's search only, all questions again, one after another: is the instance throttled? No model call."""
    from app.websearch import allowlist_for, engines_for, web_search

    env = load_env(Path(a.env_file) if a.env_file else None)
    s = settings_for("searxng", a, env)
    out = Path(a.out)
    out.mkdir(parents=True, exist_ok=True)
    times, empty, failed = [], 0, []
    for q in load_jsonl(Path(a.questions)):
        t0 = time.perf_counter()
        try:
            found = await web_search(q["question"], allowlist_for(q["course_type"], s),
                                     engines=engines_for(q["course_type"], s), settings=s)
            empty += not found
        except Exception as e:
            failed.append(f"{q['id']}: {type(e).__name__}")
        times.append(time.perf_counter() - t0)
    summary = (f"SearXNG repeat run ({time.strftime('%Y-%m-%d %H:%M')}, {len(times)} searches one after "
               f"another): p50 {f(pct(times, .5))} s, p95 {f(pct(times, .95))} s, {empty} with no result, "
               f"{len(failed)} failed.")
    (out / "searxng_repeat.json").write_text(json.dumps({"summary": summary, "failed": failed}, indent=1),
                                             encoding="utf-8")
    print(summary)
    return 0


def main(argv=None, **inject) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(HERE / "questions.jsonl"))
    ap.add_argument("--privacy", default=str(HERE / "privacy_questions.jsonl"))
    ap.add_argument("--out", default=str(ROOT / "eval-out" / "web-search"))
    ap.add_argument("--env-file", default="", help="the .env with the keys (default: the repository's)")
    ap.add_argument("--arms", default=",".join(ARMS))
    ap.add_argument("--only", default="", help="comma-separated question ids")
    ap.add_argument("--searxng-url", default="")
    ap.add_argument("--search-timeout", type=float, default=15)
    ap.add_argument("--concurrency", type=int, default=4)
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--repeat-searxng", action="store_true", help="only B's searches again, no model calls")
    ap.add_argument("--smoke", action="store_true", help="3 questions; with injected fakes (tests)")
    a = ap.parse_args(argv)
    a.transport, a.openai, a.judge, a.search = (
        inject.get(k) for k in ("transport", "openai", "judge", "search"))
    if a.repeat_searxng:
        return asyncio.run(searxng_repeat(a))
    return asyncio.run(main_async(a))


if __name__ == "__main__":
    sys.exit(main())
