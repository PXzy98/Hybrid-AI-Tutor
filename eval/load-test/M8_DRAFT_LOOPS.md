# M8: why local tier 1 drafts failed at the 2048-token limit (2026-11-22)

**Short answer:** the drafts were not long. Asked for one JSON object (`title`, `body`, `citations`), the local
Qwen3.5-9B on the lab vLLM (0.34.0, structured output, thinking off, temperature 0.2) fell into a loop inside
the JSON in most custom drafts and wrote until `max_tokens` cut it: endless spaces between JSON tokens, or
the body counting passage numbers ("per Passages 3, 6, 7, 8, 10, 11, … 425,"). A loop is not fixed by a larger
limit. Asking the local model for Markdown instead (a `# Title` line, the draft, a last `Citations: 1, 3` line)
stopped the loops: 0 of 48 runs cut off, every draft valid.

## Method

The three custom drafts of the demo database (CS50x, Week 5; two of them the failed jobs of the browser test),
rebuilt exactly as the worker does (`draft_jobs._passages`: 8 passages, at most 1,200 characters each, about
4,450 characters and 1,520 to 1,580 prompt tokens), sent to the course's local connection (the same
`OpenAICompatClient` the gateway resolves) 8 times each. Only counts were recorded; the outputs were read by
hand to name the loop, and kept outside the repository. Open course pack text only.

The direct test of the earlier note (214 tokens) was one lucky run: the same request finishes in a few hundred
tokens in about one run of three.

## Results (8 runs per draft, 3 drafts)

| Variant | Cut at 2048 | Valid drafts | Note |
|---|---|---|---|
| JSON as shipped (#155) | 17 / 24 | 7 / 24 | loops: whitespace, or passage numbers in the body |
| JSON + "cite only in the citations list" | 10 / 24 | 14 / 24 | fewer number loops; whitespace loops stay |
| JSON + structured output without free whitespace (`disable_any_whitespace`) + the citation rule | 9 / 24 | 15 / 24 | number loops remain; several valid drafts had an empty-looking body |
| JSON + `frequency_penalty` 0.3 (a model setting) | 1 / 24 | 23 / 24 | no loops, but the body loses its line breaks (headings run together) and some drafts are one line: rejected |
| **Markdown answer (this fix)** | **0 / 24** | **24 / 24** | 580 to 1,670 completion tokens, bodies of 2,200 to 5,900 characters, no passage numbers in any body |

With the fix in the code (`generate_tier1_draft` through the real gateway): custom drafts 24 / 24 valid (bodies
1,800 to 7,000 characters); project ideas, sample proposal and FAQ, with a module and for the whole course,
24 / 24 valid.

## The change

- Local tier 1 drafts (project ideas, sample proposal, FAQ, custom) ask for Markdown and send no JSON schema;
  `parse_markdown_draft` reads the title, the body and the citations line, and falls back to JSON when the
  model answers JSON anyway. The citation checks are the same as before.
- Cloud drafts keep the JSON format (the cloud gate's `DraftCloudRequest`, V16): DeepSeek did not loop.
- Every tier 1 draft logs counts only: model, kind, passages, passage characters, prompt tokens, completion
  tokens, cut off. No text.
- No model setting changed (`max_tokens`, temperature, timeouts, concurrency stay as they are).

## Not covered here

- Tier 2 drafts (KCs, check items, misconceptions) and quiz drafts still ask for JSON. They were 8 / 8 valid
  on vLLM after Z20 and showed no loop in the browser tests, but they were not measured here; the 2048-token
  research (v5-plan section 10) covers them.
- The draft that said "the material has no example" (thin material) is the prompt's instruction to say so
  instead of inventing; not changed.
