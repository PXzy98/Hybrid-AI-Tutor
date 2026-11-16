# S6 — Instructor AI tier 1 draft-generation core

Status: **offline draft generator implemented; production integration blocked**.

Scope: `backend/app/instructor_ai/drafts.py`, `backend/tests/test_instructor_drafts_core.py`.
This branch does not modify platform, privacy, model gateway, course authorization, database,
frontend or frozen API v1 code.

The generator accepts 1–8 course-scoped retrieved chunks, asks the injected gateway for
project ideas, a fictional proposal guide, or course FAQ, and validates citation numbers.
It uses only the `local` model route with `trusted_local` required, disallows mismatched
courses, and returns a `status=draft` object without any publication operation.
Tests use a fake gateway and fictional passages; no external API is called.

**Remaining production dependencies:** Z4 course/material database and `ai_draft` table,
Z6 real model gateway implementation and its final trust-level enum,
Z9/Z10 course-role enforcement, and Z4 job queue. S4 must be integrated with Z11
`scan_document()` before its indexed passages can be used. S6 can then implement
authorized API v2 draft list/edit/accept/delete and persistence. A generated item must
remain invisible to students until explicit instructor acceptance.

This is not a claim that the complete S6 feature or its HTTP endpoints are finished.
