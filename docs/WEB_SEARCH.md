# Web search (task T13)

Cloud answers to questions that need recent information can add passages from a few allowed web sites. The
search is chosen when the stack is deployed and is **off by default**.

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
| `off` (default) | no search | nothing |
| `api` | a hosted search API with the Tavily request format (`POST {api_url}` with `query`, `include_domains`, `max_results`); the allow-list is sent as `include_domains` | `WEBSEARCH_API_KEY` in `.env` (each developer uses their own key) |
| `searxng` | the self-hosted [SearXNG](https://docs.searxng.org/) metasearch engine of the `searxng` Compose profile (JSON API); one `site:` query per allowed site, the sites taken in turns | `SEARXNG_SECRET` in `.env`; `docker compose --profile searxng up -d` |

Set the mode in `.env`, for example `WEBSEARCH__PROVIDER=searxng`, or in `config.yaml`. Other settings in
`config.yaml` under `websearch`: `api_url`, `searxng_url` (default `http://searxng:8080`), `max_results` (3),
`max_chars` per result (1200), `timeout_s` (8).

**What leaves the server**: only the sanitized query and the list of allowed sites. With `api` they go to the
search provider; with `searxng` to the SearXNG container, which forwards the query to its upstream search
engines. No student identifier, no conversation and no learner data are sent.

## Allowed sites

`websearch.allowlist` lists the sites per course type; a course type without its own list uses `general`. A
site includes its subdomains (`nih.gov` allows `www.ncbi.nlm.nih.gov`). Every result is checked again,
whatever the provider returned: only https URLs on an allowed site, cleaned to plain text (markup and scripts
removed), cut to `max_chars`, no duplicate URLs, at most `max_results`.

The defaults are a starting point for the deployer to review with the instructors:

| Course type | Sites |
|---|---|
| `medical_science` | medlineplus.gov, nih.gov, cdc.gov, who.int |
| `life_science` | nih.gov, ebi.ac.uk, nature.com, khanacademy.org |
| `ece` | ieee.org, nist.gov, python.org, developer.mozilla.org, en.cppreference.com |
| `general` | wikipedia.org |

## Outbound requests

Both modes use the model gateway's SSRF protection (`app/llm/ssrf.py`): the address is checked before the
request and the connection goes to a checked address (no DNS rebinding). The API must be a public address;
SearXNG is a deployment-internal one, but never one of the system's own services or a link-local address.

## Tests

`backend/tests/test_web_search.py` (no network: an `httpx.MockTransport`): allowed sites and look-alikes,
cleaning, `off` makes no request, the API request carries only the query and the allow-list, SearXNG asks
each site and survives a failing one, an internal API address is refused, and the step searches with
`search_query()` only, never for local answers, questions without a need for recent information, or questions
with nothing general left.

## Not done yet

An evaluation of answer quality with and without web search (G1-106) needs a running SearXNG or an API key;
the harness is the next step once one is available.
