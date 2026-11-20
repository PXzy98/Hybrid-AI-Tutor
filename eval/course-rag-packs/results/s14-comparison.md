# S14: retrieval before and after (paraphrases, misspellings, semantic step)

Hit@1, hit@4 and MRR over passages, course-wide and scoped (module plus course-level files). *Before*: the S11 retriever (word and character TF-IDF), measured on the same day with the same questions. *After*: stemming, typo correction against the index vocabulary, logistics synonyms (weight 0.3), weight 0.8 for homework and exam files in course-wide concept questions, and the semantic step (the router's MiniLM encoder, weight 0.2, floor 0.2). Question sets: `questions/` (S11, eight packs) and `paraphrase_questions/` (S14: for CS50x and MIT 6.002 16 questions each, as a paraphrase and as a misspelled variant; gold files as in the S11 sets or the file that states the fact). Full reports: `report.md` (S11) and `paraphrase/report.md`.

Re-run after the review fix (stemming applied until nothing changes, so a typo correction matches the index): only MIT 6.002 course-wide moved, one question of 28 (hit@1 0.86 to 0.82, MRR 0.90 to 0.88); the paraphrase set is unchanged.

| Set | Pack | Mode | n | before hit@1 | after hit@1 | before hit@4 | after hit@4 | before MRR | after MRR |
|---|---|---|---|---|---|---|---|---|---|
| S11 | harvard_cs50x | course | 28 | 0.68 | 0.82 | 0.89 | 0.96 | 0.78 | 0.88 |
| S11 | harvard_cs50x | scoped | 28 | 0.89 | 0.93 | 0.93 | 0.96 | 0.91 | 0.95 |
| S11 | mit_6_002_circuits | course | 28 | 0.71 | 0.82 | 0.93 | 0.96 | 0.80 | 0.88 |
| S11 | mit_6_002_circuits | scoped | 28 | 0.96 | 0.96 | 0.96 | 0.96 | 0.96 | 0.96 |
| S11 | mit_6_006_algorithms | course | 25 | 0.60 | 0.64 | 0.88 | 0.84 | 0.71 | 0.71 |
| S11 | mit_6_006_algorithms | scoped | 25 | 0.88 | 0.92 | 0.96 | 0.96 | 0.91 | 0.93 |
| S11 | mit_7_016_intro_biology | course | 28 | 0.75 | 0.96 | 0.96 | 1.00 | 0.83 | 0.98 |
| S11 | mit_7_016_intro_biology | scoped | 28 | 0.96 | 1.00 | 1.00 | 1.00 | 0.97 | 1.00 |
| S11 | mit_7_03_genetics | course | 26 | 0.61 | 0.73 | 0.92 | 0.89 | 0.75 | 0.80 |
| S11 | mit_7_03_genetics | scoped | 26 | 0.92 | 0.85 | 1.00 | 0.96 | 0.96 | 0.90 |
| S11 | mit_hst035_pathology | course | 26 | 0.73 | 0.81 | 0.85 | 0.96 | 0.79 | 0.88 |
| S11 | mit_hst035_pathology | scoped | 26 | 0.85 | 0.89 | 0.96 | 0.96 | 0.90 | 0.92 |
| S11 | mit_hst151_pharmacology | course | 27 | 0.93 | 0.89 | 1.00 | 1.00 | 0.95 | 0.94 |
| S11 | mit_hst151_pharmacology | scoped | 27 | 0.96 | 0.96 | 1.00 | 1.00 | 0.97 | 0.97 |
| S11 | mit_res_6_007_signals | course | 25 | 0.64 | 0.80 | 0.96 | 0.96 | 0.79 | 0.87 |
| S11 | mit_res_6_007_signals | scoped | 25 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 | 1.00 |
| paraphrase | harvard_cs50x | course | 32 | 0.38 | 0.62 | 0.50 | 0.75 | 0.43 | 0.68 |
| paraphrase | harvard_cs50x | scoped | 32 | 0.56 | 0.66 | 0.66 | 0.78 | 0.60 | 0.71 |
| paraphrase | mit_6_002_circuits | course | 32 | 0.31 | 0.56 | 0.47 | 0.88 | 0.36 | 0.70 |
| paraphrase | mit_6_002_circuits | scoped | 32 | 0.53 | 0.84 | 0.56 | 0.91 | 0.55 | 0.87 |
| paraphrase, misspelled | harvard_cs50x | course | 16 | 0.31 | 0.69 | 0.44 | 0.75 | 0.36 | 0.71 |
| paraphrase, paraphrase | harvard_cs50x | course | 16 | 0.44 | 0.56 | 0.56 | 0.75 | 0.50 | 0.65 |
| paraphrase, misspelled | mit_6_002_circuits | course | 16 | 0.19 | 0.62 | 0.25 | 0.94 | 0.22 | 0.77 |
| paraphrase, paraphrase | mit_6_002_circuits | course | 16 | 0.44 | 0.50 | 0.69 | 0.81 | 0.51 | 0.63 |

Totals over all questions (weighted by n):

| Set | Mode | n | before hit@1 | after hit@1 | before hit@4 | after hit@4 | before MRR | after MRR |
|---|---|---|---|---|---|---|---|---|
| S11 | course | 213 | 0.709 | 0.817 | 0.925 | 0.948 | 0.800 | 0.871 |
| S11 | scoped | 213 | 0.929 | 0.939 | 0.977 | 0.977 | 0.948 | 0.955 |
| paraphrase | course | 64 | 0.344 | 0.594 | 0.484 | 0.812 | 0.397 | 0.688 |
| paraphrase | scoped | 64 | 0.546 | 0.750 | 0.609 | 0.844 | 0.575 | 0.787 |

S11 questions that were found in the top 4 before and are not now: `alg-16` (course, rank 4 -> miss), `gen-20` (course, rank 4 -> miss), `gen-26` (scoped, rank 1 -> miss), `gen-26` (course, rank 1 -> miss), `sig-10` (course, rank 2 -> miss). The semantic score lifts similar passages (other problem sets, other lectures) above them. The gains above outweigh them; the weights were chosen on the sum over all eight packs (scoped hit@4 is unchanged at 0.977).

## Still missed

- `cs50-p01b` ("wen dose the cours end?"): too garbled; the paraphrase `cs50-p01a` ("When does the course end?") is now found at rank 1 (before: not found).
- `circ-28` and the paraphrases `circ-p01a/b`, `circ-p02a/b` ("when is homework 4 due"): the calendar row states the due date next to a different homework ("Homework 3 due" in the row of Homework 4's hand-out); the syllabus ranks first. Needs a table-aware step; not done here.
- The evidence step (cross-encoder relevance, `app/routing/evidence.py`) is unchanged and can still drop a retrieved passage; S14 changed retrieval only.

## Cost

Retrieval of 4 passages: median about 26 ms lexical and about 39 ms with the semantic step on the CS50x index (1393 passages; one shared CPU core while a test suite ran). The sentence encoder loads once per process (about 7 s). Embedding a course happens at index build time in the worker: 600 to 1500 passages took 35 to 90 s with MiniLM-L6 on CPU, stored next to `passages.json` as `embeddings.npy` (float16). Indexes built before S14 keep working lexically until their next rebuild; `rag.semantic_retrieval: false` turns the step off.
