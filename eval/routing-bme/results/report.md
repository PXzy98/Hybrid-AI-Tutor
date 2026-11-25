# Routing heads for biomedical_engineering (X10)

154 questions (`data/routing/bme_questions.jsonl`), held-out 48 (30% of the paraphrase groups). Route = the capability gate of SemanticRouter; label: cloud iff `cloud_required`.

| Method | Heads | Accuracy | Cloud share (label) | Cloud recall | Local recall | Outside support | Evidence head |
|---|---|---|---|---|---|---|---|
| lr | shared | 0.75 | 0.208 (0.208) | 0.4 | 0.842 | 0.208 | 0.896 |
| lr | own | 0.896 | 0.146 (0.208) | 0.6 | 0.974 | 0.021 | 0.958 |
| svm | shared | 0.75 | 0.208 (0.208) | 0.4 | 0.842 | 0.208 | 0.896 |
| svm | own | 0.896 | 0.188 (0.208) | 0.7 | 0.947 | 0.021 | 0.917 |
