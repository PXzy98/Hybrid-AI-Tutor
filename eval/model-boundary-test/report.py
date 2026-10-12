"""Turn graded answers into the capability-boundary report.

  python report.py                 # pass threshold 80%
  python report.py --pass 0.6

Outputs in results/:
  boundary_heatmap.png   accuracy per model x (dimension, level)
  accuracy_table.csv     same numbers as a table
  report.md              boundary table + speed + Chinese vs English + failure examples
"""
import argparse, json
from pathlib import Path

import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

DIMS = [("knowledge", "Knowledge"), ("concept", "Concept"), ("calculation", "Calculation"),
        ("applied_reasoning", "Applied reasoning"), ("instruction_following", "Instruction following")]
# approx. parameters (billions) for sorting; MoE models: total (active)
PARAMS = {"qwen3.5:0.8b": 0.8, "qwen3.5:2b": 2, "qwen3.5:4b": 4, "qwen3.5:9b": 9, "qwen3.5:27b": 27,
          "qwen3.5:35b": 35, "qwen3.6:27b": 27, "qwen3.6:35b": 35, "qwen3.8:27b": 27,
          "gemma4:e2b": 2.3, "gemma4:e4b": 4.5, "gemma4:12b": 12, "gemma4:26b": 25.2, "gemma4:31b": 30.7,
          "qwen3:0.6b": 0.6, "qwen3:1.7b": 1.7, "qwen3:4b": 4, "qwen3:8b": 8, "qwen3:14b": 14,
          "qwen3:30b": 30, "qwen3:32b": 32, "llama3.2:3b": 3, "llama3.1:8b": 8}
RAMP = ["#cde2fb", "#9ec5f4", "#6da7ec", "#3987e5", "#256abf", "#184f95", "#0d366b"]
INK, INK2, SURFACE = "#0b0b0b", "#52514e", "#fcfcfb"


def cfg(r):
    th = r.get("think")
    return r["model"] + (" +think" if th is True else "")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--graded", default="results/graded.jsonl")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--pass", dest="pass_", type=float, default=0.8)
    a = ap.parse_args()
    out = Path(a.outdir)

    df = pd.DataFrame([json.loads(l) for l in open(a.graded, encoding="utf-8") if l.strip()])
    df["config"] = df.apply(cfg, axis=1)
    df = df[df["correct"].notna()].copy()
    df["correct"] = df["correct"].astype(bool)
    configs = sorted(df["config"].unique(),
                     key=lambda c: (PARAMS.get(c.split(" ")[0], 999), c))

    core = df[df["dimension"] != "chinese_mirror"]
    acc = core.pivot_table(index="config", columns=["dimension", "level"], values="correct", aggfunc="mean")
    cols = [(d, l) for d, _ in DIMS for l in (1, 2, 3, 4) if (d, l) in acc.columns]
    acc = acc.reindex(index=configs, columns=cols)
    flat = acc.copy(); flat.columns = [f"{d}_L{l}" for d, l in cols]
    flat.round(2).to_csv(out / "accuracy_table.csv")

    # ---------------- heatmap
    cmap = LinearSegmentedColormap.from_list("blue", RAMP)
    fig_w = 1.2 + 0.42 * len(cols) + 1.8
    fig, ax = plt.subplots(figsize=(fig_w, 0.45 * len(configs) + 1.8), dpi=150)
    fig.patch.set_facecolor(SURFACE); ax.set_facecolor(SURFACE)
    ax.imshow(acc.values.astype(float), cmap=cmap, vmin=0, vmax=1, aspect="auto")
    for i in range(len(configs)):
        for j in range(len(cols)):
            v = acc.values[i, j]
            if pd.notna(v):
                ax.text(j, i, f"{v*100:.0f}", ha="center", va="center", fontsize=7,
                        color="white" if v >= 0.55 else INK)
    ax.set_yticks(range(len(configs))); ax.set_yticklabels(configs, fontsize=8, color=INK)
    ax.set_xticks(range(len(cols))); ax.set_xticklabels([f"L{l}" for _, l in cols], fontsize=7, color=INK2)
    for k, (d, name) in enumerate([x for x in DIMS if any(c[0] == x[0] for c in cols)]):
        idx = [j for j, c in enumerate(cols) if c[0] == d]
        ax.text(sum(idx) / len(idx), -0.6, name, ha="center", va="bottom", fontsize=8, color=INK)
        if k:
            ax.axvline(idx[0] - 0.5, color=SURFACE, linewidth=3)
    for s in ax.spines.values():
        s.set_visible(False)
    ax.tick_params(length=0)
    fig.suptitle("Accuracy (%) by dimension and difficulty level", x=0.01, ha="left", fontsize=10, color=INK)
    fig.tight_layout(rect=(0, 0, 1, 0.93)); fig.savefig(out / "boundary_heatmap.png", facecolor=SURFACE); plt.close(fig)

    # ---------------- boundary = highest level reached with every lower level also passing
    rows = []
    for c in configs:
        row = {"config": c, "params_B": PARAMS.get(c.split(" ")[0])}
        for d, name in DIMS:
            b = 0
            for l in (1, 2, 3, 4):
                v = acc.loc[c].get((d, l)) if (d, l) in acc.columns else None
                if v is not None and pd.notna(v) and v >= a.pass_:
                    b = l
                else:
                    break
            row[name] = f"L{b}" if b else "<L1"
        sub = df[df["config"] == c]
        row["overall_acc"] = round(core[core["config"] == c]["correct"].mean(), 2)
        row["format_ok"] = round(sub[sub["answer_type"].isin(["mcq", "numeric", "short"])]["format_ok"]
                                 .astype(float).mean(), 2)
        row["median_s"] = round(sub["total_s"].median(), 1)
        row["median_tok_s"] = round(sub["tok_per_s"].median(), 1)
        row["hit_max_tokens"] = int(sub["hit_max_tokens"].fillna(False).astype(bool).sum())
        rows.append(row)
    bt = pd.DataFrame(rows)
    bt.to_csv(out / "boundary_table.csv", index=False)

    # ---------------- Chinese vs English (paired)
    zh = df[df["dimension"] == "chinese_mirror"]
    zrows = []
    for c in configs:
        z = zh[zh["config"] == c]
        if z.empty:
            continue
        en = df[(df["config"] == c) & (df["id"].isin(z["pair_of"]))]
        zrows.append({"config": c, "english_acc": round(en["correct"].mean(), 2),
                      "chinese_acc": round(z["correct"].mean(), 2), "n_pairs": len(z)})
    zt = pd.DataFrame(zrows)

    # ---------------- failures at each model's boundary
    fails = core[~core["correct"]].sort_values(["config", "dimension", "level"])
    lines = ["# Small-model capability boundary report\n",
             f"Pass threshold per cell: **{int(a.pass_*100)}%** (5 questions per cell, so 4/5 correct).  ",
             "Boundary = highest level reached with all lower levels also passing.\n",
             "## Boundary per model\n", bt.to_markdown(index=False), "",
             "![heatmap](boundary_heatmap.png)\n",
             "## Accuracy table\n", flat.round(2).to_markdown(), ""]
    if not zt.empty:
        lines += ["## Chinese vs English (same 10 questions)\n", zt.to_markdown(index=False), ""]
    lines += ["## Wrong answers (for manual inspection)\n",
              "| config | id | type | detail |", "|---|---|---|---|"]
    for _, r in fails.iterrows():
        lines.append(f"| {r['config']} | {r['id']} | {r['answer_type']} | {str(r['detail'])[:80]} |")
    (out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print(bt.to_string(index=False))
    if not zt.empty:
        print("\n" + zt.to_string(index=False))
    print(f"\n-> {out/'report.md'}, {out/'boundary_heatmap.png'}")


if __name__ == "__main__":
    main()
