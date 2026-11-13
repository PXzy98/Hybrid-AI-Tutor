"""Train the question type head (T5) and build its labelled data. Existing routing files are never touched.

Data (`data/question_type/questions.jsonl`, rebuilt with `--rebuild-data`): every row is a public question
with a `label` (concept or logistics) and a `course`; the split is always by course.
  - the S11 course-pack questions (type logistics -> logistics, concept and application -> concept),
  - the T4 ECE/CS routing questions (same rule; "current" and "hard" questions are concept questions),
  - every third question of each medical seed topic (all concept: they ask about the subject),
  - `supplement.jsonl`: questions written for T5 in six more subjects, half logistics and half concept
    questions that only mention words such as exam, grade, deadline or schedule as part of the subject.

Usage (in backend/):
    python -m app.routing.question_type_train [--rebuild-data] [--out PATH]
"""
import argparse
import hashlib
import json
from pathlib import Path

import numpy as np

from app.core.config import REPO_ROOT, get_settings
from app.routing import question_type
from app.routing.models import encode

DATA_DIR = REPO_ROOT / "data" / "question_type"
DATA_PATH = DATA_DIR / "questions.jsonl"
S11_DIR = REPO_ROOT / "eval" / "course-rag-packs" / "questions"
T4_PATH = REPO_ROOT / "data" / "routing" / "ece_cs_questions.jsonl"
SEED_PATH = REPO_ROOT / "data" / "routing" / "seed.jsonl"
SUPPLEMENT_PATH = DATA_DIR / "supplement.jsonl"
LABELS = ("concept", "logistics")
# Courses that are never trained on in the held-out evaluation (a mix of S11 packs, a seed topic, supplement).
TEST_COURSES = ("mit_hst151_pharmacology", "mit_6_006_algorithms", "migraine", "supp_economics",
                "supp_nursing")
C = 4.0  # inverse regularisation, as the routing LR head


def _lines(path: Path) -> list[dict]:
    return [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]


def build_rows() -> list[dict]:
    rows = []
    for path in sorted(S11_DIR.glob("*.jsonl")):
        for r in _lines(path):
            rows.append({"question": r["question"], "course": path.stem, "source": "s11",
                         "label": "logistics" if r["type"] == "logistics" else "concept"})
    for r in _lines(T4_PATH):
        rows.append({"question": r["question"], "course": r["pack"], "source": "t4",
                     "label": "logistics" if r["type"] == "logistics" else "concept"})
    taken: dict[str, int] = {}
    for r in _lines(SEED_PATH):
        taken[r["topic"]] = taken.get(r["topic"], 0) + 1
        if taken[r["topic"]] % 3 == 0:
            rows.append({"question": r["question"], "course": r["topic"], "source": "seed",
                         "label": "concept"})
    for r in _lines(SUPPLEMENT_PATH):
        rows.append({**r, "source": "supplement"})
    seen, unique = set(), []
    for r in rows:  # the same question in S11 and T4 counts once
        key = r["question"].strip().casefold()
        if key not in seen and r["label"] in LABELS:
            seen.add(key)
            unique.append(r)
    return unique


def write_rows(rows: list[dict], path: Path = DATA_PATH) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", encoding="utf-8", newline="\n") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")


def read_rows(path: Path = DATA_PATH) -> list[dict]:
    rows = _lines(path)
    keys = [r["question"].strip().casefold() for r in rows]
    if len(set(keys)) != len(keys) or any(r["label"] not in LABELS or not r["course"] for r in rows):
        raise ValueError("question type data: duplicate question, unknown label or missing course")
    return rows


def fit(x: np.ndarray, y: np.ndarray):
    from sklearn.linear_model import LogisticRegression

    return LogisticRegression(C=C, class_weight="balanced", max_iter=2000, random_state=42).fit(x, y)


def labels_of(rows: list[dict]) -> np.ndarray:
    return np.array([int(r["label"] == "logistics") for r in rows])


def save(model, x: np.ndarray, rows: list[dict], out: Path, cfg) -> None:
    metadata = {
        "schema_version": question_type.SCHEMA_VERSION,
        "embedding_model": cfg.embedding_model,
        "dimension": int(x.shape[1]),
        "threshold": 0.5,
        "training_count": len(rows),
        "labels": list(LABELS),
        "dataset_sha256": hashlib.sha256(DATA_PATH.read_bytes()).hexdigest(),
    }
    out.parent.mkdir(parents=True, exist_ok=True)
    # Plain arrays and JSON metadata: no pickle, no sklearn object at runtime.
    np.savez_compressed(out, metadata=np.array(json.dumps(metadata)),
                        coef=model.coef_[0].astype(np.float32), intercept=model.intercept_.astype(np.float32))


def train(out: Path | None = None, allow_download: bool = False) -> dict:
    cfg = get_settings().routing
    rows = read_rows()
    x = encode([r["question"] for r in rows], cfg, allow_download=allow_download)
    y = labels_of(rows)
    out = out or question_type.weights_path(cfg)
    save(fit(x, y), x, rows, out, cfg)
    print(f"Saved question type head: {out}")
    return {"rows": len(rows), "path": str(out)}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--rebuild-data", action="store_true", help="rewrite the data file from its sources")
    parser.add_argument("--out", type=Path, help="weight file (default: next to the routing models)")
    parser.add_argument("--allow-download", action="store_true")
    args = parser.parse_args()
    if args.rebuild_data:
        write_rows(build_rows())
    print(json.dumps(train(args.out, args.allow_download)))


if __name__ == "__main__":
    main()
