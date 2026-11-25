"""X10: routing heads for the biomedical engineering course type, before and after (no hosted model).

Rows: `data/routing/bme_questions.jsonl` (make_questions.py; labels by category, prototype_policy). The
held-out share is 30% of the paraphrase groups (GroupShuffleSplit, seed 42), so a question and its paraphrase
are never split. Compared on it, with the capability gate of SemanticRouter (eval/routing-ece/run.py
`decide`):

    shared    the shipped heads (`data/routing/models`, trained on medical questions): what a
              biomedical_engineering course gets without its own folder
    own       heads fitted on seed.jsonl + the training share of the BME rows

`--write` then fits on seed.jsonl + every BME row and writes `data/routing/models/biomedical_engineering/`
through app.routing.train (the format the app loads, V19).

    .venv\\Scripts\\python eval\\routing-bme\\run.py [--write]
"""
import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.routing.models import encode, load_weights  # noqa: E402
from app.routing.train import read_rows, train  # noqa: E402

_spec = importlib.util.spec_from_file_location("routing_ece", ROOT / "eval" / "routing-ece" / "run.py")
ece = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(ece)

HERE = Path(__file__).resolve().parent
DATA = ROOT / "data" / "routing"
TYPE = "biomedical_engineering"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--write", action="store_true", help="write data/routing/models/biomedical_engineering/")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args()
    from sklearn.model_selection import GroupShuffleSplit

    cfg = get_settings().routing
    seed = read_rows(DATA / "seed.jsonl")
    bme = read_rows(DATA / "bme_questions.jsonl")
    seed_x = encode([r["question"] for r in seed], cfg)
    bme_x = encode([r["question"] for r in bme], cfg)
    train_idx, test_idx = next(GroupShuffleSplit(n_splits=1, test_size=0.3, random_state=42).split(
        bme_x, groups=[r["group"] for r in bme]))
    test_rows, test_x = [bme[i] for i in test_idx], bme_x[test_idx]
    report: dict = {"rows": len(bme), "held_out": len(test_rows), "methods": {}}
    for method in ece.METHODS:
        metadata, arrays = load_weights(cfg, method)  # the shared heads
        shared = ece.predict(test_x, metadata, arrays, cfg)
        import numpy as np

        rows = seed + [bme[i] for i in train_idx]
        x = np.vstack([seed_x, bme_x[train_idx]])
        own_meta, own_arrays = ece.fit_arrays(x, rows, method, cfg)
        own = ece.predict(test_x, own_meta, own_arrays, cfg)
        report["methods"][method] = {
            "shared": ece.score(test_rows, shared), "own": ece.score(test_rows, own),
            "by_category": {"shared": ece.grouped(test_rows, shared, lambda r: r["category"]),
                            "own": ece.grouped(test_rows, own, lambda r: r["category"])}}
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "metrics.json").write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    lines = ["# Routing heads for biomedical_engineering (X10)", "",
             f"{len(bme)} questions (`data/routing/bme_questions.jsonl`), held-out {len(test_rows)} "
             "(30% of the paraphrase groups). Route = the capability gate of SemanticRouter; label: cloud "
             "iff `cloud_required`.", "",
             "| Method | Heads | Accuracy | Cloud share (label) | Cloud recall | Local recall "
             "| Outside support |"
             " Evidence head |", "|---|---|---|---|---|---|---|---|"]
    for method, m in report["methods"].items():
        for name in ("shared", "own"):
            s = m[name]
            lines.append(f"| {method} | {name} | {s['accuracy']} "
                         f"| {s['cloud_share']} ({s['label_cloud_share']}) | {s['cloud_recall']} "
                         f"| {s['local_recall']} | {s['unreliable_share']} | {s['evidence_head_accuracy']} |")
    (a.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    if a.write:
        with tempfile.TemporaryDirectory() as tmp:
            data = Path(tmp) / "train.jsonl"
            data.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in seed + bme),
                            encoding="utf-8")
            train(data, list(cfg.enabled_methods), False, "prototype_policy", TYPE)
    return 0


if __name__ == "__main__":
    sys.exit(main())
