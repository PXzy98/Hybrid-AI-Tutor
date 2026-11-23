# The 2048-token limit: output lengths, cut-offs and GPU time (research, 2026-11-22)

Answers to questions 1, 2 (for the call kinds M8 did not cover), 3 (as data), 4 and 5 of "Research: what the
2048-token limit changes" in `docs/v5-plan.md` section 10. Measurement only: no model setting, prompt or
backend code was changed. Options at the end are for Z to decide.

**Short answer**

- Student answers on the open packs are short: median 300 tokens, p95 868, max 1,156 for 84 plain questions;
  none was cut at 2048 (limit 1024 would have cut 2 of 84). Answers become long only when the student asks for
  detail and a table: median 1,065, p95 1,950; 1 of 64 was cut at 2048 and 7 of 64 came within 150 tokens of it.
  The one cut answer was a long table written to the end, not a loop (the same request ended at 1,936 tokens
  with a limit of 4096).
- Tier 2 drafts (KCs, check items, misconceptions) already have their own limit of 4096
  (`structure_drafts.STRUCTURE_MAX_TOKENS`) and are far below it (max 1,545 tokens, 45 of 45 valid, none cut).
  Quiz drafts use the connection's 2048: 5 questions need about 760 tokens, 12 questions (the most one call
  asks for) about 1,700 (max 1,801, 88% of the limit).
- The understand step (limit 200) needs 26 tokens (max 48).
- No loop was seen in any call kind except the tier 1 JSON drafts of M8. The only cut-off outside M8 is the long
  table answer above.
- A call holds a vLLM slot for its length divided by about 38 tokens/s: 8 s for a median answer, 23 s for a
  p95 answer, 47 s to 53 s for 2048 tokens. The server does about 270 to 300 tokens/s in total once 8 or more
  calls run together, so the throughput in answers per minute is set by the mean answer length, not by the limit.
- The hosted model (`deepseek-flash`) spent 49 to 223 hidden reasoning tokens on short fictional questions and
  never reached 2000 or 600. Drafts are another matter: the V16 cloud drafts used 1,073 to 3,664 tokens
  (reasoning included) against limits of 2000 (one-text drafts) and 4096 (structure drafts).

## Method

Harness: `eval/load-test/output_lengths.py` (phases `answers`, `understand`, `drafts`, `quiz`, `slots`,
`cloud`, `summary`). Never run by CI or unit tests; nothing imports it. It calls the lab vLLM
(Qwen3.5-9B, thinking off, temperature 0.2, `llm.local.max_tokens` 2048, 300 s client timeout instead of the
app's 60 s so a slow call is counted rather than lost) through the app's own `OpenAICompatClient`
(`factory.build_local_client`), with the app's own prompts and request builders imported from `backend/app`.
Only token counts, finish reasons, durations and counts are written to `eval/load-test/results/`
(`token_research_*.jsonl`, `token_research_tables.md`); the texts stayed in `var/token-research/` (git-ignored),
where the cut answer was read. Address and key come from the git-ignored `.env` and are not printed or stored.
At most 4 calls ran at the same time in the length phases. Every call cut at the limit was repeated once with a
limit of 4096 (`--rerun-cut`). A loop flag (compression ratio, distinct words and white space of the end of the
text) marks repetition; the one cut text was also read.

| Call kind | What the harness sends | Sample |
|---|---|---|
| Student answer | `render_local` (the generate step's messages: base + subject prompt, 4 passages of the pack's course index, no learner profile, no history) | 84 plain: 64 S11 questions (8 per pack, all 8 packs, one without an answer in the material first, then concept, application, logistics in turn) and 20 paraphrase/misspelled questions (10 on each of CS50x and 6.002) |
| Answer, detail asked | 16 of the S11 concept/application questions (2 per pack) with " Explain it in detail with a worked example and a comparison table." appended; each run 4 times | 64 (a stress case added for this study, reported apart) |
| Understand step | `understand.messages` and `schema` with the pack's module titles as KCs (8 to 11 KCs, 559 prompt tokens on average), `max_tokens=200` | 84 (the plain questions above) |
| Tier 2 draft | `structure_drafts.generate_structure_draft` through `FakeGateway`, passages and existing KCs of `eval/v16-drafts/results/inputs.json` (cs50_w4, e6002_l2, hst151_l1), the app's schema and 4096 limit | 5 per kind and case: 45 |
| Quiz draft | the request and `SYSTEM` of `quiz_drafts.draft`: no schema, the connection's limit | 3 cases x 5 drafts of 5 questions, 3 cases x 2 drafts of 12 questions: 21 |
| Slot time | the real answer prompts above (a different question per call), forced to a length with `min_tokens = max_tokens`, streamed | 300, 900 and 2048 tokens at 1 (3 calls), 8 and 16 at once (2 waves each) |
| Cloud | fictional course ZZ 101, 8 invented questions, `deepseek-flash` through the OpenAI SDK, no course text | 8 at the app's 2000 and 8 at 600 |

Not covered: tier 1 drafts (M8), personalised answers with learner profile or history (longer prompts, not
longer answers by themselves), the generalize and llm_check helpers (limits 120 and a few tokens), the
closed loop (`learner/weak_topics.py` makes no model call; there is no "explain another way" call in the
code). The lab server may be shared; durations are one measurement.

## 1. Output lengths per call kind (completion tokens)

| Kind | Calls | Median | p95 | Max | Limit | Cut at limit | Cut and looping | Above 1024 |
|---|---|---|---|---|---|---|---|---|
| Answers, S11 | 64 | 303 | 912 | 1,156 | 2048 | 0 / 64 | 0 | 2 / 64 |
| Answers, paraphrase | 20 | 218 | 695 | 726 | 2048 | 0 / 20 | 0 | 0 / 20 |
| **Answers, all plain** | 84 | 300 | 868 | 1,156 | 2048 | **0 / 84** | 0 | 2 / 84 |
| Answers, detail and a table asked | 64 | 1,065 | 1,950 | 2,048 | 2048 | **1 / 64** | 0 | 35 / 64 |
| Understand | 84 | 26 | 39 | 48 | 200 | 0 / 84 | 0 | - |
| Draft: KCs | 15 | 320 | 535 | 640 | 4096 | 0 / 15 | 0 | 0 / 15 |
| Draft: check items | 15 | 1,163 | 1,460 | 1,545 | 4096 | 0 / 15 | 0 | 0 / 15 |
| Draft: misconceptions | 15 | 521 | 816 | 817 | 4096 | 0 / 15 | 0 | 0 / 15 |
| Quiz draft, 5 questions | 15 | 760 | 816 | 829 | 2048 | 0 / 15 | 0 | 0 / 15 |
| Quiz draft, 12 questions | 6 | 1,702 | 1,801 | 1,801 | 2048 | 0 / 6 | 0 | 6 / 6 |

For the three draft rows the "above 1024" column is above 2048 in the generated table (0 of 45). Details:

- Plain answers by type: logistics median 173 (max 395), concept 440 (max 868), application 480 (max 1,156); by
  pack the medians run from 218 (pathology) to 807 (algorithms). A question without an answer in the material
  (8 of the 84) has median 242 but one reached 1,036 tokens (a long answer from general knowledge).
- Prompt tokens: answers 927 median, 1,272 max; drafts 1,535 median.
- Valid drafts: 45 of 45 tier 2 drafts passed `generate_structure_draft`; quiz drafts gave 5 of 5 usable
  questions in all 15 short runs and 12, 12, 12, 12, 12 and 11 usable in the 6 long runs.
- Detail answers: 17 of 64 above 1,500 tokens, 7 of 64 at or above 1,900. With a limit of 1024 half of them
  (35 of 64) would have been cut, which is the V22 finding behind #148.

## 2. Why calls reach the limit (outside tier 1 drafts)

Only one of the 298 local model calls of the length phases (148 answers, 84 understand, 45 tier 2 drafts, 21 quiz drafts) reached its limit:
`alg-06-d-r3`, an answer to a question that asked for detail and a table. The text is 5,698 characters with a
Markdown table of 48 cell separators and ends in the middle of the sentence after the table ("The `build(A)`
operation for a heap is O(n),"). The loop flag was false (compression and word variety normal). Repeated with a
limit of 4096 it ended by itself at 1,936 tokens (another sample, temperature 0.2). So it is a genuinely long
text that sits at the edge of 2048, not a repetition. No tier 2 draft, quiz draft, understand call or plain
answer came near a loop.

Tier 2 drafts and quiz drafts differ from tier 1 in what M8 found: tier 2 uses the JSON schema with an enumerated
KC list and a list of at most 12 items, which ends the object by itself; quiz drafts have no schema but a fixed
number of questions. Neither looped in 66 runs. The tier 1 loop is therefore tied to the free `body` string,
not to JSON in general. (A quiz of more than 12 questions needs several calls; 12 questions need about 1,700
tokens, so a longer request per call would be cut.)

## 3. What a cut-off costs, per kind (data for a decision)

| Kind | Reached the limit in this study | What a cut does today | Headroom |
|---|---|---|---|
| Plain answer | 0 of 84 | a note says the answer stops early (#148) | max 1,156 of 2048 |
| Answer with detail and a table | 1 of 64 (7 of 64 within 150 tokens) | the same note; the student asks a follow-up | 2048 is just enough; 11% of these answers are above 1,900 |
| Understand | 0 of 84 | the step is skipped | 48 of 200 |
| Tier 2 draft | 0 of 45 | the draft is lost (invalid JSON), but its limit is 4096 | 1,545 of 4096 |
| Quiz draft (5 questions) | 0 of 15 | the quiz gets no question ("no usable question") | 829 of 2048 |
| Quiz draft (12 questions) | 0 of 6 | as above, or fewer questions if the cut falls after a complete one | 1,801 of 2048 |
| Tier 1 draft | see M8 | the draft is lost | see M8 |

A cut answer is cheap to rerun at a larger limit (the one case took 1,936 tokens); a cut JSON draft is lost
entirely, which is why drafts need more margin than answers.

## 4. What the GPU pays: time per call and slots

Forced lengths on the real answer prompts, streamed, straight to vLLM (no app queue), 2 waves at 8 and 16
at once, 3 calls one after the other at 1. "Slowest" is the slowest call of the level.

| Output length | At once | Calls ok | Call p50 (s) | Slowest (s) | First token p50 (s) | Tokens/s per call | Total tokens/s |
|---|---|---|---|---|---|---|---|
| 300 (median answer) | 1 | 3 / 3 | 7.0 | 7.0 | 0.2 | 43.9 | 42.9 |
| 300 | 8 | 16 / 16 | 8.6 | 8.7 | 0.8 | 38.4 | 277 |
| 300 | 16 | 32 / 32 | 9.9 | 17.9 | 1.3 | 35.3 | 271 |
| 900 (p95 answer) | 1 | 3 / 3 | 20.8 | 20.8 | 0.2 | 43.7 | 43.4 |
| 900 | 8 | 16 / 16 | 23.5 | 23.7 | 0.8 | 39.5 | 305 |
| 900 | 16 | 32 / 32 | 27.1 | 48.7 | 1.4 | 36.0 | 297 |
| 2048 (the limit) | 1 | 3 / 3 | 47.1 | 47.1 | 0.2 | 43.7 | 43.5 |
| 2048 | 8 | 16 / 16 | 53.1 | 71.2 | 0.8 | 37.7 | 233 |
| 2048 | 16 | 32 / 32 | 80.8 | 127.2 | 1.3 | 34.0 | 272 |

Reading the table:

- One call decodes at about 44 tokens/s alone and about 38 tokens/s with 8 at once. A call therefore holds its
  slot for length / 38 s: median answer 8 s, p95 answer 23 s, limit-long answer 53 s. Tier 2 drafts measured in
  the draft phase (4 at once): KCs 8 s, check items 28 s, misconceptions 13 s (medians); quiz drafts of 5
  questions 19 s, of 12 questions 41 s.
- Total throughput stops growing at 8 calls at once: 270 to 300 tokens/s at 300 and 900 tokens, 233 to 272 at
  2048 (the long calls also carry a larger KV cache). At 16 at once the per-call speed hardly drops (34 to 36
  tokens/s) but the slowest call takes up to twice the p50 (17.9 s vs 9.9 s; 127 s vs 81 s): about the first 8
  calls run at full speed and the rest wait for a free place in the batch (inferred from the spread, not read from the server), so a 16th student waits one full
  answer length. Slots in the sense of `max_concurrent` are therefore about 8 on this server, as Z23 found.
- Answers per minute at saturation = 60 x 290 tokens/s / mean answer length:

  | Mix of answers | Mean tokens | Answers per minute |
  |---|---|---|
  | The plain questions of this study | 386 | about 45 |
  | 90% plain, 10% asked for detail | 467 | about 37 |
  | Every answer is a detail-and-table answer | 1,201 | about 14 |
  | Every answer reaches 2048 | 2,048 | about 8 |

  The Z23 "about 40 answers per minute in a burst" holds for plain questions and falls to about 37 if one
  answer in ten is a long one. The limit itself only matters for the worst case: 2048 tokens is 53 s of one
  slot, 2.4 times a p95 answer.
- Timeout: `llm.local.timeout_s` is 60 s and the client retries once. A 2048-token call takes 47 s alone and 53
  s at 8 at once (up to 71 s); with 16 at once 80 s p50. A long answer or a quiz or draft of 40 s and more
  therefore comes close to or over the timeout when the server is busy (measured with a 300 s timeout here;
  whether the app's gateway queue keeps the load at 8 was not tested).

## 5. The cloud side

`deepseek-flash`, fictional prompts only (nothing from the packs), the app's system prompt and material block,
8 questions at each limit:

| Limit | Calls | Cut (finish_reason length) | Completion tokens median | Hidden reasoning median | Reasoning max |
|---|---|---|---|---|---|
| 2000 (`llm.cloud.max_tokens`) | 8 | 0 | 214 | 90 | 223 |
| 600 | 8 | 0 | 229 | 81 | 195 |

The API reports the hidden reasoning in `completion_tokens_details.reasoning_tokens`, and it counts in
`completion_tokens` (the visible answer is about the difference). On short questions it is 49 to 223 tokens,
about 40% of the completion; answers took 1.4 to 4.0 s. A 2000 limit is far from being reached by an answer
like these, so a cut-off by reasoning is unlikely for ordinary answers; the question for M5 stays open for
long questions (a table, a long worked example) and for drafts, which the V16 run measured on the fictional
module (counts in `eval/v16-drafts/results/drafts_cloud.jsonl`, completion tokens including reasoning):

| Cloud draft | Completion tokens | Limit it ran under |
|---|---|---|
| FAQ | 1,073 | 2000 (the connection's, none is passed for one-text drafts) |
| Project ideas | 1,513 | 2000 |
| Sample proposal | 1,550 | 2000 |
| Misconceptions | 1,657 | 4096 |
| KCs | 3,382 | 4096 |
| Check items | 3,664 | 4096 |

The local model wrote the same drafts in 135 to 1,070 tokens. The cloud one-text drafts use up to 78% of 2000
and the cloud structure drafts up to 89% of 4096, so a longer module or request would be cut (and the cut
would show as a failed draft). Two of the V16 structure drafts failed for schema reasons (V16 report), not
for length. I did not measure the 30 s cloud `timeout_s` against drafts again; the V16 cloud drafts took 21 to
40 s.

## Observations

1. Outside the tier 1 JSON drafts the 2048 limit is not the problem on these packs: no plain answer, tier 2
   draft, quiz draft or understand call reached it, and the single cut was a long table.
2. The cost of 2048 is paid only by the long answers: the 11% of detail-and-table answers above 1,900 tokens
   hold a slot for 50 s each. The mean answer, not the limit, decides the GPU (386 tokens: 45 answers a
   minute).
3. The quiz draft is the call with the smallest margin among the JSON calls: 12 questions need 1,700 of 2048
   tokens, and it has no schema.
4. At 16 at once nothing fails, but half of the calls wait a full answer; the limit of about 8 together is
   a property of the server, not of the token limit.
5. The 60 s timeout is shorter than a busy long call (53 to 127 s).
6. Hidden reasoning of the cloud model is small for answers and large for drafts.

## Options for Z (not decisions)

| # | Option | What the data says |
|---|---|---|
| A | Keep 2048 for everything | Holds for all kinds measured here; the long detail answer sits at the edge (1 of 64 cut, the note appears). Quiz drafts of 12 questions have 12% margin |
| B | A limit per call kind (the gateway already takes `max_tokens` per call, as tier 2 does with 4096) | Understand 200 is ample (max 48); quiz drafts 3072 or 4096 like tier 2 (12 questions need 1,800); answers 2048 or 3072; tier 1 drafts per M8 |
| C | Retry a cut answer once with a shorter request ("answer in at most N words") instead of keeping a cut text | A cut answer is a long text, not a loop (one case, 1,936 tokens at 4096), so a retry would finish; it adds up to 53 s of slot time per retry |
| D | Raise answers to 3072 | Would finish nearly all detail answers (the one cut answer ended at 1,936 tokens with 4096) but a 3072-token call holds a slot for 81 s and passes the 60 s timeout; only useful with a larger `timeout_s` and streaming |
| E | Keep 2048 and raise `llm.local.timeout_s` (60 s) | Needed anyway for a busy server: 53 to 127 s measured for a 2048-token call |
| F | `llm.cloud.max_tokens` per kind: 2000 for answers (reasoning 49 to 223 here), more for drafts (up to 3,664 with reasoning) | One-text cloud drafts used up to 78% of 2000, structure drafts up to 89% of 4096 |
| G | For Z23/V13: plan with the mean answer (about 45 a minute for plain questions, about 37 with 10% long ones), not with the limit; treat 8 as the slot count | One answer per student at 2048 would be 8 a minute |

## Reproduce

Unpack the packs (`python scripts/fetch_open_courses.py unpack`), put `VLLM_BASE_URL` and `VLLM_KEY` (and for
the cloud phase `CLOUD_*`) in your own `.env`, then from the repository root (a Python with the backend
requirements, e.g. the main checkout's `.venv`):

```
python eval/load-test/output_lengths.py answers --per-pack 8 --paraphrase-per-pack 10 --twins 2 --rerun-cut \
    --env-file ../.env --raw-dir ../var/token-research
python eval/load-test/output_lengths.py answers --per-pack 8 --paraphrase-per-pack 10 --twins 2 --twin-reps 4 --append --rerun-cut ...
python eval/load-test/output_lengths.py drafts --reps 5 --rerun-cut ...
python eval/load-test/output_lengths.py quiz --reps 5 --rerun-cut ...
python eval/load-test/output_lengths.py understand --per-pack 8 --paraphrase-per-pack 10 --rerun-cut ...
python eval/load-test/output_lengths.py slots --lengths 300,900,2048 --per-pack 8 --paraphrase-per-pack 10 ...
python eval/load-test/output_lengths.py cloud --env-file ../.env
python eval/load-test/output_lengths.py summary
```

Indexing the eight packs with the semantic encoder takes about ten minutes the first time; the prompts are kept
in the raw directory (`prompts_*.json`, course text: never commit). The packs are open course material
(MIT OpenCourseWare, Harvard CS50x; CC BY-NC-SA 4.0); the results files hold counts and question IDs only.
