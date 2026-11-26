# Routing heads for biomedical_engineering (X10)

154 questions (`data/routing/bme_questions.jsonl`), held-out 56 (30% of the paraphrase groups, seed 42). Route = the capability gate of SemanticRouter; label: cloud iff `cloud_required`.

| Method | Heads | Accuracy | Accuracy, mean of 10 splits | Cloud share (label) | Cloud recall | Local recall | Outside support | Evidence head |
|---|---|---|---|---|---|---|---|---|
| lr | shared | 0.661 | 0.733 | 0.196 (0.214) | 0.167 | 0.795 | 0.196 | 0.875 |
| lr | own | 0.946 | 0.917 | 0.196 (0.214) | 0.833 | 0.977 | 0.0 | 0.911 |
| svm | shared | 0.661 | 0.744 | 0.196 (0.214) | 0.167 | 0.795 | 0.196 | 0.875 |
| svm | own | 1.0 | 0.937 | 0.214 (0.214) | 1.0 | 1.0 | 0.0 | 0.929 |
