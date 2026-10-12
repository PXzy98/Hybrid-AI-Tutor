"""E1: can the local model tag student questions reliably? (design §11, E1)

    .venv\\Scripts\\python eval\\understand-tagging\\run.py                    # model from config.yaml
    .venv\\Scripts\\python eval\\understand-tagging\\run.py --model gemma4:e4b --repeat 2

Runs the real understand step (same prompt, schema and client settings as the app) on cases.jsonl and
writes results/report.md and results/predictions.jsonl. Needs the Ollama server (OLLAMA_URL).

Metrics
- KC top-1 accuracy: on questions with a gold KC, the first predicted KC is one of the gold KCs.
- No-KC accuracy: on off-topic questions, the prediction is [].
- Misconception precision / recall: over (question, misconception ID) pairs.
- Confusion accuracy, question-type accuracy (informative).
- Latency p50 / p95 of the understand call (model already loaded; one warm-up call is not counted).
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.learner import understand  # noqa: E402
from app.learner.content import ContentStore  # noqa: E402
from app.llm.ollama_client import OllamaClient  # noqa: E402

TOPIC = "high_blood_pressure"
TARGETS = {  # design §11 E1: (ideal, marginal)
    "kc_top1": (0.85, 0.75),
    "mc_precision": (0.80, 0.70),
    "p50_s": (0.6, None),
}


def verdict(name: str, value: float) -> str:
    ideal, marginal = TARGETS[name]
    if name.endswith("_s"):
        return "✅ ideal" if value <= ideal else "❌ above target"
    return "✅ ideal" if value >= ideal else ("🟡 marginal" if value >= marginal else "❌ below marginal")


async def classify(client, content, question):
    t0 = time.perf_counter()
    try:
        res = await client.complete(understand.messages(content, TOPIC, question),
                                    json_schema=understand.schema(content, TOPIC), max_tokens=200)
        u = understand.parse(res.text, content, TOPIC, question)
        return u.model_dump(), time.perf_counter() - t0, None
    except Exception as e:  # noqa: BLE001  a failure is a result too (the step would be skipped)
        return None, time.perf_counter() - t0, type(e).__name__


async def main_async(args) -> None:
    s = get_settings()
    model = args.model or s.llm.understand.model
    client = OllamaClient(s.ollama_url, model, temperature=0.0, num_ctx=s.llm.local.num_ctx,
                          timeout_s=args.timeout, max_tokens=200)
    content = ContentStore(s.content_dir(), serve_unreviewed=True)
    cases = [json.loads(line) for line in (HERE / "cases.jsonl").read_text("utf-8").splitlines() if line.strip()]
    await classify(client, content, "warm-up: what is blood pressure?")  # load the model, not counted

    rows = []
    for _ in range(args.repeat):
        for c in cases:
            pred, secs, err = await classify(client, content, c["question"])
            rows.append({"id": c["id"], "gold": c, "pred": pred, "seconds": round(secs, 3), "error": err})

    kc_cases = [r for r in rows if r["gold"]["kc_ids"]]
    none_cases = [r for r in rows if not r["gold"]["kc_ids"]]
    kc_hits = sum(1 for r in kc_cases if r["pred"] and r["pred"]["kc_ids"][:1]
                  and r["pred"]["kc_ids"][0] in r["gold"]["kc_ids"])
    none_hits = sum(1 for r in none_cases if r["pred"] and not r["pred"]["kc_ids"])
    tp = fp = fn = 0
    for r in rows:
        gold = set(r["gold"]["misconception_ids"])
        pred = set(r["pred"]["misconception_ids"]) if r["pred"] else set()
        tp, fp, fn = tp + len(gold & pred), fp + len(pred - gold), fn + len(gold - pred)
    ok = [r for r in rows if r["pred"]]
    conf_acc = sum(r["pred"]["confusion"] == r["gold"]["confusion"] for r in ok) / len(ok) if ok else 0
    qt_acc = sum(r["pred"]["question_type"] == r["gold"]["question_type"] for r in ok) / len(ok) if ok else 0
    secs = sorted(r["seconds"] for r in rows)
    p50, p95 = statistics.median(secs), secs[min(len(secs) - 1, int(0.95 * len(secs)))]
    kc_top1 = kc_hits / len(kc_cases)
    mc_p = tp / (tp + fp) if tp + fp else 1.0
    mc_r = tp / (tp + fn) if tp + fn else 1.0
    errors = [r for r in rows if r["error"]]

    out = HERE / "results"
    out.mkdir(exist_ok=True)
    with (out / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps({"id": r["id"], "question": r["gold"]["question"], "gold_kc": r["gold"]["kc_ids"],
                                "gold_mc": r["gold"]["misconception_ids"], "pred": r["pred"],
                                "seconds": r["seconds"], "error": r["error"]}, ensure_ascii=False) + "\n")
    misses = [r for r in kc_cases + none_cases
              if not r["pred"] or (r["pred"]["kc_ids"][:1] != [] and r["gold"]["kc_ids"]
                                   and r["pred"]["kc_ids"][0] not in r["gold"]["kc_ids"])
              or (r["pred"] and not r["gold"]["kc_ids"] and r["pred"]["kc_ids"])
              or (r["pred"] and r["gold"]["kc_ids"] and not r["pred"]["kc_ids"])]
    mc_errors = [r for r in rows if r["pred"] and set(r["pred"]["misconception_ids"])
                 != set(r["gold"]["misconception_ids"])]
    lines = [
        "# E1: understand-step tagging (design §11)\n",
        f"Model `{model}` on `{s.ollama_url}` · {len(cases)} cases × {args.repeat} · thinking off, temperature 0, "
        f"JSON schema with the topic's IDs. Cases are a DRAFT set (to be extended to 120–150 by the team).\n",
        "| Metric | Value | Target (ideal / marginal) | Verdict |",
        "|---|---|---|---|",
        f"| KC top-1 accuracy ({len(kc_cases)} questions with a KC) | {kc_top1:.0%} ({kc_hits}/{len(kc_cases)}) "
        f"| ≥ 85% / 75% | {verdict('kc_top1', kc_top1)} |",
        f"| No-KC accuracy ({len(none_cases)} off-topic) | {none_hits}/{len(none_cases)} | — | informative |",
        f"| Misconception precision | {mc_p:.0%} ({tp}/{tp + fp}) | ≥ 80% / 70% | {verdict('mc_precision', mc_p)} |",
        f"| Misconception recall | {mc_r:.0%} ({tp}/{tp + fn}) | — | informative |",
        f"| Confusion accuracy | {conf_acc:.0%} | — | informative |",
        f"| Question-type accuracy | {qt_acc:.0%} | — | informative |",
        f"| Latency p50 / p95 | {p50:.2f} s / {p95:.2f} s | p50 ≤ 0.6 s | {verdict('p50_s', p50)} |",
        f"| Failed calls (step would be skipped) | {len(errors)} | 0 | {'✅' if not errors else '❌'} |",
        "",
        "## KC errors",
        "",
        *([f"- {r['id']}: gold {r['gold']['kc_ids']} · predicted {r['pred']['kc_ids'] if r['pred'] else r['error']}"
           f" · {r['gold']['question']}" for r in misses] or ["- none"]),
        "",
        "## Misconception differences",
        "",
        *([f"- {r['id']}: gold {r['gold']['misconception_ids']} · predicted {r['pred']['misconception_ids']}"
           f" · {r['gold']['question']}" for r in mc_errors] or ["- none"]),
        "",
        "Decision rule (design §11 E1): below marginal → keep `learner.weak_evidence: false` and topic-only "
        "retrieval.",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", help="default: llm.understand.model")
    ap.add_argument("--repeat", type=int, default=1)
    ap.add_argument("--timeout", type=float, default=30, help="per call; the app uses llm.understand.timeout_s")
    asyncio.run(main_async(ap.parse_args()))


if __name__ == "__main__":
    main()
