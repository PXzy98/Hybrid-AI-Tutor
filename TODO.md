# To do (v4)

The task list is section 7 of [docs/v4-implementation-guide.md](docs/v4-implementation-guide.md) (owners, sprints,
dependencies, "done when"); Jira project G1 tracks the same tasks. This page is the short status of 2026-11-15.
The state of each area and the decisions taken are in [docs/HANDOVER.md](docs/HANDOVER.md).

## Deadlines (syllabus)

Reflection #2 (ethics, individual) 11/18 · video 11/25 · Design Day 12/3 · final report 12/13.

## Done

- **Platform (Z1 to Z15)**: courses and modules, accounts and invitations, settings layers, PostgreSQL, model
  gateway, privacy profiles, document scanning, API v2, usage limits, CSRF, end of term and export, instructor
  AI tier 4, CI scans and monitoring configuration, operations manual.
- **Learner, content and instructor AI (S1 to S11)**: course retriever and materials on API v2, the
  eight open course packs, instructor AI tiers 1 to 3, the course-level knowledge model (the default), visibility modes, overview and learning plans, retrieval
  evaluation on all eight packs.
- **Quizzes and the end-of-term survey (Q1)**, decided at the advisor meeting of 2026-11-12.
- **Frontend on API v2 (F1, carrying T6 to T8)** with the UI upgrade (U1 to U5), accessibility (T11), manuals
  (T12), routing evaluation on ECE and CS (T4), question type (T5), demo build (T9).

## Open

| ID | Task | Owner | Status |
|---|---|---|---|
| T13 | Web search evaluation (G1-106) | T | search built (#88: off / API / SearXNG); evaluation needs SearXNG or a key |
| T10 | Video (11/25); French UI screenshots to Lavin | T | not started |
| T11 | Renaming | T | waits for the project name |
| T12 | Routing, frontend and web search handover notes | T | manuals done |
| — | `transformers` 5, `react-router` 7, `vite`/`vitest` (CI advisories) | T, Z | open |
| Z13, Z6, Z2 | Deploy on the test host with monitoring; vLLM load test; local speed of the 9B model | Z | waits for server access |
| Z13 | Choose the alert receiver | Z | waits for the client |
| S12 | Self-review and handover checklist | S | handover notes in `docs/history/s-tasks/` |
| T15 | Routing by subject: the routing heads are trained on medical questions only; harder ECE questions get no sources | T | not started |
| Z22 | Privacy filter tests: held-out ECE set, `life_science` and `general` sets, E6 scores for the v4 types, a fresh held-out medical set | Z | not started |

Not this term: targeted material for single students (only the learning plan with notes now). Tests and demos
use the eight open course packs in `data/demo_courses/`.

## Waiting for others

- Course server access: deployment, vLLM load test, Z2 local speed, monitoring.
- The client: cloud provider and billing, alert receiver, project name.
- Lavin: second review of the 30 revised check items; French UI screenshots.
