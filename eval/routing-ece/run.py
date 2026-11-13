"""T4: routing evaluation on ECE and computer science questions (no hosted model, no answer generation).

`data/routing/ece_cs_questions.jsonl` holds questions written from the four ECE/CS course packs of
`data/demo_courses/`, labelled with the labelling rule of `data/routing/seed.jsonl` (cloud_required,
requires_evidence, requires_fresh_evidence; `label_origin` prototype_policy: intended policy, not measured
local-model ability). Rows whose label depends on a model judgement are marked `uncertain` and left out of the
accuracy figures (they are listed in the report).

1. Shipped routers (`data/routing/models`, lr and svm): the capability gate of `SemanticRouter` (route is cloud
   unless the question is in the training support and cloud_probability < threshold - margin), compared with
   the label (cloud iff cloud_required). The evidence step needs the course index and the cross-encoders and is
   not simulated; the evidence head is reported on its own.
2. Retraining experiment (in memory, shipped files untouched): seed training split + a training share of the
   new rows, evaluated on the held-out share of the new rows and on the seed hold-out of the training script
   (GroupShuffleSplit 0.2, seed 42), plus leave-one-pack-out.

Usage (repository root): python eval/routing-ece/run.py [--out DIR] [--save-candidate]
`--save-candidate` also fits on seed + all new rows and writes the weights next to the report (never to
`data/routing/models`).
"""
import argparse
import json
import sys
from collections import Counter, defaultdict
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.routing.models import HEADS, encode, load_weights, predict_heads  # noqa: E402
from app.routing.train import fit_heads, portable_arrays, read_rows  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analysis_text import ANALYSIS  # noqa: E402

DATA = ROOT / "data" / "routing"
METHODS = ("lr", "svm")
TYPES = ("concept", "application", "hard", "logistics", "current")


def decide(values: dict, cfg) -> dict:
    """The capability gate of SemanticRouter.capable (same thresholds)."""
    reliable = values["nearest_similarity"] >= cfg.ood_similarity_threshold
    capable = reliable and values["cloud_required"] < max(0, cfg.threshold - cfg.uncertainty_margin)
    reason = "local" if capable else ("cloud: unreliable (outside training support)" if not reliable
                                      else "cloud: capability score")
    return {"route": "local" if capable else "cloud", "reason": reason,
            "head_route": "cloud" if values["cloud_required"] >= 0.5 else "local", **values}


def predict(x: np.ndarray, metadata: dict, arrays: dict, cfg) -> list[dict]:
    return [decide(predict_heads(v, metadata, arrays), cfg) for v in x]


def fit_arrays(x: np.ndarray, rows: list[dict], method: str, cfg):
    models = fit_heads(x, rows, method)
    metadata = {"schema_version": 1, "method": method, "embedding_model": cfg.embedding_model,
                "dimension": int(x.shape[1]), "label_origin": "prototype_policy",
                "training_count": len(rows)}
    return metadata, portable_arrays(models, x)


def score(rows: list[dict], preds: list[dict]) -> dict:
    """Accuracy of the route against cloud_required, confusion matrix, cloud share, evidence head accuracy."""
    n = len(rows)
    if not n:
        return {"n": 0}
    truth = ["cloud" if r["cloud_required"] else "local" for r in rows]
    got = [p["route"] for p in preds]
    head = [p["head_route"] for p in preds]
    conf = Counter(zip(truth, got, strict=True))
    cloud_pos = [i for i, t in enumerate(truth) if t == "cloud"]
    local_pos = [i for i, t in enumerate(truth) if t == "local"]
    return {
        "n": n,
        "accuracy": round(sum(t == g for t, g in zip(truth, got, strict=True)) / n, 3),
        "head_only_accuracy": round(sum(t == g for t, g in zip(truth, head, strict=True)) / n, 3),
        "cloud_share": round(got.count("cloud") / n, 3),
        "label_cloud_share": round(truth.count("cloud") / n, 3),
        "cloud_recall": round(sum(got[i] == "cloud" for i in cloud_pos) / len(cloud_pos), 3)
        if cloud_pos else None,
        "local_recall": round(sum(got[i] == "local" for i in local_pos) / len(local_pos), 3)
        if local_pos else None,
        "confusion": {"local->local": conf[("local", "local")], "local->cloud": conf[("local", "cloud")],
                      "cloud->local": conf[("cloud", "local")], "cloud->cloud": conf[("cloud", "cloud")]},
        "unreliable_share": round(sum(p["reason"].startswith("cloud: unrel") for p in preds) / n, 3),
        "evidence_head_accuracy": round(sum((p["requires_evidence"] >= 0.35) == bool(r["requires_evidence"])
                                            for r, p in zip(rows, preds, strict=True)) / n, 3),
    }


def grouped(rows: list[dict], preds: list[dict], key) -> dict:
    buckets = defaultdict(lambda: ([], []))
    for r, p in zip(rows, preds, strict=True):
        buckets[key(r)][0].append(r)
        buckets[key(r)][1].append(p)
    return {k: score(*v) for k, v in sorted(buckets.items())}


def split_new(rows: list[dict], share: float = 0.4):
    """Deterministic hold-out of `share` of each (pack, type) cell: every 5th row goes to a 2-of-5 test share."""
    test = []
    per_cell = Counter()
    for i, r in enumerate(rows):
        cell = (r["pack"], r["type"])
        per_cell[cell] += 1
        test.append(per_cell[cell] % 5 in (2, 4))  # 2 of every 5 rows of a cell
    train_idx = [i for i, t in enumerate(test) if not t]
    test_idx = [i for i, t in enumerate(test) if t]
    return train_idx, test_idx


def experiment(seed_rows, seed_x, new_rows, new_x, cfg) -> dict:
    from sklearn.model_selection import GroupShuffleSplit

    a, b = next(GroupShuffleSplit(n_splits=1, test_size=0.2, random_state=42).split(
        seed_x, groups=[r["group"] for r in seed_rows]))
    seed_tr, seed_te = [seed_rows[i] for i in a], [seed_rows[i] for i in b]
    tr_idx, te_idx = split_new(new_rows)
    new_tr = [new_rows[i] for i in tr_idx]
    new_te = [new_rows[i] for i in te_idx if not new_rows[i]["uncertain"]]
    new_te_x = new_x[[i for i in te_idx if not new_rows[i]["uncertain"]]]
    out = {"new_train": len(new_tr), "new_test": len(new_te), "seed_train": len(seed_tr),
           "seed_test": len(seed_te), "methods": {}, "leave_one_pack_out": {}}
    packs = sorted({r["pack"] for r in new_rows})
    for method in METHODS:
        res = {}
        base = fit_arrays(seed_x[a], seed_tr, method, cfg)
        plus_x = np.vstack([seed_x[a], new_x[tr_idx]])
        plus = fit_arrays(plus_x, seed_tr + new_tr, method, cfg)
        for name, (meta, arr) in (("seed_only", base), ("seed_plus_new", plus)):
            res[name] = {"new_test": score(new_te, predict(new_te_x, meta, arr, cfg)),
                         "seed_test": score(seed_te, predict(seed_x[b], meta, arr, cfg))}
        out["methods"][method] = res
        lopo = {}
        for held in packs:
            tr = [i for i, r in enumerate(new_rows) if r["pack"] != held]
            te = [i for i, r in enumerate(new_rows) if r["pack"] == held and not r["uncertain"]]
            meta, arr = fit_arrays(np.vstack([seed_x[a], new_x[tr]]), seed_tr + [new_rows[i] for i in tr],
                                   method, cfg)
            lopo[held] = score([new_rows[i] for i in te], predict(new_x[te], meta, arr, cfg))
        out["leave_one_pack_out"][method] = lopo
    return out


def fmt(v) -> str:
    return "-" if v is None else f"{v:.2f}"


def table(title: str, groups: dict) -> list[str]:
    lines = [f"**{title}**", "", "| Group | n | accuracy | cloud share | label cloud share | cloud recall | "
             "local recall | unreliable | evidence head acc |", "|---|---|---|---|---|---|---|---|---|"]
    for k, s in groups.items():
        lines.append(f"| {k} | {s['n']} | {fmt(s['accuracy'])} | {fmt(s['cloud_share'])} | "
                     f"{fmt(s['label_cloud_share'])} | {fmt(s['cloud_recall'])} | {fmt(s['local_recall'])} | "
                     f"{fmt(s['unreliable_share'])} | {fmt(s['evidence_head_accuracy'])} |")
    return lines + [""]


def write_report(res: dict, path: Path) -> None:
    L = ["# Routing evaluation on ECE and computer science questions (T4)", "",
         f"{res['rows']} questions written from the packs `mit_6_002_circuits`, `mit_res_6_007_signals`, "
         f"`mit_6_006_algorithms`, `harvard_cs50x` (40 each; kinds: concept, application, hard, logistics, "
         f"current) and labelled with the seed labelling rule. {res['uncertain']} rows are `uncertain` (the "
         "label depends on a model judgement: all current-information rows and a few borderline derivations) "
         f"and are excluded from the figures: {res['scored']} rows are scored. Labels are intended policy "
         "(`prototype_policy`), not measured local-model ability. *Route* is the capability gate of "
         "`SemanticRouter` (cloud when the question is outside the training support or cloud_probability >= "
         "0.52), *accuracy* compares it with the label (cloud iff `cloud_required`); the evidence step "
         "(course index plus cross-encoders) is not simulated.", ""]
    for method in METHODS:
        m = res["shipped"][method]
        L += [f"## Shipped {method.upper()} router", ""]
        L += table("All scored rows", {"all": m["all"]}) + table("Per pack", m["by_pack"]) \
            + table("Per type", m["by_type"])
        c = m["all"]["confusion"]
        L += [f"Confusion (label -> route): local->local {c['local->local']}, local->cloud {c['local->cloud']}, "
              f"cloud->local {c['cloud->local']}, cloud->cloud {c['cloud->cloud']}. Head only (no unreliability "
              f"gate, cloud_probability >= 0.5): accuracy {fmt(m['all']['head_only_accuracy'])}.", ""]
    ex = res["experiment"]
    L += ["## Retraining experiment (in memory)", "",
          f"Seed training split ({ex['seed_train']} rows) alone versus plus the training share of the new data "
          f"({ex['new_train']} rows); evaluated on the held-out new rows ({ex['new_test']} scored) and on the seed "
          f"hold-out of the training script ({ex['seed_test']} rows). Shipped files are not touched.", ""]
    for method in METHODS:
        L += [f"**{method.upper()}**", "", "| Training data | new held-out accuracy | new cloud share | new local recall | "
              "new cloud recall | seed held-out accuracy | seed cloud share |", "|---|---|---|---|---|---|---|"]
        for name, label in (("seed_only", "seed only"), ("seed_plus_new", "seed + new")):
            r = ex["methods"][method][name]
            L.append(f"| {label} | {fmt(r['new_test']['accuracy'])} | {fmt(r['new_test']['cloud_share'])} | "
                     f"{fmt(r['new_test']['local_recall'])} | {fmt(r['new_test']['cloud_recall'])} | "
                     f"{fmt(r['seed_test']['accuracy'])} | {fmt(r['seed_test']['cloud_share'])} |")
        L.append("")
        L += ["Leave-one-pack-out (seed train + the other three packs, tested on the fourth):", "",
              "| Held-out pack | accuracy | cloud share | local recall | cloud recall |", "|---|---|---|---|---|"]
        for pack, s in ex["leave_one_pack_out"][method].items():
            L.append(f"| {pack} | {fmt(s['accuracy'])} | {fmt(s['cloud_share'])} | {fmt(s['local_recall'])} | "
                     f"{fmt(s['cloud_recall'])} |")
        L.append("")
    L += ["## Uncertain rows (not scored)", ""] + [f"- `{i}`" for i in res["uncertain_ids"]] + [""]
    L += ["", ANALYSIS.rstrip(), ""]
    path.write_text("\n".join(L) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=HERE / "results")
    parser.add_argument("--save-candidate", action="store_true")
    args = parser.parse_args()
    cfg = get_settings().routing
    new_rows = [json.loads(line) for line in (DATA / "ece_cs_questions.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    seed_rows = read_rows(DATA / "seed.jsonl")
    new_x = encode([r["question"] for r in new_rows], cfg)
    seed_x = encode([r["question"] for r in seed_rows], cfg)
    scored_idx = [i for i, r in enumerate(new_rows) if not r["uncertain"]]
    scored = [new_rows[i] for i in scored_idx]
    res = {"rows": len(new_rows), "uncertain": len(new_rows) - len(scored), "scored": len(scored),
           "uncertain_ids": [r["id"] for r in new_rows if r["uncertain"]], "shipped": {}}
    for method in METHODS:
        meta, arr = load_weights(cfg, method)
        preds = predict(new_x[scored_idx], meta, arr, cfg)
        res["shipped"][method] = {
            "all": score(scored, preds), "by_pack": grouped(scored, preds, lambda r: r["pack"]),
            "by_type": grouped(scored, preds, lambda r: r["type"]),
            "by_pack_type": grouped(scored, preds, lambda r: f"{r['pack']}/{r['type']}"),
            "wrong": [{"id": r["id"], "label": "cloud" if r["cloud_required"] else "local",
                       "route": p["route"], "reason": p["reason"], "cloud_probability": round(
                           p["cloud_required"], 3), "nearest_similarity": round(p["nearest_similarity"], 3)}
                      for r, p in zip(scored, preds, strict=True)
                      if p["route"] != ("cloud" if r["cloud_required"] else "local")]}
    res["experiment"] = experiment(seed_rows, seed_x, new_rows, new_x, cfg)
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(res, indent=2) + "\n", encoding="utf-8")
    write_report(res, args.out / "report.md")
    if args.save_candidate:
        rows_all = seed_rows + [r for r in new_rows if not r["uncertain"]]
        x_all = np.vstack([seed_x, new_x[scored_idx]])
        for method in METHODS:
            meta, arr = fit_arrays(x_all, rows_all, method, cfg)
            meta["training_count"] = len(rows_all)
            cand = args.out / "candidate"
            cand.mkdir(exist_ok=True)
            np.savez_compressed(cand / f"semantic_{method}.npz", metadata=np.array(json.dumps(meta)), **arr)
    for method in METHODS:
        a = res["shipped"][method]["all"]
        print(f"{method}: n={a['n']} accuracy={a['accuracy']} cloud share={a['cloud_share']} "
              f"unreliable={a['unreliable_share']}")
    print(f"wrote {args.out}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
