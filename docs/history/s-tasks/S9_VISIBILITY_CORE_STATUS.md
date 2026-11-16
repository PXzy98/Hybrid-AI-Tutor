# S9 — Course visibility policy core

Status: **implemented and tested offline; real database/API integration blocked**.

The pure `instructor_visible_signals` function enforces:
- a caller-supplied successful instructor role check;
- visibility mode B only, explicit student acknowledgement, and no opt-out;
- visibility from `visible_since` onwards, never earlier;
- strict matching course and student identifiers for every record;
- mandatory successful audit callback before returning even an empty overview;
- numeric KC mastery signals only, without student question text.

Z4/Z10 must provide authoritative course membership, per-student timestamps,
auditing, learner state tables and access checks. S9 will then expose the approved
v2 instructor overview and plan endpoints, with tests for another course's instructor,
another student and logged-out callers.

This library does **not** grant permissions or implement the learning plan,
database persistence, end-of-term export or HTTP endpoints; those remain blocked.
