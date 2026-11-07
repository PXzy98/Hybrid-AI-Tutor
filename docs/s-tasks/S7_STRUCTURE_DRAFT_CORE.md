# S7 — Instructor AI structured content draft core

Creates **instructor-only, unpublished** structured candidates for:
1. KC names / definitions / prerequisites;
2. four-option diagnostic check items and evidence-based explanations;
3. misconceptions and corrections.

The generator takes scanned, course-scoped passages supplied by S4 and calls the
Z6 gateway with a mandatory trusted-local requirement. Strict schema and reference
validation reject extra keys, duplicate choices, invalid citations, wrong courses
and malformed output. Drafts cannot be published by this module.

This is not the approved medical question bank. Lavin's 30 revisions still require
second review. The actual S7 acceptance flow, PostgreSQL storage, KC identifiers
and API v2 require Z4, Z6, Z9, Z10 and Z11 production interfaces.
