# Integration discussion notes — Routing, RAG, privacy and web search

**Date:** October 19, 2026. **Historical reference only.**
**Reviewed branch:** `origin/feature/rag-materials-sync-tongkai` around commit `95a83a3`,
including the Siyun RAG and semantic-routing integrations.
These notes originally described proposals and observations, not confirmed
changes in the current v4 code. See the English v4 guide for binding decisions.

## A. Agreed direction

1. A student's sensitive health question should be processed locally by default.
   If an explicit generalization policy permits cloud use, a trusted local model
   first rewrites the personal question into a hypothetical, non-identifying
   one. Failed or uncertain rewrites must stay local.
2. Enforce privacy at the final cloud-send boundary, regardless of which routing
   algorithm selected cloud. The router should handle capability and evidence
   scores, not decide whether private information can leave the device.
3. When cloud is unavailable, times out, or is blocked by privacy, provide an
   explicit local-model fallback notice rather than silently changing the route.

## B. Integration problems identified for review

### Must fix before merging

- Semantic routing must not bypass the `cloud_safe` gate or the pre-send
  privacy leak guard. No `found = [] if semantic` bypass is acceptable.
- Tests that force a stub router in `conftest.py` do not exercise privacy under
  semantic routing. Add semantic-route E4 audits and end-to-end privacy tests.
- A missing cloud key, unavailable model, or `analyze_route` failure must not
  produce uncontrolled cloud sends or a default-to-cloud failure path.
- Retrieval must run on both local and cloud routes. The external model may
  receive only course passages that are approved by the privacy gate.
- Heavy dependencies should be imported lazily where practical, so selecting
  a stub implementation does not require model assets.
- MiniLM's sequence length must be handled through bounded conversation
  context, not by exceptions that force cloud use.

### Architecture choices to confirm with Zhenyan, Tongkai and Siyun

- Whether routing returns a target directly or scores a capability threshold.
- Whether LR/SVM selection is exposed to students or limited to experiments.
- Whether the routing progress panel should default to off.
- Whether streaming should include actual answer tokens, and how to avoid
  losing learner updates if a client disconnects.
- Whether the `prototype_policy` training labels measure routing policy
  compliance rather than real LLM answer quality; E5 is needed for evidence.
- Whether `needs_current_evidence` requires actual approved-domain web search.
- Whether retrieval queries should include history (potential topic drift).
- Whether local understanding with Qwen and routing with MiniLM should merge.
- Whether model and cross-encoder latency is acceptable in the full pipeline.
- Whether E3/E4 CI can run without cloud keys or downloaded models.

## C. Privacy requirements and fallback design

### C1. Hypothetical generalization

Policy: `privacy.health_detail_policy: local_only | generalize`, defaulting
to `local_only`. Under `generalize`, the local model may transform a
first-person health question into a general third-person medical question.
Personal readings, doses, names, and exact dates must not survive the rewrite.
Run the privacy filter and personal-health checks **again** after rewriting;
any uncertainty means local-only response. Medical referral signals still
derive from the original question, not only the rewritten one.

Risks include re-identification from rare conditions and small classes.
The instructor/client must explicitly approve the chosen policy and document
the data residency implications. E4 should verify that personal health
details do not cross the external boundary.

### C2. Cloud-send and post-generation controls

- Restore the send-time leak guard for semantic routing.
- For `local_only`, personal health details must never leave the local network.
- For `generalize`, verify the actual rewritten payload, not merely the
  router decision.
- Apply post-generation PII/profile/health-detail leak checking consistently.
- Test stub and semantic routing with the same adversarial private inputs.
- Audit E4 with semantic routing, including SSE events, to ensure no question
  or source document text leaks through progress messages.
- Keep conversation history and routing diagnostics out of `CloudRequest`.

### C3. Visible local fallback

Cases: missing cloud configuration, transient cloud outage/timeout, and
privacy-blocked cloud request. Inform the user that the local model supplied
the response and identify the reason without exposing private text.
When local capability is weak, present a limitation and references.
Log intended versus actual route and reason without raw question text.
Emit a structured SSE fallback status. A `fallback_to_local` configuration
may be disabled for controlled experiments, but silent fallback is not acceptable.

## D. Web search research (October 2026)

The route's current-evidence feature does not make a cloud LLM inherently
up-to-date. An approved retrieval service must supply current public
references. Historical services considered:

| Provider | Intended use | Historical constraints |
|---|---|---|
| MedlinePlus Health Topics Web Service | Authoritative medical topic summaries | NLM public service; cite MedlinePlus.gov and respect service limits |
| PubMed E-utilities | Biomedical abstracts and papers | NCBI rate limits; use fixed or sanitized terms |
| Brave Search API | Independent general web index | Paid; verify retention and data-protection terms |
| Tavily | LLM-oriented web retrieval | Verify retention and service privacy terms |

The October 2026 prices, service quotas and retention claims are historical
and should be reverified before procurement or deployment.

### Required search controls

1. Build the query from general, sanitized topic concepts only.
2. Never include personal health details, learner identity or conversations.
3. Use an instructor-approved domain allowlist.
4. Record source URL/date and provenance, not raw student question text.
5. Treat retrieved web pages as untrusted evidence, not executable model
   instructions.
6. Validate citations, freshness, timeout, rate limits and spend budgets.

## E. Remaining owner actions

**Zhenyan:** privacy policies, cloud-send gate, explicit fallback, model
deployment and operational tests.
**Tongkai:** capability routing, current-evidence web search, user-facing
progress/fallback behavior and long-history handling.
**Siyun:** source passage retrieval, course-scope isolation and evidence
quality assessment.
**All:** record interface decisions and run independent cross-component
privacy evaluation. The authoritative updated ownership is in
`docs/v4-implementation-guide.md`.
