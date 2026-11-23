# Video (11/25) and Design Day (12/3) demo script (task T10, draft)

Story: **PACT, "Brightspace plus"**: a course platform with an AI tutor that keeps students' data private, for
teaching, research groups and industry training; a bridge between academia, research and industry. Only
fictional accounts and the open course packs (`data/demo_courses/`) are shown.

Setup: the production site (or the dev server for the video) built with
`python scripts/build_demo.py --students 6 --sample-activity --learner-content` (the
`--learner-content` option comes with S15, PR #113; merge it before the demo build); the demo vLLM running
(DEMO_VLLM.md); a second browser profile for the student.

| Min | Who | What to show | Point to make |
|---|---|---|---|
| 0:00 | — | title, the problem: students paste personal details into AI tools; instructors want insight, not surveillance | privacy is the main message |
| 0:40 | student | log in, the green privacy line, **What is private?** (en, then switch to fr) | nobody, not even the instructor, sees your questions (V1, V3) |
| 1:30 | student | ask in CS50x "Compare memory safety in C, Rust and Go for systems programming today, with the trade-offs of each."; open the routing steps: the cloud model answers; ask it again starting with "I have asthma and missed the lab." (a fictional health detail): the routing steps still choose the cloud, but the local model answers with "A privacy check kept this question on the local model." | a health detail never leaves the university: the privacy filter overrides the routing; a name or a student number is replaced by a placeholder before a question reaches a cloud model (not shown on screen; say it) |
| 2:30 | student | a quiz; **My progress** changes; **Explain it another way** on a weak topic; **How answers should look** | the learner model adapts privately (S15, V8, V15) |
| 3:30 | instructor | **Class overview**: use of the tutor, topics the class finds hard, hidden small groups | statistics only (V2, V8) |
| 4:15 | instructor | course and module guideline ("never give the final answer of a homework problem"); ask as the student again | instructor rules bind the tutor (Z26) |
| 5:00 | instructor | **AI assistant**: custom request "research topics from this paper" with **Upload a file** (an open-access paper) and with **A web page**; review, accept | drafts from any source, never shown before review (V4 to V7) |
| 6:00 | admin | accounts from term to term, end of term export and import into a new course | runs year after year (V9) |
| 6:40 | — | architecture slide (docs/diagrams), cost slide (GPU_COST.md), what comes next (extension-points.md) | the value for future teams and research |

Backup: screenshots of each step in case the network or the GPU fails; the video is the fallback for the live
demo.
