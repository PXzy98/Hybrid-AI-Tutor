"""E6 for engineering courses (task Z11): does the ECE privacy profile find credentials, lab addresses and
repository URLs in ECE questions without hiding course terms?

Cases: ece_cases.jsonl (fictional; every key is a fake made for this set). Profiles compared: `general` (the
base layer every course has) and `ece` (base + internal addresses + repository URLs). An entity counts as
protected when at least 80% of its characters are covered by findings (the E6 rule). A negative question,
or a `keep` term, with any finding counts as over-redaction.

    .venv\\Scripts\\python eval\\privacy-filter\\ece.py          # -> results/ece/report.md, metrics.json
"""
import argparse
import json
import sys
from collections import Counter
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

import yaml  # noqa: E402

from app.core.config import DEFAULT_CONFIG, PrivacyConfig  # noqa: E402
from app.privacy.analyzer import PIIAnalyzer  # noqa: E402
from app.privacy.profiles import privacy_profile  # noqa: E402


def covered(spans: list[tuple[int, int]], start: int, end: int) -> float:
    chars = set()
    for s, e in spans:
        chars.update(range(max(s, start), min(e, end)))
    return len(chars) / max(1, end - start)


def evaluate(cases: list[dict], analyzer: PIIAnalyzer) -> dict:
    found_by_type: Counter = Counter()
    total_by_type: Counter = Counter()
    leaks, over, kept_lost, misses, false = 0, 0, 0, [], []
    positives = [c for c in cases if c["group"] == "positive"]
    negatives = [c for c in cases if c["group"] == "negative"]
    for c in cases:
        findings = analyzer.analyze(c["text"])
        spans = [(f.start, f.end) for f in findings]
        leaked = False
        for ent in c["entities"]:
            start = c["text"].find(ent["text"])
            total_by_type[ent["type"]] += 1
            if covered(spans, start, start + len(ent["text"])) >= 0.8:
                found_by_type[ent["type"]] += 1
            else:
                leaked = True
                misses.append(f'{c["id"]} {ent["type"]}')
        for term in c["keep"]:
            start = c["text"].find(term)
            if start >= 0 and covered(spans, start, start + len(term)) > 0:
                kept_lost += 1
                false.append(f'{c["id"]} keep "{term}"')
        if c["group"] == "positive" and leaked:
            leaks += 1
        if c["group"] == "negative" and findings:
            over += 1
            false.append(f'{c["id"]} ' + ", ".join(sorted({f.type for f in findings})))
    return {
        "positive": len(positives), "negative": len(negatives),
        "leak_rate": leaks / max(1, len(positives)),
        "over_redaction": over / max(1, len(negatives)),
        "keep_terms_lost": kept_lost,
        "recall_by_type": {t: found_by_type[t] / total_by_type[t] for t in sorted(total_by_type)},
        "misses": misses, "false_findings": false,
    }


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--cases", type=Path, default=HERE / "ece_cases.jsonl")
    ap.add_argument("--out", type=Path, default=HERE / "results" / "ece")
    a = ap.parse_args()
    cases = [json.loads(line) for line in a.cases.read_text(encoding="utf-8").splitlines() if line.strip()]
    config = yaml.safe_load(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))  # config.yaml only, no .env
    base = PrivacyConfig(**config["privacy"])
    results = {}
    for name in ("general", "ece"):
        profile = privacy_profile(name)
        cfg = PrivacyConfig(**{**base.model_dump(), "recognizers": list(profile.recognizers)})
        results[name] = evaluate(cases, PIIAnalyzer(cfg))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "metrics.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    types = sorted({t for r in results.values() for t in r["recall_by_type"]})
    lines = [
        "# E6 for engineering courses (task Z11)", "",
        f"{len(cases)} fictional ECE questions ({results['ece']['positive']} positive, "
        f"{results['ece']['negative']} negative), `ece_cases.jsonl`; every key is a fake made for this set. "
        "Protected = at least 80% of the characters covered by findings. The rules were written with this "
        "set in view: read the numbers as optimistic until a held-out ECE set exists.", "",
        "| Profile | Leak: positive | Over-redaction: negative | Course terms lost | "
        + " | ".join(f"Recall {t}" for t in types) + " |",
        "|---|---|---|---|" + "---|" * len(types),
    ]
    for name, r in results.items():
        recall = " | ".join(f"{r['recall_by_type'].get(t, 0):.0%}" for t in types)
        lines.append(f"| {name} | {r['leak_rate']:.1%} | {r['over_redaction']:.1%} | "
                     f"{r['keep_terms_lost']} | {recall} |")
    for name, r in results.items():
        lines += ["", f"## `{name}`: misses and false findings", "",
                  "Misses: " + (", ".join(r["misses"]) or "none"),
                  "", "False findings: " + (", ".join(r["false_findings"]) or "none")]
    (a.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
