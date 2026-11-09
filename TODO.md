# To do (v4)

The task list is section 7 of [docs/v4-implementation-guide.md](docs/v4-implementation-guide.md) (owners, sprints,
dependencies, "done when"); Jira project G1 tracks the same tasks. This page is the short status of 2026-11-08.
The older MVP list is in the history of this file. The state of each area and the decisions taken are in
[docs/HANDOVER.md](docs/HANDOVER.md).

## Deadlines (syllabus)

Beta 11/11 · Reflection #2 (ethics, individual) 11/18 · video 11/25 · Design Day 12/3 · final report 12/13.

## Zhenyan (Z)

| ID | Task | Status |
|---|---|---|
| Z1 | Course structure and interface contract | merged |
| Z2 | 9B vs 27B comparison, vLLM sizing | PR #51; local speed needs the course server |
| Z3 | PostgreSQL + Alembic | merged |
| Z4 | Course catalog | merged |
| Z5 | Settings layers, live component switch | merged |
| Z6 | Model gateway | merged; the vLLM load test needs the server |
| Z7 | Privacy profile framework | merged |
| Z8 | Docker Compose skeleton | merged |
| Z9 | API v2 (accounts, courses, members, invitations, content, settings, admin) | merged; end of term and export wait for S's per-course learner data |
| Z10 | Usage counters, CSRF, login limits, access tests | merged |
| Z11 | ECE profile, `scan_document`, `search_query`, consent text | merged |
| Z12 | Instructor AI tier 4 (local vs cloud evaluation) | PR #53 |
| Z13 | CI scans, `/metrics`; deployment on the test host, Grafana, alerts | part 1: PR #49; part 2 needs the host |
| Z14 | Operations manual, handover, load test | PR #50; load test needs the server |
| Z15 | Rule 14 in Z code | merged |

Next for Z: the v2 ask endpoint (pipeline per course, usage checks) and end of term, after S's per-course
learner-data interface.

## Siyun (S)

S1–S12 in guide section 7.2. Open items that other tasks wait for:
- `course_id` on the learner tables and an interface to export and delete one course's learner data (needed by
  end of term and the v2 ask endpoint);
- indexing accepts a document when `scan_document` reports no blocking finding (PR by Z for S's review);
- `defusedxml` for PubMed responses (PR by Z for S's review).

## Tongkai (T)

T1–T14 in guide section 7.3. Open items that other tasks wait for:
- frontend pages for API v2 (T6, T7); a v2 client sends `X-CSRF-Token` (api-v2.md section 2);
- pinned Hugging Face revisions for the routing models and the move to `transformers` 5 together with Z
  (PR for the pins by Z for T's review);
- T14 (this file in English, the Chinese guide moved to `docs/`): PR by Z for T's review.

## Waiting for others

- Lavin: second review of the 30 revised check items.
- Prof. Gita: permission to use the ELG 5902 material (S5).
- Course server access: vLLM load test, Z2 local speed, Z13 part 2.
