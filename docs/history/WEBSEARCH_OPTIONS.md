# Web search options (G1-92)

Status, 22 Oct 2026: **on hold.** The options below were written up for a decision; nothing is implemented yet.

## Today

- Neither the local nor the cloud model searches the web. Answers use only the stored MedlinePlus pages and
  instructor uploads; the cloud client calls plain `chat.completions` with no tools.
- The semantic router can flag a question as "needs fresh evidence" (`routing.freshness_required_threshold`),
  and the evidence check only accepts a fresh source verified within `routing.current_source_max_age_days`
  (30). No source can satisfy that flag yet.
- `backend/app/rag/pubmed.py` exists (opt-in, not used in student requests). It already builds PubMed queries
  from a fixed topic/focus vocabulary only.

## Rules every option must follow

1. **The student's sentence never leaves the server**, not even the sanitized one. The only thing sent out is a
   query built from a fixed vocabulary: topic + focus (for example `hypertension` + `treatment`). The local
   router chooses the focus from the fixed list.
2. Results only from allow-listed domains: medlineplus.gov, nih.gov, cdc.gov, who.int, canada.ca.
3. Results are marked "unreviewed source", show their source, are cached, and go through the same evidence
   check as other passages.
4. The cloud models' built-in search (OpenAI web_search, Gemini grounding) is not used: it would send the
   question to a search service outside our control.

## Option A: live queries to trusted APIs (MedlinePlus + PubMed)

When the router flags a question as needing fresh evidence, call the MedlinePlus Health Topics Web Service
(free, about 85 requests/min per IP, attribution required) and PubMed E-utilities at that moment; cache the
results.

- Pros: free, no API key, official medical sources only; the PubMed vocabulary already exists.
- Cons: MedlinePlus is general health information, not "latest news"; PubMed returns research abstracts that may
  be too technical for nursing students. Narrow coverage. The search service sees when a topic was asked about
  (but nothing about the student).

## Option B: general search API restricted to the allow-listed sites

The same fixed-vocabulary query, sent to a search API (Brave, Bing, Tavily, ...) with
`site:cdc.gov OR site:who.int OR site:canada.ca ...`.

- Pros: widest coverage and the most current pages (CDC, WHO, Health Canada updates).
- Cons: needs an API key and costs money; a third-party search provider sees the (generic) query; the HTML
  pages must be fetched and parsed.

## Option C: scheduled refresh, no live search

A daily job fetches every topic × focus from the allow-listed sources (MedlinePlus, PubMed, optionally the
sources of B) and stores them in the RAG index with a verification date. A student request never triggers an
outgoing request.

- Pros: strongest privacy (outside services cannot even tell when a topic was asked about); reproducible; the
  instructor can review new sources in the dashboard before they are served.
- Cons: not on demand; "fresh" means as of the last refresh.

## Recommendation

**C as the main path, with A as a live fallback on a cache miss.** Privacy is the core of the project, and C is
the easiest to review and demonstrate; A costs nothing and needs no key. B can be added later if the client
finds the coverage too thin.

## Open decisions

1. Which option: A, B, C or C + A?
2. Focus vocabulary. Proposal: `overview / treatment / risks / prevention / guidelines / statistics`.
3. Should students see PubMed abstracts, or only MedlinePlus and government pages?
4. What "up-to-date" means for this course (guidelines? new drugs? statistics?), to confirm with Dr. Abbas.

## Done when (from Jira)

A "needs fresh evidence" question gets at least one current, attributed source; the E4 audit shows no question
text in outgoing search requests; tests cover the allow-list and the query vocabulary.
