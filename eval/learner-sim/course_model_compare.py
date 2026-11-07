"""S8 evaluation: the course-level layered model vs plain KC-level BKT on simulated students.

Offline, fictional, no real student data. Simulated course: 12 KCs in a prerequisite graph.

Simulated student:
- ability theta ~ N(0, 1); true mastery of a KC m = sigmoid(1.2 * theta + b_kc), b_kc ~ U(-1.5, 0.5),
  never more than 0.2 above the weakest prerequisite (as in sim.py);
- learning rate in [0.05, 0.20]: after practising a KC, m += learn * (1 - m); forgetting 0.02 per step;
- slip in [0.10, 0.25], guess in [0.20, 0.40]; P(correct) = m * (1 - slip) + (1 - m) * guess;
- each step practises a random KC (the student does not see every KC: new KCs keep appearing).

Configurations (all use CourseKnowledgeCore with the same BKT parameters):
- `bkt`: plain BKT (no prerequisites, ability_weight 0), i.e. the v3 model per KC;
- `+ability`: unobserved KCs start from the ability-shifted prior;
- `+prereq`: prerequisite propagation only;
- `layered`: both (the S8 model).

Metrics, every step: MAE between the estimate (effective mastery) and the true mastery over all KCs; MAE
over the KCs not practised yet (where the ability layer matters); next-answer AUC of predict_correct.

Run from the repository root: python eval/learner-sim/course_model_compare.py
"""
import argparse
import random
import sys
from math import exp
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.learner.knowledge.course_core import CourseEvidence, CourseKnowledgeCore  # noqa: E402
from sklearn.metrics import roc_auc_score  # noqa: E402

GRAPH = {
    "K01": [], "K02": [], "K03": ["K01"], "K04": ["K01", "K02"], "K05": ["K03"], "K06": ["K04"],
    "K07": ["K05", "K06"], "K08": ["K02"], "K09": ["K08"], "K10": ["K07"], "K11": ["K09", "K10"],
    "K12": ["K11"],
}
ORDER = list(GRAPH)  # topological


def _sigmoid(x: float) -> float:
    return 1 / (1 + exp(-x))


def _student(rng: random.Random) -> dict:
    theta = rng.gauss(0, 1)
    mastery: dict[str, float] = {}
    for kc in ORDER:
        m = _sigmoid(1.2 * theta + rng.uniform(-1.5, 0.5))
        if GRAPH[kc]:
            m = min(m, min(mastery[d] for d in GRAPH[kc]) + 0.2)
        mastery[kc] = m
    return {"mastery": mastery, "learn": rng.uniform(0.05, 0.20),
            "slip": rng.uniform(0.10, 0.25), "guess": rng.uniform(0.20, 0.40)}


def _models() -> dict[str, CourseKnowledgeCore]:
    flat = {kc: [] for kc in GRAPH}
    return {
        "bkt": CourseKnowledgeCore(flat, ability_weight=0.0),
        "+ability": CourseKnowledgeCore(flat, ability_weight=0.5),
        "+prereq": CourseKnowledgeCore(GRAPH, ability_weight=0.0),
        "layered": CourseKnowledgeCore(GRAPH, ability_weight=0.5),
    }


def run(students: int, steps: int, seed: int) -> dict[str, dict[str, float]]:
    rng = random.Random(seed)
    models = _models()
    stats = {name: {"abs": 0.0, "n": 0, "abs_new": 0.0, "n_new": 0, "pred": [], "obs": []} for name in models}
    for s in range(students):
        sim = _student(rng)
        states = {name: m.initial(1, f"sim-{s}") for name, m in models.items()}
        seen: set[str] = set()
        for _ in range(steps):
            for kc in ORDER:
                sim["mastery"][kc] *= 0.98
            kc = rng.choice(ORDER)
            m = sim["mastery"][kc]
            correct = rng.random() < m * (1 - sim["slip"]) + (1 - m) * sim["guess"]
            difficulty = rng.choice(["basic", "intermediate", "advanced"])
            for name, model in models.items():
                st, est = stats[name], model.effective_mastery(states[name])
                for k in ORDER:
                    err = abs(est[k] - sim["mastery"][k])
                    st["abs"] += err
                    st["n"] += 1
                    if k not in seen:
                        st["abs_new"] += err
                        st["n_new"] += 1
                st["pred"].append(model.predict_correct(states[name], kc))
                st["obs"].append(int(correct))
                states[name] = model.update(states[name], CourseEvidence(
                    1, f"sim-{s}", kc, "strong", correct, difficulty))
            seen.add(kc)
            sim["mastery"][kc] += sim["learn"] * (1 - sim["mastery"][kc])
    return {name: {"mae": st["abs"] / st["n"], "mae_unseen": st["abs_new"] / max(st["n_new"], 1),
                   "auc": roc_auc_score(st["obs"], st["pred"])} for name, st in stats.items()}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--students", type=int, default=300)
    parser.add_argument("--steps", type=int, default=40)
    parser.add_argument("--seeds", type=int, nargs="+", default=[2026, 2027, 2028])
    parser.add_argument("--out", type=Path, default=Path(__file__).parent / "results" / "course_model.md")
    args = parser.parse_args()
    runs = [run(args.students, args.steps, seed) for seed in args.seeds]
    names = list(runs[0])
    lines = [
        "# S8: course-level layered model vs plain BKT (simulated)",
        "",
        f"{args.students} fictional students × {args.steps} answers, 12 KCs, seeds {args.seeds}; mean over "
        "seeds (min–max). Generated by `eval/learner-sim/course_model_compare.py`; see its docstring for the "
        "simulation. Lower MAE and higher AUC are better.",
        "",
        "| Config | MAE (all KCs) | MAE (KCs not practised yet) | Next-answer AUC |",
        "|---|---|---|---|",
    ]
    for name in names:
        cells = []
        for metric in ("mae", "mae_unseen", "auc"):
            values = [r[name][metric] for r in runs]
            cells.append(f"{sum(values) / len(values):.3f} ({min(values):.3f}–{max(values):.3f})")
        lines.append(f"| {name} | " + " | ".join(cells) + " |")
    lines += ["", "Simulation only: it shows the layers behave as intended on data generated with an ability "
              "factor and prerequisites; it is not evidence about real students."]
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
