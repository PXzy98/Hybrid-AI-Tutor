# Capability boundary test plan for small local models

**Project**: Privacy-Aware Hybrid AI Tutor (ELG 5902, Group 1)
**Scope of this round**: no RAG and no PII handling. Only one question: **which types and difficulty levels of
questions can local models of different sizes still answer correctly?**
**Hardware**: Ollama server `192.168.2.25`, RTX 2080 Ti 22GB

---

## 1. Questions to answer

1. Up to which difficulty level (the "boundary") does each model reach for each question type?
2. As models get larger, which question types improve most, and which stay poor?
3. How far does thinking mode push the boundary up, and at what latency cost?
4. Does asking in Chinese lower accuracy?
5. Can small models reliably follow an output format (for example JSON)? This decides whether they can serve
   as a router or classifier.

The results feed directly into the routing rules: **question types beyond the local model's boundary go to the
cloud.**

## 2. Test set design (`data/boundary_set.jsonl`, 110 questions)

5 dimensions × 4 levels × 5 questions per cell = 100 questions, plus 10 Chinese/English paired questions. All
questions are about medical AI / health informatics.

| Dimension | L1 | L2 | L3 | L4 |
|---|---|---|---|---|
| **Knowledge** | common terms (CT, EHR) | standard course concepts (FHIR, ICD-10, k-fold) | specific details (HU values, DICOM tags, LOINC) | obscure facts + **false-premise traps** (papers or standards that do not exist, to test whether the model makes things up) |
| **Concept** | definitions | comparing two concepts | applying to a concrete case | common misconceptions (what AUC means, how class weights affect calibration) |
| **Calculation** | one formula | two steps | several steps (Bayes, kappa, likelihood ratios) | long chains (two tests in a row, sample size, cost) |
| **Applied reasoning** | obvious errors | data leakage, overfitting | domain shift, temporal leakage, subgroup differences | hidden leakage, capacity constraints, Simpson's paradox, open design |
| **Instruction following** | one constraint (one sentence, answer only Yes) | structure constraints (3 bullet points, word limit) | several constraints, **JSON output**, router-style classification | Socratic tutoring (must not give the answer), refusing to help cheat, strict formats |

**Grading** (104 of the 110 questions are graded automatically):

| Type | Count | Grading |
|---|---|---|
| Multiple choice `mcq` | 55 | reads the last line `ANSWER: X`; option positions are shuffled |
| Numeric `numeric` | 25 | with a tolerance (mostly ±2%); percentages are accepted |
| Short answer `short` | 5 | keyword matching |
| Rule `rule` | 19 | the format is checked by code (words, sentences, bullet points, JSON, language, ...) |
| Open `open` | 6 | scored by an LLM judge or by hand (only 6 questions per model, about 5 minutes by hand) |

Each cell has only 5 questions, so "80% passed" means 4 of 5 correct and a single run has some randomness. See
round 3 in section 5.

## 3. Models to prepare in Ollama

Model information from ollama.com (October 2026). Sizes are the download sizes at the default Q4 quantization;
the KV cache comes on top at run time. Without RAG in this round, `num_ctx=4096` is enough.

### Required (main ladder)

Different sizes of one family (Qwen3.5) show the effect of model size alone; a second family (Gemma 4) cross-checks.

| Model | Parameters | Approx. size | On 22GB | Role |
|---|---|---|---|---|
| `qwen3.5:2b` | 2B | ~2.7 GB | ✅ easy | very small model, possible router |
| `qwen3.5:4b` | 4B | ~3.4 GB | ✅ easy | small model |
| `qwen3.5:9b` | 9B | ~6.6 GB | ✅ easy | medium model, possible default local model |
| `qwen3.5:27b` | 27B dense | ~17 GB | ✅ fits | the largest dense model this card can run |
| `gemma4:e4b` | 4.5B effective | ~7–9.5 GB | ✅ easy | cross-family check: small model |
| `gemma4:12b` | 12B | ~8 GB | ✅ easy | cross-family check: medium model |
| `gemma4:26b` | 25B MoE (about 3.8B active) | ~16–19 GB | ✅ fits | **key**: MoE model, speed close to a small model, quality possibly close to a large one |

About 65 GB of disk is needed.

### Optional (if time allows)

| Model | Note |
|---|---|
| `qwen3.5:0.8b` | finds the lower bound, about 1 GB |
| `gemma4:e2b` | the smallest Gemma |
| `gemma4:31b` | 31B dense, 19–20 GB, very tight. If `ollama ps` does not show 100% GPU, do not continue |
| `qwen3.8:27b` | the newest Qwen 27B on Ollama. Compared with qwen3.5:27b it shows how much the new generation improved |
| `qwen3.5:35b` | 35B-A3B MoE, about 22 GB, **part of it always runs on the CPU**. Only a quality reference; its speed is not a result |

Pull the models with `pull_models.sh` (Linux) or `pull_models.ps1` (Windows), run on the server.

## 4. Test settings

| Setting | Value | Reason |
|---|---|---|
| temperature | 0 (0.6 in round 3) | reproducible results |
| num_ctx | 4096 | no RAG, the questions are short |
| max output | 2048 tokens (8192 with thinking) | stops small models from looping forever; hitting the limit is recorded |
| thinking | off by default, tested separately in round 2 | separates the model's own ability from what thinking adds |
| system prompt | asks for a last line `ANSWER: ...` | easy automatic grading; a wrong format is itself a metric |

## 5. Steps

| Round | Content | Command | Expected time |
|---|---|---|---|
| 0 | smoke test | `python bench.py --models qwen3.5:4b --limit 5 --out results/smoke.jsonl` | 2 minutes |
| 1 | **all required models, thinking off** | `python bench.py --models qwen3.5:2b qwen3.5:4b qwen3.5:9b gemma4:e4b gemma4:12b gemma4:26b qwen3.5:27b` | 2–3 hours, 27B is slowest |
| 2 | effect of thinking | `python bench.py --models qwen3.5:4b qwen3.5:9b qwen3.5:27b --think on` | 3–6 hours, can run overnight |
| 3 | stability near the boundary | for models near the boundary (60–80%) in round 1: `--repeats 3 --temperature 0.6` | as needed |
| 4 | grading and report | `python grade.py`, grade the 6 open questions in `results/manual_review.csv`, then `python report.py` | 30 minutes |

## 6. How the "boundary" is decided

- **Pass per cell**: accuracy ≥ 80% (adjustable with `--pass`).
- **Boundary**: the highest level passed continuously from L1. For example, if L1 and L2 pass and L3 does not,
  the boundary is L2.
- **Other metrics**:
  - `format_ok`: whether the model writes the `ANSWER:` line as asked. A low value means the model is not
    suited to work that needs structured output (such as a router).
  - `hit_max_tokens`: how often the output hit the limit. Many hits mean the model looped, common for small
    models with thinking on.
  - The false-premise questions of Knowledge L4: a wrong answer means the model **makes things up**. For
    teaching this is a serious problem.
  - The accuracy difference on the Chinese/English paired questions.

## 7. How the results are used in the project

| Result | Effect on the design |
|---|---|
| A model's Calculation boundary is L2 | multi-step calculations (L3 and above) are routed to the cloud |
| A 2B/4B model passes Instruction following L3 (JSON, classification) | that small model can serve as the router and meet the ≤0.5 s latency target |
| The MoE model (gemma4:26b) has about the same boundary as the 27B dense model but is much faster | choose it as the default local model |
| No local model passes the false-premise questions of Knowledge L4 | made-up content must be controlled by RAG and the answer verification module, which also shows why the next round tests RAG |
| Accuracy is clearly lower in Chinese | Chinese questions go to the cloud first, or choose a model better at Chinese |

## 8. Next steps (after this round)

1. Add RAG with the same method and see how much the boundary rises once course material is given.
2. Add the PII questions (in the previous version of the test set) to test how far "sensitive but complex"
   questions can be handled locally.
3. Once Dr. Abbas provides course material, replace the synthetic questions with real course questions.
