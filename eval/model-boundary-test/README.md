# Local model capability boundary benchmark

This historical benchmark studies which kinds of educational questions different
sizes of **locally hosted** LLMs can answer reliably. It is not the v4 production
course retrieval or privacy evaluation.

## Quick start

On the GPU server, configure Ollama to listen on the intended trusted interface,
then install the test models:

```bash
bash pull_models.sh
```

On Windows, use `pull_models.ps1`. From the developer workstation:

```bash
python bench.py --models qwen3.5:4b --limit 5 --out results/smoke.jsonl
python bench.py --models qwen3.5:4b qwen3.5:9b qwen3.5:27b --think on
python grade.py
python report.py
```

The smoke test checks basic execution. The full run tests model sizes, formats,
reasoning, answer quality and latency. See [TEST_PLAN.md](TEST_PLAN.md)
for the experimental design, thresholds and review procedures.

## Result interpretation

- The benchmark includes several dimensions of educational difficulty.
- Multiple-choice, numeric, short and format-rule items can be graded
  automatically; open items require independent manual or model-assisted
  review.
- A model passing a narrow benchmark cell is not sufficient evidence that
  it is safe for clinical decisions or for unrestricted student-facing use.
- Chinese-language benchmark cases are historical internationalization
  test fixtures; their source files use Unicode escape notation to satisfy
  the repository's English-only source-text policy while preserving the
  original runtime input.
- Scores should be reported with versioned model configurations and caveats.
