"""T5: accuracy of the question type head (concept vs logistics); local encoder only, no network.

Two evaluations, both split by course (no question of a test course is in training):
  - held-out: train on every course except `TEST_COURSES`, test on those;
  - leave-one-course-out: for every course, train on all the others (the per-course table).
Writes `report.md` and `metrics.json` next to this file. Does not write the shipped weight file.

Usage (repository root):  python eval/question-type/run.py [--out DIR]
"""
import argparse
import json
import sys
from pathlib import Path

import numpy as np

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.routing.models import encode  # noqa: E402
from app.routing.question_type_train import TEST_COURSES, fit, labels_of, read_rows  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analysis_text import ANALYSIS  # noqa: E402

NAMES = ("concept", "logistics")


def scores(y: np.ndarray, pred: np.ndarray) -> dict:
    tn, fp = int(((y == 0) & (pred == 0)).sum()), int(((y == 0) & (pred == 1)).sum())
    fn, tp = int(((y == 1) & (pred == 0)).sum()), int(((y == 1) & (pred == 1)).sum())
    n = len(y)
    return {"n": n, "accuracy": round((tn + tp) / n, 3),
            "logistics_precision": round(tp / (tp + fp), 3) if tp + fp else None,
            "logistics_recall": round(tp / (tp + fn), 3) if tp + fn else None,
            "confusion": {"concept->concept": tn, "concept->logistics": fp,
                          "logistics->concept": fn, "logistics->logistics": tp}}


def fmt(v) -> str:
    return "-" if v is None else f"{v:.2f}"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--out", type=Path, default=HERE)
    args = parser.parse_args()
    cfg = get_settings().routing
    rows = read_rows()
    x = encode([r["question"] for r in rows], cfg)
    y = labels_of(rows)
    course = np.array([r["course"] for r in rows])
    test = np.isin(course, TEST_COURSES)

    model = fit(x[~test], y[~test])
    prob = model.predict_proba(x[test])[:, 1]
    held = scores(y[test], (prob >= 0.5).astype(int))
    held["majority_baseline_accuracy"] = round(float((y[test] == 0).mean()), 3)
    held["per_course"] = {c: scores(y[test & (course == c)],
                                    (model.predict_proba(x[test & (course == c)])[:, 1] >= 0.5).astype(int))
                          for c in TEST_COURSES}
    wrong = [{"question": rows[i]["question"], "course": rows[i]["course"], "label": rows[i]["label"],
              "p_logistics": round(float(p), 3)}
             for i, p in zip(np.flatnonzero(test), prob, strict=True) if (p >= 0.5) != y[i]]

    loco, pred_all = {}, np.zeros(len(y), dtype=int)
    for c in sorted(set(course)):
        mask = course == c
        m = fit(x[~mask], y[~mask])
        pred_all[mask] = (m.predict_proba(x[mask])[:, 1] >= 0.5).astype(int)
        loco[c] = scores(y[mask], pred_all[mask])
    overall = scores(y, pred_all)

    metrics = {"rows": len(rows), "logistics_rows": int(y.sum()), "test_courses": list(TEST_COURSES),
               "held_out": held, "leave_one_course_out": {"overall": overall, "per_course": loco},
               "held_out_errors": wrong}
    args.out.mkdir(parents=True, exist_ok=True)
    (args.out / "metrics.json").write_text(json.dumps(metrics, indent=2) + "\n", encoding="utf-8")

    cm = held["confusion"]
    lines = [
        "# Question type head: concept vs logistics (T5)", "",
        f"{len(rows)} labelled questions ({int(y.sum())} logistics) from the S11 course packs, the T4 ECE/CS "
        "questions, the medical seed questions (every third one) and a supplement of six more subjects "
        "(`data/question_type/`). The head is a logistic regression (C=4, balanced classes) on the local "
        "`all-MiniLM-L6-v2` embedding the router already computes; threshold 0.5. Every split is by "
        "course.", "",
        "## Held-out courses", "",
        f"Trained on {int((~test).sum())} questions, tested on {int(test.sum())} questions of "
        f"{len(TEST_COURSES)} courses never seen in training: "
        + ", ".join(f"`{c}`" for c in TEST_COURSES) + ".", "",
        f"Accuracy **{held['accuracy']:.3f}** (always answering concept: "
        f"{held['majority_baseline_accuracy']:.3f}); logistics precision {fmt(held['logistics_precision'])}, "
        f"recall {fmt(held['logistics_recall'])}.", "",
        "| True \\ predicted | concept | logistics |", "|---|---|---|",
        f"| concept | {cm['concept->concept']} | {cm['concept->logistics']} |",
        f"| logistics | {cm['logistics->concept']} | {cm['logistics->logistics']} |", "",
        "| Course | n | accuracy | logistics precision | logistics recall |", "|---|---|---|---|---|"]
    for c, s in held["per_course"].items():
        lines.append(f"| {c} | {s['n']} | {fmt(s['accuracy'])} | {fmt(s['logistics_precision'])} | "
                     f"{fmt(s['logistics_recall'])} |")
    lines += ["", "Held-out errors:", ""]
    lines += [f"- {w['label']} (p(logistics) {w['p_logistics']:.2f}, `{w['course']}`): {w['question']}"
              for w in wrong] or ["- none"]
    cm = overall["confusion"]
    lines += ["", "## Leave-one-course-out", "",
              "Each course is predicted by a head trained on all the others, so every question is scored "
              f"once on unseen course material. Accuracy **{overall['accuracy']:.3f}** over {overall['n']} "
              f"questions; logistics precision {fmt(overall['logistics_precision'])}, recall "
              f"{fmt(overall['logistics_recall'])}.", "",
              "| True \\ predicted | concept | logistics |", "|---|---|---|",
              f"| concept | {cm['concept->concept']} | {cm['concept->logistics']} |",
              f"| logistics | {cm['logistics->concept']} | {cm['logistics->logistics']} |", "",
              "| Course | n | accuracy | logistics precision | logistics recall |", "|---|---|---|---|---|"]
    for c, s in loco.items():
        lines.append(f"| {c} | {s['n']} | {fmt(s['accuracy'])} | {fmt(s['logistics_precision'])} | "
                     f"{fmt(s['logistics_recall'])} |")
    lines += ["", ANALYSIS.rstrip(), ""]
    (args.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(f"held-out accuracy {held['accuracy']:.3f} (n={held['n']}); leave-one-course-out "
          f"{overall['accuracy']:.3f} (n={overall['n']})")
    print(f"wrote {args.out / 'report.md'}")


if __name__ == "__main__":
    main()
