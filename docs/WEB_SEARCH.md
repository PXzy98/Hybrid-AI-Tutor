# Web search (task T13)

Cloud answers to questions that need recent information can add passages from a few allowed web sites. The
search is chosen when the stack is deployed. **The default is `openai`** (chosen after the comparison of
2026-11-16, below); without `OPENAI_API_KEY` the search step fails and the answer uses the course material.

## When it runs

All of these must hold (`app/pipeline/steps/web_search.py`, after `route` in `config.yaml`):

1. `websearch.provider` is not `off`;
2. the question goes to the **cloud** model (local answers, and courses set to local only, never search);
3. the semantic router found that it needs recent information (`requires_fresh_evidence`);
4. `search_query()` returns a query (guide rule 5). It is built from the privacy filter's sanitized text only;
   every sentence that held personal data is dropped, and nothing is searched when fewer than three general
   words are left. The search code never sees the original question;
5. with `privacy.llm_check` on, the local model's personal-health check has passed. It runs here, before
   anything is sent, instead of only when the cloud request is built; a flagged question (or a failed check)
   is not cloud-safe, so nothing is searched, and the generate step reuses the result.

The results are added after the course passages, shown in the Sources list under their page title, and the
routing panel shows a "Web search" step. A failed search is skipped: the answer uses the course material.

## The three modes

| `websearch.provider` | What | Needs |
|---|---|---|
| `off` | no search | nothing |
| `openai` (default) | OpenAI's web search (Responses API, `web_search` tool with `filters.allowed_domains` = the allow-list, `tool_choice: required`). `openai_model` (`gpt-6-luna`) searches for the query and writes short findings citing their pages; every cited page on an allowed site becomes one passage (its citing paragraphs, links removed). The course's cloud model then writes the answer from these passages, as with `api` | `OPENAI_API_KEY` in `.env`: an OpenAI key (the developer's own) |
| `api` | a hosted search API with the Tavily request format (`POST {api_url}` with `query`, `include_domains`, `max_results`); the allow-list is sent as `include_domains` | `TAVILY_API_KEY` in `.env` (each developer uses their own key; the old name `WEBSEARCH_API_KEY` still works) |
| `searxng` | the self-hosted [SearXNG](https://docs.searxng.org/) metasearch engine of the `searxng` Compose profile (JSON API); one query to the course type's engines (below) | no key; `SEARXNG_SECRET` in `.env` for the SearXNG server itself; `docker compose --profile searxng up -d` |

Set the mode in `.env`, for example `WEBSEARCH__PROVIDER=searxng`, or in `config.yaml`. Each provider reads
only its own key, so keys of the other providers can stay in `.env` when switching. Other settings in
`config.yaml` under `websearch`: `api_url`, `openai_url`, `openai_model` (`gpt-6-luna`), `openai_timeout_s`
(30), `searxng_url` (default `http://searxng:8080`), `max_results` (3), `max_chars` per result (1200),
`timeout_s` (8, `api` and `searxng`), `cache_hours` (24).

**Cache**: results are kept per process for `cache_hours` (0 turns it off), keyed by provider, query, sites and
engines, so the same question in a course does not search again. Only the sanitized query and public pages are
kept; empty answers and failures are not cached.

**What leaves the server**: only the sanitized query and the list of allowed sites (and, with `openai`, the
fixed instruction and model name). With `api` and `openai` they go to the search provider; with `searxng` to the SearXNG container, which forwards the query to its upstream search
engines. No student identifier, no conversation and no learner data are sent.

## Allowed sites

`websearch.allowlist` lists the sites per course type; a course type without its own list uses `general`. A
site includes its subdomains (`nih.gov` allows `www.ncbi.nlm.nih.gov`). Every result is checked again,
whatever the provider returned: only https URLs on an allowed site, cleaned to plain text (markup and scripts
removed), cut to `max_chars`, no duplicate URLs, at most `max_results`.

The defaults are a starting point for the deployer to review with the instructors:

| Course type | Sites |
|---|---|
| `medical_science` | medlineplus.gov, nih.gov, cdc.gov, who.int, semanticscholar.org, nature.com |
| `life_science` | nih.gov, ebi.ac.uk, nature.com, khanacademy.org, arxiv.org, semanticscholar.org |
| `ece` | ieee.org, nist.gov, python.org, developer.mozilla.org, en.cppreference.com, arxiv.org, semanticscholar.org, stackoverflow.com |
| `general` | wikipedia.org |

## SearXNG engines

SearXNG forwards each query to upstream engines. The scraped web engines (Google, DuckDuckGo, Brave,
Startpage) blocked the test instance after a few requests (CAPTCHA, "too many requests"), while the engines
that call an official API kept answering. So `websearch.searxng_engines` names API-backed engines per course
type, and each question is **one query** to those engines (`engines=` parameter):

| Course type | Engines |
|---|---|
| `medical_science` | pubmed, semantic scholar |
| `life_science` | pubmed, semantic scholar, arxiv |
| `ece` | arxiv, semantic scholar, mdn, stackoverflow |
| `general` | wikipedia |

SearXNG silently falls back to its default engines when an engine name is unknown or disabled, so only results
from the engines asked for are kept. A course type without engines (and no `general` list) uses the older
behaviour: one `site:` query per allowed site to the instance's default engines.

`deploy/searxng/settings.yml` keeps only these engines (`use_default_settings.engines.keep_only`) and turns
on `semantic scholar`, which SearXNG ships disabled. An instance deployed outside the Compose stack needs the
same file. API-backed engines have limits too: on the test instance PubMed (NCBI allows a few requests a second
without a key) answered "too many requests" and SearXNG then suspended it for its suspension time (an hour by
default), and Semantic Scholar's keyless API returned errors. SearXNG still answers 200 then, with the engine
under `unresponsive_engines`; when every engine asked for is down the search counts as failed (the routing
panel shows it), not as empty. These sources are mostly paper abstracts, documentation and encyclopedia pages; public health pages
(MedlinePlus, CDC) are better reached through the `api` mode.

## Outbound requests

Both modes use the model gateway's SSRF protection (`app/llm/ssrf.py`): the address is checked before the
request and the connection goes to a checked address (no DNS rebinding). The API must be a public address;
SearXNG is a deployment-internal one, but never one of the system's own services or a link-local address.

## Tests

`backend/tests/test_web_search.py` (no network: an `httpx.MockTransport`): allowed sites and look-alikes,
cleaning, `off` makes no request, the API request carries only the query and the allow-list, SearXNG asks
the course type's engines once and drops other engines' results (or, without engines, asks each site and
survives a failing one), the cache, an internal API address is refused, and the step searches with
`search_query()` only, never for local answers, questions without a need for recent information, or questions
with nothing general left.

## Evaluation (G1-106)

`eval/web-search/` compares the modes on 79 fictional questions of the four demo-course subjects (59 need
information from 2024 to 2026), answers by `gpt-6.1-terra`, judged by Claude Sonnet against references checked
on the web. Results of 2026-11-16 (questions needing recent information answered correctly):

| Mode | Correct | Cost per question | Total time p50 |
|---|---|---|---|
| no search | 30 / 59 | $0.001 | 2.9 s |
| `searxng` (API-backed engines) | 31 / 59 | $0.001 | 4.6 s |
| `api` (Tavily) | 40 / 59 | $0.010 (first 1,000 a month free) | 5.3 s |
| OpenAI writes the answer itself with `web_search` (`gpt-6-luna`) | 50 / 59 | $0.013 | 4.1 s |
| **`openai`** (`gpt-6-luna` findings as passages, `gpt-6.1-terra` answers) | 48 / 59 | $0.012 | 7.7 s |

No mode made the 20 control questions (no recent information needed) worse, and no personal data reached a
search request in 10 fictional questions with personal data. SearXNG helped little: PubMed matches every word
of a whole question and rate-limits clients without a key. The `openai` mode keeps the answer in the tutor's
own pipeline (the search model only reports findings, the course's cloud model answers from them as
passages): nearly as accurate as letting OpenAI answer itself, and better than Tavily in pairwise judging (26
wins to 11). Its search has a long tail: half of the searches take under 5 s, 10% more than 12 s, and 2 of 79
reached `openai_timeout_s` (30 s; the answer then uses the course material only).
