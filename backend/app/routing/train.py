"""Train portable calibrated LR/SVM heads on local sentence embeddings.

The bundled seed labels describe intended routing policy, NOT measured Qwen success.
Replace cloud_required labels with independently graded local-model outcomes before
claiming a capability benchmark. Paraphrases must share a `group` identifier.
"""

import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from app.core.config import REPO_ROOT, get_settings
from app.routing.methods import estimator
from app.routing.models import HEADS, encode, weights_path


def read_rows(path: Path) -> list[dict]:
    rows = [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]
    if len(rows) < 20:
        raise ValueError("At least 20 independently grouped examples are required")
    seen = set()
    for row in rows:
        if not row.get("question", "").strip() or not row.get("group"):
            raise ValueError("Every row needs question and paraphrase group")
        key = row["question"].strip().casefold()
        if key in seen:
            raise ValueError("Duplicate training question")
        seen.add(key)
        for head in HEADS:
            if type(row.get(head)) is not int or row[head] not in (0, 1):
                raise ValueError(f"Every row needs binary {head}")
        if row["requires_fresh_evidence"] and not row["requires_evidence"]:
            raise ValueError("Freshness implies evidence is required")
    return rows


def fit_heads(x: np.ndarray, rows: list[dict], method: str):
    from sklearn.calibration import CalibratedClassifierCV
    from sklearn.model_selection import StratifiedGroupKFold

    models = {}
    groups = [r["group"] for r in rows]
    for head in HEADS:
        y = np.array([r[head] for r in rows])
        cv = list(StratifiedGroupKFold(n_splits=3, shuffle=True, random_state=42).split(x, y, groups))
        if any(len(set(y[a])) < 2 or len(set(y[b])) < 2 for a, b in cv):
            raise ValueError(f"Need more independent groups of both classes for {head}")
        model = CalibratedClassifierCV(estimator=estimator(method), method="sigmoid", cv=cv)
        model.fit(x, y)
        models[head] = model
    return models


def portable_arrays(models: dict, prototypes: np.ndarray) -> dict:
    arrays = {"prototypes": prototypes.astype(np.float32)}
    for head, model in models.items():
        folds = model.calibrated_classifiers_
        arrays[f"{head}_coef"] = np.stack([f.estimator.coef_[0] for f in folds])
        arrays[f"{head}_intercept"] = np.array([f.estimator.intercept_[0] for f in folds])
        arrays[f"{head}_a"] = np.array([f.calibrators[0].a_ for f in folds])
        arrays[f"{head}_b"] = np.array([f.calibrators[0].b_ for f in folds])
    return arrays


def train(data: Path, methods: list[str], allow_download=False, label_origin="prototype_policy"):
    from sklearn.metrics import accuracy_score, brier_score_loss, recall_score
    from sklearn.model_selection import GroupShuffleSplit

    cfg = get_settings().routing
    rows = read_rows(data)
    x = encode([r["question"] for r in rows], cfg, allow_download=allow_download)
    a, b = next(
        GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(
            x, groups=[r["group"] for r in rows]
        )
    )
    report = {
        "label_origin": label_origin,
        "rows": len(rows),
        "heldout_rows": len(b),
        "warning": "Policy-label holdout is NOT a benchmark of local LLM answer quality.",
        "split": "GroupShuffleSplit by paraphrase group; calibration uses separate group folds",
        "methods": {},
    }
    for method in methods:
        fitted = fit_heads(x[a], [rows[int(i)] for i in a], method)
        metrics = {}
        for head, model in fitted.items():
            y = np.array([rows[int(i)][head] for i in b])
            p = model.predict_proba(x[b])[:, 1]
            metrics[head] = {
                "accuracy": float(accuracy_score(y, p >= 0.5)),
                "positive_recall": float(recall_score(y, p >= 0.5, zero_division=0)),
                "brier": float(brier_score_loss(y, p)),
            }
        report["methods"][method] = metrics
        models = fit_heads(x, rows, method)
        metadata = {
            "schema_version": 1,
            "method": method,
            "embedding_model": cfg.embedding_model,
            "dimension": int(x.shape[1]),
            "label_origin": label_origin,
            "training_count": len(rows),
            "dataset_sha256": hashlib.sha256(data.read_bytes()).hexdigest(),
        }
        path = weights_path(cfg, method)
        path.parent.mkdir(parents=True, exist_ok=True)
        # No pickle/joblib deserialization and no sklearn-version-dependent runtime object.
        np.savez_compressed(path, metadata=np.array(json.dumps(metadata)), **portable_arrays(models, x))
        print(f"Saved {method}: {path}")
    path.parent.joinpath("training_report.json").write_text(
        json.dumps(report, indent=2) + "\n", encoding="utf-8"
    )
    return report


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--data", type=Path, default=REPO_ROOT / "data/routing/seed.jsonl")
    parser.add_argument("--methods", nargs="+", choices=["lr", "svm"])
    parser.add_argument("--allow-download", action="store_true")
    parser.add_argument("--label-origin", default="prototype_policy")
    args = parser.parse_args()
    report = train(
        args.data,
        args.methods or get_settings().routing.enabled_methods,
        args.allow_download,
        args.label_origin,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
