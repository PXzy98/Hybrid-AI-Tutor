"""E6 for the course types (task Z22): the held-out sets of make_course_sets.py, each with the profile of
its course type (and with `general`, the base layer, for comparison).

An entity counts as protected when at least 80% of its characters are covered by findings (the E6 rule).
A negative question, or a `keep` term, with any finding counts as over-redaction. Uses the application's
analyzer with config.yaml only (no .env), like ece.py.

    .venv\Scripts\python eval\privacy-filter\course_sets.py [--out eval\privacy-filter\results\z22]
"""
import argparse
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
sys.path.insert(0, str(HERE))

import yaml  # noqa: E402
from ece import evaluate  # noqa: E402

from app.core.config import DEFAULT_CONFIG, PrivacyConfig  # noqa: E402
from app.privacy.analyzer import PIIAnalyzer  # noqa: E402
from app.privacy.profiles import privacy_profile  # noqa: E402

SETS = [  # (file, course type, profiles to run)
    ("ece_holdout.jsonl", "ECE", ["general", "ece"]),
    ("cs_holdout.jsonl", "computer science", ["general", "computer_science"]),
    ("life_holdout.jsonl", "life science", ["general", "life_science", "medical_science"]),
    ("general_holdout.jsonl", "general", ["general"]),
]


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, default=HERE / "results" / "z22")
    a = ap.parse_args()
    config = yaml.safe_load(Path(DEFAULT_CONFIG).read_text(encoding="utf-8"))
    base = PrivacyConfig(**config["privacy"])
    results: dict = {}
    for fname, label, profiles in SETS:
        cases = [json.loads(x) for x in (HERE / fname).read_text(encoding="utf-8").splitlines() if x.strip()]
        for name in profiles:
            recognizers = list(privacy_profile(name).recognizers)
            cfg = PrivacyConfig(**{**base.model_dump(), "recognizers": recognizers})
            analyzer = PIIAnalyzer(cfg)
            r = evaluate(cases, analyzer)
            r["by_id"] = {c["id"]: [f.type for f in analyzer.analyze(c["text"])] for c in cases}
            r["set"], r["label"] = fname, label
            results[f"{fname}|{name}"] = r
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "metrics.json").write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
    for k, r in results.items():
        print(k, f"pos {r['positive']} neg {r['negative']} leak {r['leak_rate']:.1%} "
                 f"over {r['over_redaction']:.1%} keep-lost {r['keep_terms_lost']}")
        print("   recall", {t: f"{v:.0%}" for t, v in r["recall_by_type"].items()})
        print("   misses", r["misses"])
        print("   false", r["false_findings"])


if __name__ == "__main__":
    main()
