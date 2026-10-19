"""E6 cloud exposure: what would actually reach the cloud, per configuration and test set.

    .venv\\Scripts\\python eval\\privacy-filter\\exposure.py      (after run.py on the three sets)

The leak rate in run.py counts every unprotected entity, also in questions the filter keeps local (a personal
health question never goes to the cloud, whatever is left in it). Here a question is "exposed" only if the
filter would send it to the cloud (no local-only finding) and it still contains unprotected PII. Identifier
exposure counts names, student numbers, e-mails and phones only: the details that link a question to a person.
Reads results/{.,holdout_dev,holdout_test}/predictions.jsonl, writes results/exposure.md.
"""
import collections
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
IDENTIFIERS = {"PERSON", "STUDENT_ID", "EMAIL_ADDRESS", "PHONE_NUMBER", "USERNAME", "ID_NUMBER", "HEALTH_CARD"}
SETS = [(".", "main set (development, 404)"), ("holdout_dev", "held-out v1 (dev, 102)"),
        ("holdout_test", "held-out v2 (test, 102)")]


def main() -> int:
    L = ["# E6: cloud exposure per configuration\n",
         "Share of labelled questions (positive, hard, French, multi-turn) that the filter would send to the cloud "
         "with PII still in them. *Any PII*: any unprotected entity; *identifier*: a name, student number, e-mail, "
         "phone or other ID; *health*: the question states a personal health detail but is not kept local.\n"]
    for d, title in SETS:
        path = HERE / "results" / d / "predictions.jsonl"
        if not path.exists():
            continue
        by = collections.defaultdict(list)
        for line in path.read_text("utf-8").splitlines():
            r = json.loads(line)
            if r["group"] not in ("negative", "out_of_scope"):
                by[r["config"]].append(r)
        L += [f"## {title}\n", "| Configuration | Questions | Sent to cloud | Exposed: any PII | identifier | "
              "personal health |", "|---|---|---|---|---|---|"]
        for c, rs in by.items():
            n, cloud = len(rs), [r for r in rs if not r["predicted_health"]]
            anyp = sum(any(not e["protected"] for e in r["entities"]) for r in cloud)
            ident = sum(any(e["type"] in IDENTIFIERS and not e["protected"] for e in r["entities"]) for r in cloud)
            health = sum(r["personal_health"] for r in cloud)
            L.append(f"| {c} | {n} | {len(cloud)} | {anyp / n:.1%} | {ident / n:.1%} | {health / n:.1%} |")
        L.append("")
    (HERE / "results" / "exposure.md").write_text("\n".join(L), encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
