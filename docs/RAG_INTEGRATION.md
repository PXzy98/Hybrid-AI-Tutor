# Medical RAG integration (TF-IDF baseline)

## Status (2026-10-12)

This baseline is integrated into the Hybrid AI Tutor request pipeline. It was adapted from
`A:\5902\medical_rag_demo` without changing the original demo. It is **not** a clinically
reviewed knowledge base or a semantic/vector-database retriever.

- Implementation: `backend/app/rag/medical_tfidf.py` (`MedicalTfidfRetriever`)
- Registered name: `medical_tfidf`
- Selected by `rag.impl: medical_tfidf` in `config.yaml`
- Dependency: scikit-learn (declared in `backend/pyproject.toml`)
- Corpus snapshot: `data/medical_rag/raw/*.txt`
- Source provenance: `data/medical_rag/sources.json` and `corpus_manifest.json`
- Tests: `backend/tests/test_medical_tfidf.py` and `backend/tests/contracts/test_rag_contract.py`

## Data and retrieval

Five topic-specific MedlinePlus snapshots are used: high blood pressure, type 2 diabetes,
asthma, migraine and pneumonia. The material was fetched for the earlier demonstration
on 2026-10-06 (see the manifest for per-page last-modified dates). The corpus is a
research/development sample, not approved course lecture material.

At startup, text is split into sentence windows (five sentences, two-sentence overlap).
Each topic gets its own unigram/bigram TF-IDF matrix, with English stopwords and sublinear
term frequency. Retrieval computes cosine similarity *within the requested topic only*,
then prefers chunks matching the requested KC IDs and level. If too few match, remaining
topic chunks fill the requested k. Returned Chunk objects contain passage text, a
MedlinePlus URL, the topic, cosine score, KC IDs and level.

The existing pipeline calls this retriever *after local PII removal*. It does not upload
queries or learner profiles, and does not make an external API call. Existing answer
verification and cloud-request guards remain separate; the extractive answer/verification
demo was not substituted for the team's verification implementation.

## KC labels: provisional, not reviewed

The previous prototype had no KC/level annotations. The new adapter derives **candidate**
KC tags by comparing chunk text with the names and descriptions in
`content/topics/<topic>/kcs.yaml` using lexical TF-IDF. The level is inherited from
the highest-scoring KC definition. This is deterministic but **not a validation**.

High Blood Pressure has six draft KCs. The other four topics currently have only one
placeholder KC each. Therefore, apparent coverage of those topics does not imply
fine-grained personalization. All automatic tag assignments and medical material must
be reviewed by the team and Dr. Abbas where appropriate before student use.

## Develop and test

From the repository root in PowerShell:

```powershell
.\.venv\Scripts\python.exe -m pip install -e "backend[dev]"
cd backend
..\.venv\Scripts\python.exe -m ruff check .
..\.venv\Scripts\python.exe -m pytest tests/contracts -k rag -q
..\.venv\Scripts\python.exe -m pytest tests/test_medical_tfidf.py -q
..\.venv\Scripts\python.exe -m pytest -q
```

To revert temporarily, use `RAG__IMPL=fixture` or `RAG__IMPL=stub` in the local
`.env` file. `rag.impl` may also be configured in `config.yaml`.
No changes to the `/api/v1/ask` request schema are required.

## Remaining work before final RAG acceptance

1. Replace the tiny demonstration corpus with client-approved, course-specific sources.
   Confirm reuse permissions, document versions, review status, and update policy.
2. Have a human review KC and level tags; add the missing KC maps for other topics.
3. Create chunk-level query/relevance judgments and evaluate Recall@k, MRR, coverage,
   answer grounding and latency. The earlier 12-question *source-level* score is not
   evidence of chunk-level correctness; with topic-filtered retrieval it would be trivial.
4. Compare TF-IDF with dense embeddings/hybrid retrieval on the **same** labeled queries.
   Add a persistent vector index only if it materially improves retrieval quality.
5. Evaluate the real local/cloud model's grounded answers when Ollama/cloud access is
   configured, with privacy and medical-safety testing retained.

Never use unreviewed material to provide diagnosis or individualized treatment advice.


---

## Phase 2: section-aware hybrid lexical retrieval (2026-10-12)

The active retriever is now `medical_hybrid` in `config.yaml`. The previous
`medical_tfidf` implementation remains available for a reproducible A/B baseline.

Files:
- `backend/app/rag/medical_hybrid.py`: registered `medical_hybrid` retriever
- `backend/tests/test_medical_hybrid.py`: content, fallback, and API integration checks
- `eval/medical_rag_cases.json`: 20 hand-authored question / original-text anchor pairs
- `eval/medical_rag_compare.py`: fixed-case baseline versus hybrid comparison
- `eval/results/medical_rag_compare.md`: generated metrics and missed questions
- `scripts/export_medical_rag_review.py`: exports provisional KC and level tags
- `docs/review/medical_rag_kc_review.csv`: 53 review rows, all `pending`

**What changed:** preserve section headings and short list items when chunking (rather than
splitting solely at sentence punctuation). Retrieval combines locally computed BM25,
unigram/bigram TF-IDF cosine similarity, and character-n-gram TF-IDF cosine similarity.
Weights are 0.35/0.45/0.20 respectively, normalized within the requested topic.
KC and level matching are preferred, followed by topic-only fallback when fewer than
`k` passages match. MMR-style diversification penalizes near-duplicate passages.
Unknown topics, empty questions, and requests without meaningful overlap return `[]`.
No internet access, embedding API, vector database or external model is required.

**This is hybrid *lexical* retrieval, not semantic dense-embedding retrieval.**
Tags are machine-proposed and **have not been reviewed**; four topics still have only
one placeholder KC. Teaching adaptivity depends on having more detailed approved KC maps.

### Reproduce the comparative evaluation

```powershell
cd F:\5902
.\.venv\Scripts\python.exe eval\medical_rag_compare.py
.\.venv\Scripts\python.exe scripts\export_medical_rag_review.py
cd backend
..\.venv\Scripts\python.exe -m pytest -q
```

On the initial 20-query anchor set, measured Hit@1 was **55%** for TF-IDF versus
**75%** for the hybrid; Hit@4 **90%** versus **95%**; MRR@4 **0.688** versus **0.838**.
The hybrid averaged approximately **4–5 ms** retrieval against approximately
**0.5 ms** for the baseline (startup/index build excluded). See generated results
for the current rerun; numbers depend on hardware and process load.

**Important evaluation limits:** The anchors are exact snippets already known to occur
in the corpus. This is a small, hand-authored diagnostic, not blinded relevance
judgment, not reliable clinical grounding evaluation, and not a held-out benchmark.
Original 12-question source-level scores cannot validate chunk retrieval because
each topic has one MedlinePlus source. The remaining top-4 miss is the migraine
non-medicine relief question. Do not tune the implementation solely to these cases.

The medical content is still an October 2026 *demo snapshot*, not instructor-approved
course material. Do not use with real patient/student health data before permission,
medical-content review and privacy procedures are settled.

### Suggested next steps for the RAG owner

1. Obtain rights-cleared lecture materials and a dated, medically reviewed corpus
2. Have a reviewer fill in `docs/review/medical_rag_kc_review.csv` and build an
   explicit tag override/import process; do not silently treat suggestions as approved
3. Establish independent chunk-level relevance judgments with held-out questions,
   including deliberately out-of-scope and near-duplicate queries
4. Compare a locally run dense embedding model and a real hybrid lexical+semantic
   fusion model on exactly the same held-out questions
5. Revisit source freshness and citations when ingestion of updated documents is added


### Applying human-reviewed KC/level labels

The exported `docs/review/medical_rag_kc_review.csv` is a **review worksheet**.
It is never treated as approved input by default.

After a qualified reviewer has checked the source, copied excerpts, and correct KC:
1. Fill `review_status=approved`, `reviewed_kc_ids` (semicolon-separated, e.g.
   `HBP.5`), `reviewed_level` (`basic`, `intermediate` or `advanced`),
   and `reviewer` for the verified rows.
2. Copy the reviewed CSV to `data/medical_rag/reviewed_tags.csv` on the
   application machine. Keep pending rows pending. Do **not** populate a fake reviewer.
3. Restart the API. It loads only approved rows with a nonblank reviewer. The
   KC IDs must exist for that topic; invalid approved rows fail startup instead
   of silently changing learner guidance.
4. Overrides are tied to a SHA-256 fingerprint of `topic|source URL|chunk text`.
   When source material or chunking changes, stale overrides do not match and
   cannot be applied to a different chunk. Re-export and re-review after updates.
5. A tag review is not a medical-content approval or reuse licence. Those
   approvals are separate and remain required before real student deployment.

If `reviewed_tags.csv` does not exist, the retriever uses its provisional
automatic KC/level suggestions, as it does in the initial demo.
