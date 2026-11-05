# Historical privacy upgrade plan — October 19, 2026

**Owner:** Zhenyan. **Status:** Historical plan, not a certification of live v4
privacy protection. Binding v4 requirements are in
[the English implementation guide](../v4-implementation-guide.md) and
[the privacy subsystem report](../report/privacy_subsystem.md).

## 1. Baseline at MVP

The Privacy-Aware Hybrid AI Tutor uses Presidio/spaCy and custom entity
recognizers to detect student IDs, names, contact information and
personal medical details. It replaces sensitive spans with placeholders
locally, routes questions, and restores only those values that are
authorized for local processing. The model-facing learner profile is
restricted by the local/cloud trust boundary.

Important assumptions: never persist raw student questions, never
store a reversible identity map in external logs, and never include
student identifiers in instructor class aggregates. Do not claim that
a completed test in one route protects all routing implementations.

## 2. Scan instructor-uploaded documents before indexing

Uploaded PDF, PPTX, TXT or DOCX material may contain sensitive student
records or clinical information. The upload/index pipeline should:
1. Verify that the actor is an instructor for the correct course.
2. Extract supported text in a bounded parsing operation.
3. Run the course-appropriate `scan_document(text, profile)` analysis.
4. Reject or quarantine documents with sensitive content or incomplete
   scanner results, without writing their extracted text to persistent
   RAG passages.
5. Queue index rebuilding and publish a new version only after approval.
6. Record metadata and typed findings, not sensitive text.

The current S4 adapter accepts only a completed zero-finding scan;
the Z11 scanner and operational review process are Zhenyan's tasks.

## 3. Multi-turn privacy

Sensitive context may be divided across messages. A safe cloud payload
must be evaluated using the current request and the permitted conversation
context. Never concatenate raw past personal health statements into
cloud-bound prompts. Use local analysis to determine whether a disclosure
is sensitive even when each individual turn appears harmless.

Test paraphrases, separated conditions and readings, incomplete IDs,
and repeated follow-up questions.

## 4. Post-generation privacy checks and local verification

The cloud-send gate is mandatory for all routing methods, including
semantic routing. Recheck a generalized question and reject any
unapproved personal details. A local verification stage may detect
PII/profile leakage or unsupported personalized medical content in
model outputs. When safety or privacy cannot be established, use an
explicit local fallback or refuse the unsafe operation.

Streamed progress events and instructor logs must not contain raw
questions, uploaded texts or reversible mappings.

## 5. Medical question generalization

`privacy.health_detail_policy` supports `local_only` (default) and
an explicitly approved `generalize` mode. In the latter, a trusted
local model rewrites a personal question as a hypothetical, general
educational question, removing identifying details, readings, doses
and dates. A second privacy pass is mandatory before cloud use.

The local-only policy must prevail when consent, policy, or confidence
is missing. Medical referral decisions still derive from the original
question; a generalized prompt cannot erase safety signals.

## 6. Evaluation and release gates

- E6: repeat privacy filtering on held-out personal data cases.
- E4: audit actual cloud requests under stub and semantic routing, including
  fallback and streaming events.
- Verify that class-level instructor reports expose no individual question text.
- Confirm the provider, country of processing, retention policy and service
  terms with the client before authorizing external transfer.
- Obtain explicit instructor/client approval before use of real medical
  teaching materials or actual student records.

These are engineering safeguards; they do not independently establish
institutional ethics or legal compliance.
