# S11 — Independently labelled multi-course retrieval evaluator

This adds a reusable two-course RAG evaluation utility (plus CLI wrapper) with
Hit@1, Recall@K, MRR@K, negative-query abstention, mean and p95 retrieval latency.
The evaluator reads an existing, scan-approved on-disk course index, **never**
publishes an index itself, checks that each gold source and exact anchor matches
one and only one indexed passage, and rejects cross-course results or inconsistent
labels. Only aggregate metrics are output, never the input questions.

Usage from repository root with a private, instructor-authored CSV (not committed):
```powershell
$env:PYTHONPATH = "$PWD\backend"
& "F:\5902\.venv\Scripts\python.exe" eval\course_rag_v4.py --index-root data --labels <approved-labels.csv> --k 4
```
The CSV columns are `id,course_id,module_id,question,gold_source,gold_anchor,negative`.
Repeat `id` for multiple independent gold chunks. Negative examples have empty
source and anchor and `negative=true`.

**This has not produced measured real-course quality results.** Only fictional
two-course engineering tests are used. S11 still needs Gita's permission for ELG5902
teaching materials, approved real course indexes, and independent expert labels.
