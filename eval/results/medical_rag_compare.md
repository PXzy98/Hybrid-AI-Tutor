# Medical RAG baseline vs hybrid — anchor retrieval

Small, manually authored checks against exact source phrases (not gold chunk judgments or clinical validation).

| Retriever | Hit@1 | Hit@4 | MRR@4 | Mean ms | P95 ms |
|---|---:|---:|---:|---:|---:|
| baseline | 55.0% | 90.0% | 0.688 | 0.46 | 0.63 |
| hybrid | 75.0% | 95.0% | 0.838 | 4.45 | 5.95 |

## Hybrid misses in Top-4
- migraine: What can help during a migraine attack without medicine? (anchor: quiet, darkened room)
