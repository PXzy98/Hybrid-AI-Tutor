# V16: instructor AI drafts before and after (2026-11-21)

**Question.** Did #119 (custom drafts, chosen sources) and #129 (KC drafts leave out KCs the course already has;
quiz questions written about the subject, not "the passage") make the drafts of the local model better?
Method approved by Z on 2026-11-21. How to run: [../README.md](../README.md).

## Method

- **Versions.** "Before" is `a64ebb2` (the parent of `9d7d35d`, #119); "after" is main at `49fbd04`. Each
  version's own `app` package drafted in-process: `generate_tier1_draft`, `generate_structure_draft` and
  `parse_content` as the job `ai_draft.generate` calls them, and the request and parser of `quiz.draft`
  (5 questions, multiple choice and true/false). The gateway is `FakeGateway` around the app's vLLM client
  (thinking off, JSON schema enforced, temperature 0.2, output limit 1,024 tokens for one-text drafts and
  4,096 for structure drafts, as in the app); the timeout was raised to 180 s on the shared server. Nothing of
  the "before" code had to be adapted.
- **Model.** The lab vLLM, Qwen3.5-9B. Course pack text went only there.
- **Inputs, the same for both.** Five modules of three open course packs: CS50x week 2 (arrays) and week 4
  (memory), MIT 6.002 lecture 2 (circuit analysis), MIT HST.151 lecture 1 (receptors) and lecture 2
  (pharmacokinetics). Each pack was staged and indexed as in S11 (`instructor_only/` never staged), and the
  passages were retrieved once per module and kind with the job's query (8 passages for drafts, 6 for quiz
  questions): [inputs.json](inputs.json). Every module has three existing KCs written for this test (for
  example "Pointers", "Dynamic memory allocation", "Hexadecimal notation" for CS50x week 4).
- **Drafts.** 7 kinds (kcs, check_items, misconceptions, quiz, project_ideas, sample_proposal, faq) x 5
  modules x 2 versions = 70 drafts, one call each: [drafts_before.jsonl](drafts_before.jsonl),
  [drafts_after.jsonl](drafts_after.jsonl) (with the model's raw answers). `custom` exists only after #119 and
  is not compared.
- **What actually differs.** The requests sent to the model are byte-identical in both versions for
  project_ideas, sample_proposal, faq, check_items and misconceptions (checked by hashing the messages, the
  schema and the output limit). Only the KC draft (#129: the rule "never repeat a name from
  accepted_kc_names" and a filter that drops such items) and the quiz prompt (#129, W24: never "the text",
  "the passage" or a passage number) changed. #119's course and module guidelines go into the tutor's system
  prompt, not into drafts, and its custom kind and chosen sources do not change a default draft. So for five
  kinds the before/after difference is the model's sampling variation, which this run therefore also shows.
- **Rubric, the same for every draft** (scores with the reason per draft: [scores.json](scores.json)):
  valid (the version's own validators), wrong (items with a factual error or not exactly one correct answer),
  fit to the material (0 to 2), duplicates of existing KCs (KC drafts), edit effort (0 none, 1 small, 2 large,
  3 unusable or failed). Scored by one reviewer (Claude) from a sheet in random order without the version
  (`score.py --blind`); the reviewer knew which kinds had changed. Automatic counts: exact repeats of existing
  KC names, and quiz questions written about "the text" or a passage number.

## Results per kind

| Kind | Version | Valid | Items (mean) | Wrong items | Fit (0-2) | KC repeats raw / kept / same idea | "The text" in stem / explanation / passage number | Edit (0-3) |
|---|---|---|---|---|---|---|---|---|
| kcs | before | 5/5 | 3.0 | 1 | 2.0 | 15 / 15 / 15 | - | 3.0 |
| kcs | after | 4/5 | 3.5 | 0 | 2.0 | 4 / 0 / 4 | - | 1.4 |
| check_items | before | 4/5 | 5.2 | 1 | 2.0 | - | - | 1.4 |
| check_items | after | 4/5 | 5.5 | 1 | 2.0 | - | - | 1.2 |
| misconceptions | before | 5/5 | 3.8 | 4 | 2.0 | - | - | 1.6 |
| misconceptions | after | 5/5 | 4.4 | 3 | 2.0 | - | - | 1.2 |
| quiz | before | 5/5 | 5.0 | 3 | 2.0 | - | 8 / 25 / 15 | 1.2 |
| quiz | after | 5/5 | 5.0 | 3 | 2.0 | - | 2 / 19 / 5 | 0.8 |
| project_ideas | before | 5/5 | - | 1 | 1.6 | - | - | 1.4 |
| project_ideas | after | 4/5 | - | 0 | 1.5 | - | - | 2.2 |
| sample_proposal | before | 5/5 | - | 1 | 1.0 | - | - | 2.0 |
| sample_proposal | after | 3/5 | - | 0 | 1.0 | - | - | 2.4 |
| faq | before | 3/5 | - | 1 | 1.3 | - | - | 2.0 |
| faq | after | 5/5 | - | 1 | 1.8 | - | - | 1.4 |

"Wrong items" and "fit" count valid drafts only; "edit" counts every draft (a failed one is 3). KC repeats:
exact names in the model's answer / exact names in the kept draft / items the reviewer found to be an existing
KC (also renamed ones). Quiz: questions (25 per version) with such wording in the stem or options, in the
explanation, and with a passage or evidence number. Printed by `score.py`.

| All 35 drafts | Before | After |
|---|---|---|
| Valid | 32 | 30 |
| Usable with at most small edits (edit 0 or 1) | 15 | 22 |
| Mean edit effort | 1.8 | 1.5 |
| Wrong items (valid drafts) | 12 | 8 |
| Mean time per draft (4 in parallel, shared server) | 75 s | 84 s |

## What changed, with examples

**KC drafts (#129): the one clear gain.** Before, every valid KC draft only restated the module's three
existing KCs under the same names (15 of 15 items), for example 6.002 lecture 2: "Kirchhoff's voltage law",
"Kirchhoff's current law", "Series and parallel resistors". The instructor gets nothing new. After, the same
module gives "Node Voltage Analysis Procedure", "Associated Variable Convention", "Lumped Circuit Abstraction
Principles", and HST.151 lecture 2 adds steady state, bioavailability and AUC. But:
- the model still repeats existing names (4 exact repeats in its answers); the filter, not the prompt, removes
  them. In CS50x week 2 every item was an existing KC, so the whole draft failed ("The draft only repeats
  knowledge components the course already has"): 1 of 5;
- renamed repeats pass the exact-name filter: "Pointer Fundamentals" for "Pointers", "Total Clearance" for
  "Clearance" (4 items in 2 drafts). The instructor deletes them by hand.

**Quiz questions (W24): better stems, explanations mostly unchanged.** Stems or options written about the
material fell from 8 to 2 of 25 and explanations with a passage number from 15 to 5. "The text states ..." is
still in 19 of 25 explanations (before 25). Before: "According to the lecture, what is the primary goal of the
Basic KVL, KCL method?", explained by "Passage 4 states ...". After: "When applying the basic circuit analysis
method, what is the primary goal regarding the circuit elements?", explained by "The text states ...".
Correctness did not change (3 wrong of 25 in each; for example a 6.002 question with two right options,
1/R = 1/R1 + 1/R2 and R1R2/(R1+R2)).

**The other five kinds: no change, and the size of the noise.** Their requests are identical, yet valid drafts
moved by up to 2 of 5 (sample_proposal 5 to 3, faq 3 to 5) and the mean edit effort by up to 0.8. Differences
of this size in the table are sampling variation, not an effect of the code.

## Weaknesses of the local drafts in both versions

- **One-text drafts fail or come back nearly empty.** 5 of 30 project_ideas, sample_proposal and faq drafts
  failed (repeated passage citations 3, answer cut off at 1,024 tokens 1, a citation list repeated until the
  limit 1), and 5 valid ones are only a heading or a paragraph of the wrong kind. One-text drafts use the
  connection's default output limit (1,024 tokens); structure drafts get 4,096.
- **No sample proposal.** None of the 8 valid sample_proposal drafts is a proposal: from lecture material the
  model writes a lesson guide. project_ideas gives one project, rarely the asked "directions, topics,
  difficulty, KCs and deliverables".
- **Check items cut off.** CS50x week 2 check items failed in both versions at 4,096 tokens.
- **KC links of misconceptions** are often wrong (the schema makes the model pick a name from the list):
  3 drafts before and 1 after needed relinking (same request, so noise).
- **CS50x NUL character** (`\0` in the notes) comes out as `'0'` in 6 drafts.
- Check items and misconceptions are mostly correct: 2 wrong of 43 check items, 7 of 41 misconceptions.

## Local and cloud model on fictional material (V16 option)

A short fictional module (ROB 210, PID control of a teaching rover, written for this test; `FICTIONAL` in
`run_drafts.py`) drafted by both models: [drafts_cloud.jsonl](drafts_cloud.jsonl). The cloud drafts went
through the job's privacy scan and `CloudClient.complete_draft` (the cloud gate). Cloud model: the configured
`CLOUD_MODEL` (`deepseek-flash`).

| Kind | Local: valid, edit | Cloud: valid, edit |
|---|---|---|
| kcs | yes, 0 (5 new KCs) | **failed** |
| check_items | yes, 1 | **failed** |
| misconceptions | yes, 1 | **failed** |
| project_ideas | yes, 1 (one paragraph) | yes, 0 (directions, five topics, difficulty, KCs, deliverables) |
| sample_proposal | yes, 2 (notes, not a proposal) | yes, 0 (a fictional sample proposal, marked as such) |
| faq | yes, 2 (one question) | yes, 0 (9 questions) |

- For one-text drafts the cloud model is clearly better: it does what the kind asks, covers the whole module
  and stays within the material.
- **Every cloud structure draft failed** (3 of 3): the answers used their own field names ("description",
  "prerequisites", "evidence"; "prompt" and options as objects; "misconception"). The cloud transport asks
  only for a JSON object (`schema_output` is off for hosted APIs), and the structure prompt names only the
  `items` field, so a hosted model has to guess the item fields; with the local vLLM the schema is enforced.
  So the V16 cloud option works today for the one-text kinds (project ideas, sample proposals, FAQs and,
  by the same path, custom drafts, which were not run), not for KCs, check items or misconceptions.

## Conclusion

- **KC drafts got much better** (mean edit 3.0 to 1.4): before #129 the local model only repeated the
  course's existing KCs; after, most drafts add new ones. Left: a draft fails when the model only repeats
  (1 of 5), and renamed repeats are not caught.
- **Quiz questions got somewhat better** (edit 1.2 to 0.8): fewer stems about "the text" and fewer passage
  numbers, but most explanations still say "the text states".
- **Nothing else changed**, by design: the other five kinds send the same request. Their quality is the 9B
  model's: check items, misconceptions and FAQs are mostly usable, project ideas and sample proposals are weak,
  and a third of the one-text drafts fail or are empty.
- **Overall** usable drafts (edit 0 or 1) went from 15 to 22 of 35, almost all of it from KCs and quiz
  questions. Five drafts per kind with one sample each is small; the unchanged kinds show that differences of
  1 to 2 drafts per kind are noise.

**Suggestions (not done here; each would be its own task):** (1) give one-text drafts a larger output limit,
as structure drafts have, and drop repeated citations instead of failing the draft; (2) for the cloud model,
send the JSON schema where the provider supports it, or name the item fields in the structure prompt, so KC,
check item and misconception drafts work in the cloud; (3) for KC drafts, also catch near-duplicate names;
(4) a sample proposal needs a project description as its source, so the default sources or the guidance for
that kind should say so.

**License.** The drafts of the course packs and `inputs.json` contain or are derived from MIT OpenCourseWare
(6.002, HST.151) and Harvard CS50x material, CC BY-NC-SA 4.0; see `data/demo_courses/<pack>/README.md`.