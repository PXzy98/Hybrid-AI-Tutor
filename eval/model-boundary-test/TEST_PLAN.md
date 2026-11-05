# Local Small-Model Capability Boundary: Evaluation Plan

**Project:** Privacy-Aware Hybrid AI Tutor (ELG 5902, Group 1).
**Scope:** Offline model capability and reasoning assessment, **without RAG or PII
filtering**. This is a historical experiment rather than a clinical benchmark.

## 1. Research question

Determine how question type, difficulty and model size influence accuracy,
format compliance, response latency and thinking-token requirements.
The historical test server uses Ollama and an RTX 2080 Ti with 22 GB VRAM.
Actual model availability and fit must be checked on the server.

## 2. Dimensions and levels

Questions cover knowledge and factual recall, calculations and reasoning,
conceptual application, advanced reasoning, and instruction following.
Difficulty levels progress from direct recall or single-step questions
to multistep problems, structured JSON/classification, adversarial premises,
open-ended system design and constrained educational responses.

The dataset contains 110 cases with five questions per dimension/level cell,
so a result of four correct out of five is only a rough boundary estimate.
Cross-language cases are included solely to test model robustness and should
not be interpreted as support for a Chinese-language project UI.

| Type | Count | Evaluation |
|---|---:|---|
| Multiple choice (`mcq`) | 55 | Last `ANSWER: X` line |
| Numeric | 25 | Numeric tolerance, including valid percentage equivalents |
| Short answer | 5 | Keyword matching |
| Rule/format | 19 | Code checks for syntax, sentence/word count, lists and JSON |
| Open answer | 6 | Independent manual or evaluator-model review |

## 3. Historical candidate models

The original study compared Qwen3.5 models (2B, 4B, 9B and 27B),
Gemma family variants (including e4b, 12b and 26b), and optional
smaller/larger candidates. The original storage estimates were based on
October 2026 Ollama releases and are not guaranteed current.

Run different model sizes within a family first, then compare another family
to distinguish a scaling effect from architectural differences.

## 4. Experimental settings

- Temperature: 0 for repeatability; use 0.6 for the stability round.
- Context: 4,096 tokens, since no retrieval context is attached.
- Output budget: approximately 2,048 tokens without thinking and 8,192
  with thinking, subject to model-specific limits.
- System instruction: return a final `ANSWER: ...` line for automated grading.
- Record format errors, incomplete/truncated answers and max-token hits.
- Use the same dataset, scoring rule and configuration across models.

## 5. Execution stages

1. **Smoke:** one small model and five questions:
   `python bench.py --models qwen3.5:4b --limit 5 --out results/smoke.jsonl`.
2. **Primary comparison:** 2B/4B/9B/27B and selected Gemma models,
   with thinking disabled.
3. **Thinking effect:** rerun representative sizes with `--think on`.
4. **Boundary stability:** for cells at 60–80% accuracy, repeat at
   least three times with temperature 0.6.
5. **Scoring:** `python grade.py`; manually review six open questions
   using `results/manual_review.csv`, then `python report.py`.

The original plan contained approximate runtime budgets for the historical
hardware. Actual times depend on model load, GPU offload and output length.

## 6. Capability boundary definition

A cell passes if at least 80% of its questions are correct. A boundary
is the highest contiguous passing difficulty level starting at L1.
Also report `format_ok`, `hit_max_tokens`, response latency and
incorrectly accepted false premises. At five items per cell, statistical
uncertainty is high and results should be repeated.

## 7. Implications for the tutor

- Use measured local capability limitations to guide routing rather than
  assuming cloud is always better.
- Prefer small local models for structured classification only if JSON,
  precision and latency requirements are actually satisfied.
- A larger or MoE model may offer a different throughput/quality tradeoff;
  measure actual GPU offload before comparing speed.
- A failure on false-premise questions reinforces the need for grounded
  retrieval, verification and abstention.
- Language differences belong in the benchmark report, not in the project's
  source-code or documentation language policy.

## 8. Follow-up

1. Repeat with approved course RAG to assess how sources change capability.
2. Assess sensitive-but-complex questions inside the authorized local boundary.
3. Replace fictional questions with instructor-approved course materials
   and obtain qualified reviewers before presenting real-course conclusions.
