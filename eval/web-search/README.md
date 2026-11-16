# Web search comparison (T13 / G1-106)

Compares the ways the tutor can add recent information to a cloud answer: no search, the self-hosted
SearXNG, a hosted search API (Tavily format), and OpenAI's own `web_search` tool, on performance, accuracy
per subject and cost. See [docs/WEB_SEARCH.md](../../docs/WEB_SEARCH.md) for the search modes.

| Arm | What |
|---|---|
| A | no search: `gpt-6.1-terra` (reasoning effort none) answers from the prompt alone |
| B | SearXNG with the course type's API-backed engines (`app.websearch`, `provider: searxng`) + the same model |
| C | Tavily (`app.websearch`, `provider: api`) + the same model |
| D | OpenAI `web_search` with the same allow-list, answer by `gpt-6.1-terra` |
| DL | the same as D with `gpt-6-luna` (low cost) |

A, B and C use the app's `render_cloud` prompt; the web passages take the place of the course passages.
Every arm searches every question, including the control questions, to see whether search hurts.

## Files

- `questions.jsonl`: 79 fictional questions, four subjects (medical science, life science, ECE, computer
  science; course types of the demo courses). 59 need recent information (2024 to 2026) and carry a reference
  answer and the URL where it was checked, on an allowed site; 20 controls need none. Drafted and checked on
  the web by Claude Sonnet subagents (another family than the answer models), reviewed by Z: one question
  whose source could not be confirmed was dropped, three PubMed references corrected.
- `privacy_questions.jsonl`: 10 fictional questions with personal data (names, student numbers, e-mail,
  phone, health details, keys, addresses) and the strings that must never reach a search request.
- `run.py`: runs the arms, the judge and the report. Answers are cached in `<out>/runs.jsonl`, judgements
  in `<out>/judge.jsonl`.

## Running

Keys from the environment or the repository's `.env`: `OPENAI_API_KEY`, `TAVILY_KEY` (or
`WEBSEARCH_API_KEY`), `OPENROUTER_API_KEY` (judge). Only the fictional questions are sent.

```bash
python eval/web-search/run.py --searxng-url http://<searxng-host>:<port> --out <dir>
python eval/web-search/run.py --repeat-searxng --searxng-url http://<searxng-host>:<port> --out <dir>
python eval/web-search/run.py --smoke --out <dir>
```

`--repeat-searxng` runs B's searches again, one after another and without model calls, to check that the
instance is not throttled; the next report includes its summary. A full run costs about 6 to 8 USD (the
OpenAI search tool is the largest part). `backend/tests/test_web_search_eval.py` runs the harness against
fakes (no network).

## Judging

Claude Sonnet (`anthropic/claude-sonnet-5.5` through OpenRouter) grades each answer against the reference
(correct / partial / wrong / refused) and, for B and C, whether the passages support it. It compares B with C
and C with D on the fresh questions, once in each order; a win counts only when both orders agree. Small
samples: proportions come with Wilson 95% intervals, pairs with a sign test; read directions, not decimals.

## Limits

- No course retrieval: the fresh questions are not in the course material, so all arms answer without it.
- The reference answers were checked on the web on 2026-11-16 and will age.
- The SearXNG instance's engine set decides B's coverage; see `deploy/searxng/settings.yml`.
