# E6 label spot check

50 cases drawn at random from `cases.jsonl` (`random.Random(50).sample(cases, 50)`), each read against its
labels: entity type and span, the personal-health flag (which decides "must stay local") and, for negatives,
the words that must stay visible.

**Reviewer: the coding assistant (Claude), 2026-10-19 — not yet a human check.** A team member should repeat
the check on the same 50 ids before the final report; the ids below make that a 10-minute job.

| Result | Cases |
|---|---|
| Label correct | 47 |
| Debatable, kept as is | 3 |
| Wrong | 0 |

Sample by group: 26 positive, 16 negative, 4 hard, 3 French, 1 out-of-scope (no multi-turn case drawn; the
21 multi-turn messages were checked by hand when the 8 conversations were written).

Debatable cases (a different labeller could reasonably decide otherwise):

- **P187** “My symptoms got worse yesterday. hydration matters?” — labelled a personal health detail (stay
  local). It names no condition; a stricter reading would only call it a personal statement. Kept: it states
  the student's own health is worsening.
- **P051** “Ms. Grace Lee told us something different …” — labelled PERSON. Grace Lee could be course staff, who
  are not redacted (allow-list); she is not on the staff list, so she is treated as another person.
- **P320** “is it normal to cough up green mucus for weeks?” — labelled negative (no personal detail). It may
  imply the student's own symptom, but nothing says so; the filter is not expected to infer it.

Checked ids: P255 P137 P187 P327 P125 P355 P243 P393 P169 P044 P276 P163 P115 P347 P286 P079 P178 P051 P164
P114 P097 P036 P310 P312 P220 P326 P046 P033 P172 P354 P330 P221 P003 P117 P173 P223 P359 P055 P103 P227 P139
P298 P236 P065 P320 P108 P274 P297 P063 P211
