# Semantic routing in the complete main/RAG integration (v3)

## Behavior

The student selects LR or SVM per question. Both use the same local sentence embeddings and three independently calibrated heads: intended Cloud need, evidence requirement, and freshness requirement. The server first applies the capability/uncertainty gate, then retrieves and checks available course evidence. Local and Local-with-RAG share a single generator and a single `local` target.

Default pipeline:

`privacy_filter -> understand -> learner_context -> analyze_route -> retrieve -> route -> generate -> restore -> verify -> attach_check -> record`

The answering Qwen model no longer acts as a routing or evidence judge. The existing `understand` step still uses it for learner/course tagging, independently of routing.

Semantic runtime is local/offline: model preparation is an explicit command. Missing assets, incompatible classifier weights, overlong encoder inputs, unsupported domains and uncertain classification select Cloud with an explicit reason. A semantic Cloud decision never silently falls back to Local if Cloud is unavailable; the existing API error path is used.

## Privacy integration boundary

Requested scope: no privacy-condition branch inside semantic routing. `pii.cloud_safe` and `force_local_if_not_cloud_safe` do not change the semantic Local/Cloud decision. The existing upstream privacy filter, sanitized CloudRequest allow-list and post-response checkers remain owned by the teammate. Semantic generation does not repeat the legacy pre-send privacy routing guard. That integration point is marked `TEAM INTEGRATION` in code. The legacy stub router retains its original behavior for regression tests.

## Methods and removal

`backend/app/routing/methods/lr.py` and `svm.py` are independent training builders. Runtime inference uses portable NPZ coefficient/calibration arrays, not pickled sklearn models. All heads share the selected method and semantic encoder.

To keep LR only:

```yaml
routing:
  enabled_methods: [lr]
  default_method: lr
```

The options endpoint and student selector update from this configuration. Requests naming a disabled method receive HTTP 422. The unused builder/weight file can subsequently be removed; there are no method-specific branches in chat or generation code. Restart after changing this YAML.

## RAG integration contract

Keep the existing `Retriever.retrieve(query, topic, k, kc_ids, level) -> list[Chunk]` signature. The query includes recent sanitized student context for follow-ups. Each chunk still needs `text`, `source`, `topic`, `score`; existing KC/level fields continue to work. An optional `metadata` dictionary is additive:

```python
Chunk(
    text="The actual course passage...",
    source="course/chapter-3.pdf",
    topic="high_blood_pressure",
    score=0.83,                    # retrieval score; never treated as support probability
    metadata={
        "approved": True,         # optional; False/invalid explicit values reject a source
        "valid_until": "2027-01-01T00:00:00Z",  # optional expiration
        "verified_current": True, # required only for freshness-dependent questions
        "verified_at": "2026-10-17T12:00:00Z",  # ISO timestamp, refreshed by source owner
    },
)
```

Plain old-style chunks without metadata work for ordinary instructor-provided course material. This trusts the course Retriever's provenance contract; it does not infer source authority from text. Freshness-dependent questions additionally require a recent `verified_at` and `verified_current=True`. A publication date alone does not prove a source is current.

`rag.impl: medical_hybrid` is enabled. Siyun's BM25 + word/character TF-IDF retrieval and bundled five-topic snapshots are retained. The materials-sync patch indexes instructor uploads alongside the snapshots and displays their status in the Content page. Its optional PubMed helper is not automatically invoked by student requests. See `docs/MATERIALS_SYNC.md` for formats and limits.

RAG states distinguish `disabled`, `error`, `empty`, `returned` and `skipped`. Zero passages have zero support coverage. A question that needs evidence is never admitted to Local with zero evidence. A question that does not need external evidence can still use Local without RAG.

Evidence verification uses MS MARCO relevance and a separate QNLI answerability model. Explicit subquestions are checked separately; all must pass. Only accepted passages reach prompts and displayed course sources. Missing evidence model assets, malformed/expired metadata, oversized verification inputs and scoring errors cannot become a pass.

QNLI is a domain-transfer support estimate, not proof of factual truth. It does not fully resolve source contradictions or every implicit subtask. Current thresholds need a representative medical/course evidence benchmark. A complex question still needs to pass the independent capability gate even when relevant evidence exists.

## API additions

- Optional request `routing_method: "lr" | "svm"`; absent means the server default.
- `GET /api/v1/routing/options`: authenticated student-visible methods and display flag.
- `POST /api/v1/ask/stream`: POST/fetch SSE; `meta`, `progress`, `result`, `error`, `done` events. HTTP auth/validation/ownership errors occur before the stream begins. Transport interruption without a complete result is an error.
- Existing `POST /ask` remains supported.
- Additive response `routing_method`, `routing_details`, `routing_progress` fields.
- Runtime instructor setting `show_routing_progress`, persisted in existing configuration history; old history rows remain valid through a default. New requests snapshot the flag. Disabled means no detailed progress events or routing diagnostics, enforced server-side. The client also hides old panels while the flag is off; method selection stays available.
- `RouteInput` adds passages, method, retrieval status and recent sanitized conversation context. `RouteScore` adds target, method, analysis, evidence and accepted indices. Existing fields remain intact.

Timings are server wall-clock durations for actual stages; the active-stage clock is animated client-side between events. Cold local-model loading belongs to the embedding/evidence stage. The final route `score` is a policy score; `analysis.cloud_probability` is the separately calibrated classifier output. Neither is established clinical confidence.

## Model/data preparation and retraining

Run from `backend/`:

```bash
python -m app.routing.prepare                 # download all three local assets; train missing weights
python -m app.routing.prepare --routing-only  # encoder only; evidence models must be prepared before real RAG use
python -m app.routing.train --data ../data/routing/seed.jsonl --methods lr svm
```

The shipped NPZ weights were generated using the real sentence encoder. The seed contains 500 synthetic policy examples, 100 per topic, in 337 groups. Both trained NPZ files are carried forward unchanged from the 500-question package. Their labels describe desired routing policy, NOT measured Qwen answer success. The UI and training report explicitly mark this as `prototype_policy`.

For a capability benchmark, replace `cloud_required` with labels derived from independently graded answers from the actual local model under fixed prompts/materials. Include same-topic easy/hard pairs, complex cases without obvious trigger words, false-local cases and unfamiliar topics. Keep paraphrases in one group. Retraining fits calibration on group-separated folds and reports an additional grouped holdout before fitting deployable weights on all provided rows. Reported policy-label holdout scores must not be presented as end-to-end tutor quality.

Default encoder is English-focused. For multilingual deployment, configure a suitable multilingual encoder and retrain; old weights are rejected if the configured encoder name changes. NPZ arrays are pickle-free and sklearn-version-independent at inference.

## Cloud scope

The patch uses the existing configured OpenAI-compatible Cloud client. It does not add a provider-specific web-search service. Routing to Cloud is not itself proof that external evidence exists; sources still require provider/RAG integration and answer verification. No API keys, database, original `.env`, downloaded base models or `node_modules` are included in the patch.

## Complete integration

This v3 retains the entire latest-main instructor dashboard (students, class summary, settings, logs,
content), learner/understand implementation and existing privacy module. It supersedes the earlier
RAG-based v2 whose instructor page had only settings. See INTEGRATION.md for exact source commits.

The real-model smoke report contains both successful and failed decisions. Some relevant passages
are rejected by the current cross-encoder thresholds; an explicit diabetes course-source request is
missed by the evidence-need classifier. Neither the 500 policy labels nor generic QNLI prove actual
Qwen capability or medical correctness. Current thresholds and semantics are retained, not retuned
against the smoke prompts.
