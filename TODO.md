# Project TODO (historical v3 backlog)

**Updated:** October 22, 2026, after the October 21 MVP submission. This is the
historical G1/Jira backlog, not the authoritative v4 implementation plan.
For current roles, dependencies, milestones and acceptance criteria, use
[the English v4 implementation guide](docs/v4-implementation-guide.md).

**Owners:** Z = Zhenyan, T = Tongkai, S = Siyun; Jira controls assignment.
**Milestones:** November 4 peer feedback, November 11 Beta, November 18 ethics
reflection, November 25 video, December 3 Design Day, December 13 final report,
December 14 client/advisor evaluation.

## 0. MVP follow-up

- [x] T: align presentation slide 14 with the report; retain BKT and model settings;
  remove the unnecessary hypothetical-rewrite switch.
- [ ] Z: add the generative-AI usage disclosure to the final slide.
- [ ] Z: fill Sprint 3 dates, task dependencies, sprint milestones, and Jira
  permissions for two TAs and the professor.
- [ ] Z: create Sprint 3a/3b if needed; close the duplicate dashboard task G1-4.
- [ ] Owners: review G1-57, G1-59, G1-61, G1-63, G1-64 and close fixed bugs.

## 1. Sprint 3a (October 21-28)

### Privacy — Z

- [x] G1-93: detect spaced or malformed student IDs and health details split over turns.
- [x] G1-95: retain age and sex when needed for educational medical context.
- [x] G1-109: merge configurable hypothetical health-question generalization with
  post-rewrite privacy checks and original-question medical referral rules.
- [ ] Add post-generation health-detail leakage detection.
- [ ] Scrub medical terms and readings before storage (E4/E6 finding).
- [ ] Scan instructor-uploaded documents before indexing.

### Deployment, operations and learner model — Z

- [ ] G1-94: instructor-configurable school-hosted local LLM server, model and
  a "Test connection" control.
- [ ] G1-56: Docker Compose, CI, demo seed script and packaged routing/evidence models.
- [ ] G1-100: review BKT/KC design and retain the rule learner as a fallback.
- [ ] Confirm cloud provider, data residency and cost limits with the client.

### Routing and web evidence — T

- [ ] G1-92: approved-domain search for current information, using only sanitized queries.
- [ ] G1-99: explain the observed 82.9% routing agreement.
- [ ] G1-74/75/76: fix conversational routing and long-history truncation.

### Retrieval and medical content — S

- [ ] G1-96: invite Lavin to answer the synthetic student questionnaire.
- [ ] G1-97: ingest approved PDF/lecture materials, improve chunks and KC filters,
  and reassess the provisional M6 Recall@1 thresholds (85% ideal, 70% marginal).
- [ ] G1-98: strengthen unsupported-answer detection.
- [ ] G1-112: confirm retrieval-quality thresholds with the client.
- [ ] G1-102: coordinate Lavin and Dr. Abbas medical-content review.
- [ ] G1-69: October 27 progress meeting.

### General

- [ ] G1-101: choose a student-friendly project name.

## 2. Sprint 3b (October 29-November 4)

- [ ] Z / G1-103: Beta E6 held-out privacy evaluation, E4 audit and dashboard workflow.
- [ ] Z / G1-107: Beta code review and CI.
- [ ] S / G1-104: evaluate RAG groundedness, Recall@K, Precision@K and latency.
- [ ] T / G1-105: routing and learner model evaluation (M7-M10).
- [ ] T / G1-106: test web source quality, privacy, latency and costs.
- [ ] T / G1-77-80: distinguish non-medical/logistics questions.
- [ ] T / G1-108: Beta report and demo.
- [ ] Z / G1-110: model reasoning controls and token budgets.
- [ ] G1-111: English/French UI localization; ownership follows updated v4 guide.
- [ ] Assign M11 answer latency, M12 cloud-use/cost, and M13 student ratings.

## 3. Sprints 4-6 and later

- Sprint 4 (Nov 4-10): Z validates accounts and instructor settings; S validates
  upload, replacement, indexing and restart persistence; T validates routing,
  end-to-end latency and local/cloud answer quality (E5).
- Sprint 5 (Nov 11-17): Z reviews code, privacy, UI and deployment;
  S evaluates retrieval/answers; T reviews routing logic and source corpora.
- Sprint 6 (Nov 18-24): team prepares client delivery, Design Day, report and manual.

### Additional Jira items

- [ ] S / G1-113: compare dense retrieval with hybrid retrieval on Hit@1/4,
  MRR@4, latency and memory use.
- [ ] S / G1-47: remaining four medical topics' KCs, check items and misconceptions,
  subject to Dr. Abbas review.
- [ ] Z / G1-46: online clinician content review.
- [ ] Z: multistep privacy upgrades, local LLM verification (C5), E1 dataset expansion,
  Dr. Abbas E3 evaluations and per-student cloud usage limits.
- [ ] Z/T: token streaming and safe status handling.
- [ ] S: delete or replace uploaded materials and update the search index.
- [ ] Z: Alembic migrations, Playwright end-to-end tests and end-of-course data deletion.

## 4. Integration technical debt (October 19 review)

### Privacy/security

- [ ] Z: post-generation health leak checks; confirm CloudRequest excludes
  history and routing internals.
- [ ] Z/T: test both stub and semantic routing without dependence on developer .env.
- [ ] Z: end-to-end private-medical-question + cloud routing test.
- [ ] Z: semantic E4 audit and SSE source-text exposure checks.
- [ ] Z/T: E3/E4 CI should tolerate unavailable models/cloud credentials.
- [ ] Check 19 historical failures related to unreviewed content; assign separately.

### Routing and resilience

- [ ] T: make analyze_route failure skippable without failing the whole request.
- [ ] S/T: retrieve evidence regardless of routing decision; deliver verified
  course passages through either route.
- [ ] S/T: lazy-load sklearn/torch/transformers when applicable.
- [ ] Z/T: publish explicit SSE fallback events.

### Open design decisions

- Should the router supply scores or pick targets? (Z/T)
- Should students select LR/SVM or should it be instructor-controlled? (T)
- Should the routing progress panel show simplified stages only? (T)
- Should answer text stream, and should learner writes happen outside streams? (T/Z)
- Should retrieval queries incorporate history? (S)
- Can the Qwen understanding and MiniLM routing stages be consolidated? (Z/T)
- Should the understanding model change after E1 results? (Z)
- Is weak evidence useful for each learner model? (Z)

### Known Jira bugs

- [ ] T / G1-58: medical-safety checker incorrectly blocks some general questions.
- [ ] Z / G1-60: first request after model reload times out; consider warm-up
  and Ollama keep-alive.

### Repository housekeeping

- [ ] T: remove obsolete ZIP handover scripts and machine-specific environment values
  after verifying their users no longer need them.
- [ ] All: keep file names, branch names, documentation and comments in English.

## 5. Historical completed work

The October 21 MVP report, presentation and speaker notes were submitted.
Existing work includes E6 privacy evaluations, semantic routing, hybrid medical
retrieval, BKT and rule-based learner models, personalization, teacher dashboard
and an E4 live-cloud audit. These historical claims are not a substitute for
current v4 production verification; see the English implementation guide and
Siyun's latest handoff for the present state.
