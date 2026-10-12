"""E2: does BKT estimate mastery better than the rule method? (design §11 E2)

    .venv\\Scripts\\python eval\\learner-sim\\run.py              # full: 200 students x 40 interactions
    .venv\\Scripts\\python eval\\learner-sim\\run.py --smoke      # CI: 8 students x 8 interactions

Runs bkt and rule, each with weak evidence off and on, plus a one-at-a-time sensitivity sweep of the BKT
parameters. Writes results/report.md and SVG charts (results/*.svg), and prints the recommended
learner.knowledge value. The simulator is described in sim.py. No LLM is involved.

Pre-registered decision rule (design §11 E2):
- keep BKT only if its MAE is lower than the rule method's by at least 0.03 AND its AUC is not lower;
  otherwise switch to `rule`;
- weak evidence: keep it only if it lowers the MAE (for the recommended model).
"""
import argparse
import math
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))

import sim  # noqa: E402

from app.core.config import get_settings  # noqa: E402

MAE_MARGIN = 0.03
E1_REPORT = HERE.parent / "understand-tagging" / "results" / "report.md"
DEFAULT_NOISE = 0.08
SWEEP = {"p_init": (0.10, 0.30), "learn": (0.05, 0.20), "slip": (0.05, 0.20), "guess": (0.15, 0.35)}
COLORS = {"bkt": "#0f766e", "rule": "#d97706"}


def e1_noise() -> tuple[float, str]:
    """Tagging error rate = 1 - KC top-1 accuracy from the E1 report, if there is one."""
    if E1_REPORT.exists():
        m = re.search(r"KC top-1 accuracy[^|]*\|\s*(\d+)%", E1_REPORT.read_text(encoding="utf-8"))
        if m:
            return round(1 - int(m.group(1)) / 100, 3), f"E1 report ({E1_REPORT.relative_to(sim.ROOT)})"
    return DEFAULT_NOISE, "default (no E1 report)"


def paired_diff(a: list[float], b: list[float]) -> tuple[float, float]:
    """Mean of a - b per student, and a 95% half-width."""
    d = [x - y for x, y in zip(a, b, strict=True)]
    mean = statistics.fmean(d)
    half = 1.96 * statistics.stdev(d) / math.sqrt(len(d)) if len(d) > 1 else float("nan")
    return mean, half


def decide(results: dict[str, sim.RunResult]) -> dict:
    bkt, rule = results["bkt"], results["rule"]
    keep_bkt = bkt.mae <= rule.mae - MAE_MARGIN and bkt.auc >= rule.auc
    model = "bkt" if keep_bkt else "rule"
    weak_on, weak_off = results[f"{model}+weak"], results[model]
    return {"knowledge": model, "keep_bkt": keep_bkt, "weak_evidence": weak_on.mae < weak_off.mae,
            "mae_gain": rule.mae - bkt.mae, "auc_diff": bkt.auc - rule.auc}


# ------------------------------------------------------------------------------------------- SVG charts
def svg_bars(title: str, labels: list[str], values: list[float], colors: list[str], fmt="{:.3f}") -> str:
    w, h, left, top, bar_h, gap = 640, 40 + 34 * len(labels), 170, 34, 22, 12
    vmax = max(values) * 1.15 if values and max(values) > 0 else 1
    rows = []
    for i, (lab, v, c) in enumerate(zip(labels, values, colors, strict=True)):
        y = top + i * (bar_h + gap)
        bw = (w - left - 70) * v / vmax
        rows.append(f'<text x="{left - 8}" y="{y + 16}" text-anchor="end" font-size="13">{lab}</text>'
                    f'<rect x="{left}" y="{y}" width="{bw:.1f}" height="{bar_h}" fill="{c}"/>'
                    f'<text x="{left + bw + 6:.1f}" y="{y + 16}" font-size="12">{fmt.format(v)}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif">'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<text x="12" y="22" font-size="15" font-weight="bold">{title}</text>{"".join(rows)}</svg>')


def svg_lines(title: str, series: dict[str, tuple[list[float], str]], ylabel: str) -> str:
    w, h, left, right, top, bottom = 640, 320, 56, 20, 36, 40
    n = max(len(v) for v, _ in series.values())
    ymax = max(max(v) for v, _ in series.values()) * 1.1 or 1
    def x(i): return left + (w - left - right) * i / max(n - 1, 1)
    def y(v): return top + (h - top - bottom) * (1 - v / ymax)
    parts = [f'<line x1="{left}" y1="{y(0)}" x2="{w - right}" y2="{y(0)}" stroke="#94a3b8"/>',
             f'<line x1="{left}" y1="{top}" x2="{left}" y2="{y(0)}" stroke="#94a3b8"/>']
    for t in range(5):
        v = ymax * t / 4
        parts.append(f'<text x="{left - 6}" y="{y(v) + 4:.1f}" text-anchor="end" font-size="11">{v:.2f}</text>')
    for i in range(0, n, max(1, n // 8)):
        parts.append(f'<text x="{x(i):.1f}" y="{h - bottom + 16}" text-anchor="middle" font-size="11">{i + 1}</text>')
    for k, (name, (vals, color)) in enumerate(series.items()):
        pts = " ".join(f"{x(i):.1f},{y(v):.1f}" for i, v in enumerate(vals))
        parts.append(f'<polyline points="{pts}" fill="none" stroke="{color}" stroke-width="2"/>'
                     f'<text x="{w - right - 140}" y="{top + 16 * k + 4}" font-size="12" fill="{color}">{name}</text>')
    parts.append(f'<text x="{(w + left) / 2}" y="{h - 6}" text-anchor="middle" font-size="12">interaction</text>'
                 f'<text x="14" y="{top - 10}" font-size="12">{ylabel}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif">'
            f'<rect width="100%" height="100%" fill="white"/>'
            f'<text x="12" y="20" font-size="15" font-weight="bold">{title}</text>{"".join(parts)}</svg>')


# ---------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--students", type=int, default=200)
    ap.add_argument("--interactions", type=int, default=40)
    ap.add_argument("--sweep-students", type=int, default=100)
    ap.add_argument("--noise", type=float, help="weak-signal tagging error rate (default: from the E1 report)")
    ap.add_argument("--seed", type=int, default=2026)
    ap.add_argument("--smoke", action="store_true", help="tiny run for CI")
    ap.add_argument("--no-sweep", action="store_true")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args(argv)
    if a.smoke:
        a.students, a.interactions, a.sweep_students = 8, 8, 4
    noise, noise_src = (a.noise, "command line") if a.noise is not None else e1_noise()

    base = get_settings()
    content = sim.load_content(base)
    topics = sim.simulated_topics(content)
    skipped = [t for t in content.topics() if t not in topics]
    a.out.mkdir(parents=True, exist_ok=True)
    started = time.perf_counter()
    lines = ["# E2: BKT vs rule on simulated students (design §11 E2)\n",
             f"{a.students} students × {a.interactions} interactions per topic · seed {a.seed} · "
             f"weak-signal tagging noise {noise:.0%} ({noise_src}) · forgetting {sim.FORGET}/step · "
             "student slip ∈ [0.10, 0.25], guess ∈ [0.20, 0.40], learning ∈ [0.05, 0.20] "
             "(BKT defaults: slip 0.10, guess 0.25, learn 0.10).\n",
             f"Topics simulated: {', '.join(topics) or 'none'}. "
             f"Skipped (no complete item bank yet): {', '.join(skipped) or 'none'}.\n"]
    decisions = []
    for topic in topics:
        students = sim.make_students(content, topic, a.students, a.seed)
        configs = [sim.RunConfig("bkt"), sim.RunConfig("rule", knowledge="rule"),
                   sim.RunConfig("bkt+weak", weak_evidence=True),
                   sim.RunConfig("rule+weak", knowledge="rule", weak_evidence=True)]
        results = {c.name: sim.run(base, content, topic, c, students, a.interactions, noise, a.seed)
                   for c in configs}
        d = decide(results)
        decisions.append(d["knowledge"])
        diff, half = paired_diff(results["bkt"].mae_by_student, results["rule"].mae_by_student)
        lines += [f"## {topic}\n",
                  "| Config | MAE | Next-answer AUC (oracle) | Band accuracy | Items reused (24 h rule) |",
                  "|---|---|---|---|---|",
                  *[f"| {n} | {r.mae:.3f} | {r.auc:.3f} ({r.oracle_auc:.3f}) | {r.band_accuracy:.1%} | "
                    f"{r.reused_items} |" for n, r in results.items()],
                  "",
                  "The oracle AUC predicts each answer from the student's true P(correct): the ceiling set by "
                  "slip and guess. Items reused: every item of the KC was answered within 24 h (no simulated "
                  "time passes), so the least recently answered one was asked again.",
                  "",
                  f"BKT − rule MAE per student: {diff:+.3f} (95% CI ± {half:.3f}). "
                  f"Needed for BKT: ≤ −{MAE_MARGIN:.2f} and AUC not lower "
                  f"(AUC difference {d['auc_diff']:+.3f}).\n",
                  f"**Decision:** `learner.knowledge: {d['knowledge']}` "
                  f"({'BKT kept' if d['keep_bkt'] else 'switch to rule'}). "
                  f"Weak evidence for {d['knowledge']}: "
                  f"**{'keep (lowers MAE)' if d['weak_evidence'] else 'keep off (does not lower MAE)'}** "
                  f"({results[d['knowledge']].mae:.3f} off vs {results[d['knowledge'] + '+weak'].mae:.3f} on).\n"]
        names = list(results)
        (a.out / f"{topic}_mae.svg").write_text(svg_bars(
            f"MAE vs true mastery ({topic})", names, [results[n].mae for n in names],
            [COLORS[n.split("+")[0]] for n in names]), encoding="utf-8")
        steps = {n: ([statistics.fmean(s) for s in results[n].mae_by_step], COLORS[n])
                 for n in ("bkt", "rule")}
        (a.out / f"{topic}_mae_by_step.svg").write_text(
            svg_lines(f"MAE by interaction ({topic})", steps, "MAE"), encoding="utf-8")
        lines += [f"![MAE]({topic}_mae.svg)\n", f"![MAE by step]({topic}_mae_by_step.svg)\n"]

        if not a.no_sweep:
            sweep_students = students[:a.sweep_students]
            rows = [("defaults", sim.run(base, content, topic, sim.RunConfig("defaults"), sweep_students,
                                         a.interactions, noise, a.seed))]
            for param, values in SWEEP.items():
                for v in values:
                    cfg = sim.RunConfig(f"{param}={v}", bkt={param: v})
                    rows.append((cfg.name, sim.run(base, content, topic, cfg, sweep_students, a.interactions,
                                                   noise, a.seed)))
            lines += [f"### Sensitivity of BKT ({topic}, {len(sweep_students)} students, one parameter at a time)\n",
                      "| BKT parameters | MAE | AUC | Band accuracy |", "|---|---|---|---|",
                      *[f"| {n} | {r.mae:.3f} | {r.auc:.3f} | {r.band_accuracy:.1%} |" for n, r in rows],
                      f"\nRule method on the same students for reference: see the table above. MAE range across the "
                      f"sweep: {min(r.mae for _, r in rows):.3f}–{max(r.mae for _, r in rows):.3f}.\n"]
            (a.out / f"{topic}_sensitivity.svg").write_text(svg_bars(
                f"BKT sensitivity: MAE ({topic})", [n for n, _ in rows], [r.mae for _, r in rows],
                [COLORS["bkt"]] * len(rows)), encoding="utf-8")
            lines.append(f"![Sensitivity]({topic}_sensitivity.svg)\n")

    recommended = "bkt" if decisions and all(d == "bkt" for d in decisions) else "rule"
    lines += ["## Recommendation\n",
              f"`learner.knowledge: {recommended}`" + ("" if decisions else " (no topic could be simulated)") + "\n",
              f"Runtime {time.perf_counter() - started:.0f} s."
              + (" **Smoke run: too small to decide anything.**" if a.smoke else "") + "\n"]
    (a.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    print(f"recommended learner.knowledge: {recommended}")
    return 0 if topics else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # reports contain ≥, ×, ∈ (Windows consoles)
    sys.exit(main())
