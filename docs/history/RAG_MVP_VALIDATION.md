# RAG MVP engineering validation (Siyun feature branch)

Scope: instructor material ingestion, lexical retrieval, evidence provenance, answer
grounding, and interface integration. This is a developer verification checklist,
**not** a clinical validation, a medical content approval, or a user survey.

## What was verified

- Five built-in MedlinePlus topics remain available.
- Course TXT/MD/PDF/DOCX/HTML upload, indexing, replacement, restart and topic
  isolation are covered by `backend/tests/test_material_sync.py` (the integrated
  tests from the team) and `test_rag_mvp_validation.py`.
- Uploaded source references use `course/<topic>/<filename>`. Local evidence
  records now expose the filename as a readable title and explicitly identify
  instructor-uploaded content as **review status unverified**.
- Weak accidental character n-gram matches are checked against the *raw* cosine
  score before topic-relative score normalization. Nonsense queries now abstain
  rather than hallucinating a retrieval match. A high-similarity misspelling
  can still retrieve results. This is a heuristic threshold, not a trained
  domain/out-of-domain classifier.
- Post-generation Grounding now warns if no course passages exist or if numeric
  tokens in a sentence cannot be found together in any supporting passage.
  Lexical overlap / numeric token presence **never proves** medical correctness.

## Rerun locally (PowerShell, from F:\5902)

```powershell
.\.venv\Scripts\python.exe eval\medical_rag_compare.py
.\.venv\Scripts\python.exe eval\mvp_rag_validation.py
cd backend
..\.venv\Scripts\python.exe -m pytest -q
..\.venv\Scripts\python.exe -m ruff check .
cd ..\frontend
npm run test -- --run
npm run build
```

## Retrieval numbers

**Existing MedlinePlus 20-query snippet-anchor check:**

| Metric | TF-IDF baseline | Medical Hybrid RAG |
|---|---:|---:|
| Hit@1 | 55% | 75% |
| Hit@4 | 90% | 95% |
| MRR@4 | 0.688 | 0.838 |

The fixed phrases come from the same source corpus; this is an anchor lookup
diagnostic, not independent relevance grading or medical truth evaluation.

**New isolated instructor-upload fixture:**

- 10 synthetic educational documents across five topics, with 10 manually
  annotated questions and one gold passage for each question.
- At the latest run: Recall@1 **100%**, Recall@4 **100%**, Precision@1
  **100%**, Precision@4 **25%**, MRR@4 **1.000**, returned-source
  traceability **100%**. Precision@4 is capped at 25% by one annotated
  positive per query; other potentially relevant passages count as negatives.
- Two deliberately unrelated inputs abstained after the relevance-gate fix.
- Latency is recorded per run in the JSON output. It excludes index-building
  and varies with machine load.

These easy, authored synthetic samples **do not** establish performance
on unseen professor materials. No clinical or real-student data is present.
They run in an isolated temporary materials directory; production uploads are
never modified.

Results:
- `eval/results/medical_rag_compare.json` and `.md`
- `eval/results/mvp_rag_validation.json` and `.md`

## Evidence and integration boundaries

- `backend/tests/test_rag_mvp_validation.py` covers numerical warnings,
  no-evidence warnings, source traceability, abstention, spelling tolerance,
  upload refresh and real FastAPI pipelines with a **fake** generation model.
- The integrated tests also cover teacher upload -> retrieved citation ->
  student answer and LR/SVM evidence routing with stubbed auxiliary models.
- Full real generative-LLM end-to-end success still depends on a reachable
  Ollama server and/or configured cloud provider, neither available during
  the earlier local deployment check.
- Expert approval of course materials, KC/level tags, source-date review,
  independent chunk relevance labels and broader domain/medical safety tests
  remain separate requirements before use with real students.

This branch does not alter the teammate-owned semantic route decision rules.
