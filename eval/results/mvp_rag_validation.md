# MVP RAG: independently isolated upload fixture

**Synthetic educational texts only.** The 10 manually labelled examples are a
small engineering diagnostic; not blind, clinician-reviewed, real-student or
held-out production data. Each question has exactly one gold passage.
The retriever also contains the five built-in MedlinePlus texts.

- Uploaded documents: 10; indexed passages: 10
- Labelled questions: 10; unrelated negative queries: 2
- Recall@1: 100.0%; Recall@4: 100.0%
- Precision@1: 100.0%; Precision@4: 25.0%
- MRR@4: 1.000
- Source traceability (returned chunks): 100.0%
- Mean / p95 retrieval latency: 2.55 / 4.34 ms (index construction excluded)

Precision@4 is capped at 25% when one gold passage is annotated per query;
other potentially useful chunks are conservatively counted as nonrelevant.
Scores cannot be generalized to actual professor materials.

| ID | Topic | Rank | Retrieved | P@4 | Milliseconds |
|---|---|---:|---:|---:|---:|
| C01 | high_blood_pressure | 1 | 3 | 0.25 | 2.68 |
| C02 | high_blood_pressure | 1 | 4 | 0.25 | 4.64 |
| C03 | asthma | 1 | 1 | 0.25 | 1.95 |
| C04 | asthma | 1 | 1 | 0.25 | 1.79 |
| C05 | type2_diabetes | 1 | 2 | 0.25 | 1.89 |
| C06 | type2_diabetes | 1 | 4 | 0.25 | 4.34 |
| C07 | migraine | 1 | 2 | 0.25 | 2.15 |
| C08 | migraine | 1 | 1 | 0.25 | 1.86 |
| C09 | pneumonia | 1 | 2 | 0.25 | 1.98 |
| C10 | pneumonia | 1 | 3 | 0.25 | 2.18 |

## Deliberately unrelated inputs
- asthma: abstained=True; returned=0
- migraine: abstained=True; returned=0

## Interpretation
- The labelled excerpt and matching document must both be returned.
- Passage scores are not probabilities of medical correctness.
- Labels, permissions, source freshness and medical safety require human review.
- Re-run with educator-approved course content and independent gold judgements.
