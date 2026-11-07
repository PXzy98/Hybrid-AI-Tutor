# Course-material RAG Beta — Siyun (2026-11-03)

## Implemented

- Teacher uploads already accept TXT, MD, HTML, DOCX and text-layer PDF, automatically refreshing the topic index.
- This branch also recognizes Markdown, numbered and lecture section headings in uploaded files.
- Word heading styles are kept as section boundaries.
- PDF chunks do not cross pages. Their original page number is attached to chunk metadata, and the student-chat Sources section can show `filename (page N)`.
- MedlinePlus built-in passages and existing per-topic source IDs are unchanged. No embedding or external network request is needed for retrieval.
- The lightweight grounding checker continues to warn about missing evidence, low lexical support, and unsupported numeric claims. Its PASS is **not** a medical approval.

## PowerPoint lecture uploads (S2)

- Accept `.pptx` files (up to 20 MB compressed, 64 MB unpacked, 250 slides).
- Extract searchable slide-body text, tables and speaker notes **locally**, without a network request.
- Treat each slide as a separate source boundary. Blank/image-only slides retain their position, so citations refer to the original slide number.
- Every PowerPoint chunk carries `metadata.slide` (a positive integer); PDF chunks continue to use `metadata.page`.
- Reject presentations containing images but no readable text or speaker notes with an explicit indexing error; OCR is not automatic.
- The student-facing `slide N` label requires the S3 citation-source fix (separate task PR), plus the v4 frontend localization work owned by Tongkai. No new v1 fields or endpoints are added here.
- Tested with fictional three-slide presentations, including notes, a table, blank slides, image-only rejection and an actual teacher upload request. This verifies extraction/retrieval, not real medical content.

## Instructor workflow

1. Use the instructor **Content** tab to select a medical topic, upload a lecture note or PDF, and confirm it shows **Searchable**.
2. A scanned/image-only PDF will show an indexing error. Obtain an authorized text-layer export first; no OCR or online parsing runs automatically.
3. In the student chat, ask a question tied to the uploaded file. Source attribution should show its filename, plus page number for a PDF.
4. The file is still **unreviewed** until a subject-matter expert approves its content. A retrieval hit does not certify its accuracy, copyright permission, or clinical freshness.

Limits: 20 MB per file, 250 PDF pages, 500,000 extracted characters per file, 2,000,000 characters per topic. The page number refers to the PDF page order, not necessarily printed page numbering. Tables, diagrams, math, images and unusual PDF layouts still require manual quality review.

## Real-data evaluation (G1-97 / G1-104 / M6)

Use the CSV template at `eval/fixtures/course_rag_labels_template.csv`.
Do **not** fill in invented labels or give the system the expected answers before the instructor labels them.

Each record requires:
- `id`: question ID; repeat an ID to define multiple gold passages for one question.
- `topic`: one of the five topic folder names.
- `query`: a question written independently from the retrieval output.
- `gold_source`: exact `course/<topic>/<filename>` or MedlinePlus URL.
- `gold_anchor`: a short **exact excerpt** that occurs in one and only one indexed chunk.

To test that the retriever refuses a nonsense/out-of-scope question, leave both `gold_source` and `gold_anchor` empty. The evaluation will reject ambiguous or absent gold excerpts rather than silently marking them wrong.

Example command from project root (PowerShell):

```powershell
$env:PYTHONPATH = "$PWD\backend"
# Run from the repository root; prepare a private, independently labelled CSV first.
& .\.venv\Scripts\python.exe eval\course_rag_benchmark.py `
    --materials-dir .\data\topics `
    --labels .\eval-out\course_rag_gold.csv `
    --output .\eval-out\course_rag_beta_results.json `
    --marginal 0.70 --ideal 0.85
```

The materials path must contain `<topic>/<filename>` files actually uploaded for evaluation; the label file must refer to those same source names. Both target values are **provisional M6 figures** from the MVP report, not yet independently reconfirmed with the client. Tests print/optionally save Hit@1, Recall@1, Recall@4, Precision@1, Precision@4, MRR@4, negative-query abstention, source traceability, and mean/p95 retrieval latency (excluding indexing).

If only one passage is labelled per question, Precision@4 has a maximum of 25%; this is an annotation-design limitation, not a statement that three other retrieved passages are necessarily useless.

For repeatability: keep the gold CSV read-only, include difficult paraphrased queries, test across different lecture topics, and record extraction failures and skipped PDFs. Do not include personal student records or other protected data in code, public results, or git commits.

## Testing

```powershell
cd backend
python -m pytest -q tests/test_course_rag_beta.py tests/test_material_sync.py tests/test_rag_mvp_validation.py
python -m ruff check . ../scripts
```

The above checks are engineering tests built on fictional fixtures, including a two-page PDF. They do not replace independent medical review or real-student pilot testing.

## Medical advisor / BKT questionnaire — reserved, not started

Lavin responded on November 5, 2026: she did not find medical inaccuracies in the original questions, but advised more plausible distractors and stronger difficulty differences. A revised **84-question draft** and her comments are staged separately on branch `feature/s7-lavin-draft-content`, awaiting her second review and the Z4 content-migration interface. Every updated question remains unreviewed; no simulated student answers or BKT fitting have been recorded. An advisor's simulated student response would only test functionality, not generalize to a real student population.
