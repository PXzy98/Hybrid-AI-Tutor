"""Export a topic's KCs, check questions and misconceptions to a CSV for review (e.g. by Dr. Abbas).

    .venv\\Scripts\\python scripts\\export_content_review.py high_blood_pressure
    .venv\\Scripts\\python scripts\\export_content_review.py --all

Writes docs/review/<topic>_review.csv (UTF-8 with BOM, so Excel shows accents and symbols correctly).
One row per KC, item and misconception; reviewers fill in `reviewer_comment` (and, once approved,
the author sets `reviewed_by` in the YAML).
"""
import argparse
import csv
import sys
from pathlib import Path

from app.core.config import REPO_ROOT, get_settings
from app.learner.content import ContentStore

COLUMNS = ["type", "id", "kc", "level", "text", "option_A", "option_B", "option_C", "option_D", "answer",
           "explanation_or_correction", "distractor_misconceptions", "prerequisites", "reviewed_by",
           "reviewer_comment"]


def rows_for(store: ContentStore, topic: str) -> list[dict]:
    tc = store.topic(topic)
    if tc is None:
        raise SystemExit(f"unknown topic '{topic}' (known: {', '.join(store.topics())})")
    rows = [{"type": "TOPIC", "id": tc.topic, "text": tc.name, "explanation_or_correction": tc.guideline}]
    for k in tc.kcs:
        rows.append({"type": "KC", "id": k.id, "kc": k.id, "level": k.difficulty,
                     "text": f"{k.name}: {k.definition}".strip(": "),
                     "prerequisites": " ".join(k.prerequisites)})
        for i in (i for i in tc.items if i.kc == k.id):
            row = {"type": "ITEM", "id": i.id, "kc": i.kc, "level": i.level, "text": i.stem,
                   "answer": i.answer, "explanation_or_correction": i.explanation,
                   "reviewed_by": i.reviewed_by or ""}
            for key, opt in sorted(i.options.items()):
                row[f"option_{key}"] = opt.text
            tags = [f"{key}={o.misconception}" for key, o in sorted(i.options.items()) if o.misconception]
            row["distractor_misconceptions"] = " ".join(tags)
            rows.append(row)
        for m in (m for m in tc.misconceptions if m.kc == k.id):
            rows.append({"type": "MISCONCEPTION", "id": m.id, "kc": m.kc, "text": m.statement,
                         "explanation_or_correction": m.correction, "reviewed_by": m.reviewed_by or ""})
    return rows


def export(store: ContentStore, topic: str, out_dir: Path) -> Path:
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{topic}_review.csv"
    with path.open("w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=COLUMNS, restval="")
        w.writeheader()
        w.writerows(rows_for(store, topic))
    return path


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("topic", nargs="?")
    ap.add_argument("--all", action="store_true", help="every topic that has at least one item")
    ap.add_argument("--out", type=Path, default=REPO_ROOT / "docs" / "review")
    args = ap.parse_args(argv)
    store = ContentStore(get_settings().content_dir())
    topics = [t for t in store.topics() if store.topic(t).items] if args.all else [args.topic]
    if not topics or topics == [None]:
        ap.error("give a topic or --all")
    for t in topics:
        print(export(store, t, args.out))


if __name__ == "__main__":
    sys.exit(main())
