"""S11: retrieval evaluation of the course index on the open course packs (no model, no network).

Each pack of `data/demo_courses/` (unpack first: `python scripts/fetch_open_courses.py unpack`) is staged with
`stage_demo_course` into a temporary data root and indexed by `IndexedCourseRetriever` behind the real privacy
scan of the pack's course type. Questions are in `questions/<pack>.jsonl` (written from the pack material;
they are public text, not student data). For every question the harness retrieves k passages twice: scoped
to the module the question is about (plus the course-level files, as in the product) and course-wide.

A question counts as a hit at rank r when the r-th returned passage comes from one of the gold files.
hit@1, hit@k and MRR are computed over passages (several passages of one file count separately). Questions
whose gold files the privacy scan refused cannot be answered and are left out of the metrics (listed in the
report). Questions with `gold: []` are not in the material; for them only the top score is reported, to
check that it stays low.

Usage (repository root):
    python eval/course-rag-packs/run.py [--smoke] [--packs a,b] [--k 4] [--out DIR] [--check]
`--check` only verifies the question files: every `evidence` pattern must occur in a gold file.
"""
import argparse
import json
import re
import statistics
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.privacy.profiles import privacy_profile  # noqa: E402
from app.rag.course_retriever import IndexedCourseRetriever  # noqa: E402
from app.rag.demo_courses import stage_demo_course  # noqa: E402
from app.rag.documents import DocumentError, extract_text  # noqa: E402
from app.rag.privacy_adapter import privacy_scan_callback  # noqa: E402

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE))
from analysis_text import ANALYSIS  # noqa: E402

PACKS_DIR = ROOT / "data" / "demo_courses"
TYPES = ("concept", "application", "logistics")
COURSE_ID = 1


def load_questions(pack: str) -> list[dict]:
    rows = [json.loads(line) for line in (HERE / "questions" / f"{pack}.jsonl").read_text(
        encoding="utf-8").splitlines() if line.strip()]
    ids = [row["id"] for row in rows]
    if len(ids) != len(set(ids)):
        raise ValueError(f"{pack}: duplicate question IDs")
    for row in rows:
        if row["type"] not in TYPES or not row["question"].strip():
            raise ValueError(f"{row['id']}: bad type or empty question")
        if row["module_order"] is not None and type(row["module_order"]) is not int:
            raise ValueError(f"{row['id']}: module_order must be an integer or null")
    return rows


def smoke_subset(rows: list[dict]) -> list[dict]:
    """First module question, first logistics question and first question without an answer."""
    picks = [next(r for r in rows if r["gold"] and r["module_order"] is not None),
             next(r for r in rows if r["gold"] and r["type"] == "logistics"),
             next(r for r in rows if not r["gold"])]
    return picks


def file_map(pack_dir: Path, manifest: dict) -> dict[tuple[str, str], str]:
    """(staged folder, staged file name) -> file path relative to the pack."""
    mapping: dict[tuple[str, str], str] = {}
    entries = [("_course", rel) for rel in manifest["documents"]]
    entries += [(str(m["module_order"]), m["demo_note"]) for m in manifest["modules"]]
    for folder, rel in entries:
        key = (folder, Path(rel).name)
        if key in mapping:
            raise ValueError(f"two files named {key[1]} in {folder}")
        mapping[key] = rel
    return mapping


def build_index(pack_dir: Path, manifest: dict,
                data_root: Path) -> tuple[IndexedCourseRetriever, list[str], str]:
    """Stage and index the pack. Returns (retriever, refused file paths, how the index was built)."""
    stage_demo_course(pack_dir, data_root, COURSE_ID)
    mapping = file_map(pack_dir, manifest)
    scan = privacy_scan_callback(privacy_profile(manifest["course_type"]))
    retriever = IndexedCourseRetriever(data_root, scan=scan)
    try:
        retriever.rebuild(COURSE_ID)
        return retriever, [], "whole course"
    except DocumentError:
        pass
    # The whole-course rebuild fails closed on the first refused file: scan per file, drop the refused ones.
    refused: list[str] = []
    materials = data_root / "courses" / str(COURSE_ID) / "materials"
    for folder in sorted(materials.iterdir()):
        for path in sorted(folder.iterdir()):
            try:
                text = extract_text(path, preserve_pdf_pages=path.suffix.lower() == ".pdf")
                ok = scan(text) is True
            except DocumentError:
                ok = False
            if not ok:
                refused.append(mapping[(folder.name, path.name.removeprefix("reading_"))])
                path.unlink()
    retriever.rebuild(COURSE_ID)
    return retriever, sorted(refused), "per file (refused files skipped)"


def source_to_pack_path(source: str, mapping: dict[tuple[str, str], str]) -> str:
    _, _, folder, name = source.split("/", 3)
    return mapping[(folder, name)]


def rank_of(files: list[str], gold: set[str]) -> int | None:
    for position, name in enumerate(files, 1):
        if name in gold:
            return position
    return None


def metrics(ranks: list[int | None], k: int) -> dict:
    n = len(ranks)
    if not n:
        return {"n": 0, "hit@1": None, f"hit@{k}": None, "mrr": None}
    return {"n": n, "hit@1": round(sum(r == 1 for r in ranks) / n, 3),
            f"hit@{k}": round(sum(r is not None for r in ranks) / n, 3),
            "mrr": round(sum(1 / r for r in ranks if r) / n, 3)}


def evaluate_pack(pack: str, rows: list[dict], k: int) -> dict:
    pack_dir = PACKS_DIR / pack
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    mapping = file_map(pack_dir, manifest)
    with tempfile.TemporaryDirectory(prefix="pack-eval-") as tmp:
        retriever, refused, how = build_index(pack_dir, manifest, Path(tmp))
        indexed = len(retriever._snapshot(COURSE_ID).passages)
        results = []
        for row in rows:
            gold = set(row["gold"])
            entry = {"id": row["id"], "type": row["type"], "module_order": row["module_order"],
                     "gold": sorted(gold), "gold_refused": sorted(gold & set(refused))}
            for mode, module in (("scoped", row["module_order"]), ("course", None)):
                if mode == "course" and row["module_order"] is None:
                    entry["course"] = entry["scoped"]
                    continue
                hits = retriever.retrieve(COURSE_ID, module, row["question"], k=k)
                files = [source_to_pack_path(h.source, mapping) for h in hits]
                entry[mode] = {"files": files, "scores": [h.score for h in hits],
                               "rank": rank_of(files, gold) if gold else None,
                               "top_score": hits[0].score if hits else 0.0}
            results.append(entry)
    return {"pack": pack, "course_type": manifest["course_type"], "index": how, "passages": indexed,
            "refused_files": refused, "results": results}


def summarize(pack_result: dict, k: int) -> dict:
    """Metrics per type and overall, for both retrieval modes; top scores of unanswerable questions."""
    answerable = [r for r in pack_result["results"] if set(r["gold"]) - set(r["gold_refused"])]
    out: dict = {"skipped_gold_refused": [r["id"] for r in pack_result["results"]
                                          if r["gold"] and set(r["gold"]) <= set(r["gold_refused"])]}
    for mode in ("scoped", "course"):
        per_type = {t: metrics([r[mode]["rank"] for r in answerable if r["type"] == t], k) for t in TYPES}
        per_type["all"] = metrics([r[mode]["rank"] for r in answerable], k)
        out[mode] = per_type
        top = [r[mode]["top_score"] for r in answerable]
        none = [r[mode]["top_score"] for r in pack_result["results"] if not r["gold"]]
        out[f"{mode}_top_score"] = {
            "answerable_median": round(statistics.median(top), 3) if top else None,
            "answerable_p10": round(sorted(top)[len(top) // 10], 3) if top else None,
            "unanswerable_n": len(none),
            "unanswerable_mean": round(statistics.mean(none), 3) if none else None,
            "unanswerable_max": round(max(none), 3) if none else None,
            # Chance that a random answerable question scores higher than a random unanswerable one.
            "auc": round(sum((a > b) + 0.5 * (a == b) for a in top for b in none) / (len(top) * len(none)), 3)
            if top and none else None,
        }
    return out


def check_questions(packs: list[str]) -> int:
    """Every evidence pattern must occur in at least one gold file; gold files must exist."""
    problems = 0
    for pack in packs:
        pack_dir = PACKS_DIR / pack
        text: dict[str, str] = {}
        for row in load_questions(pack):
            for rel in row["gold"]:
                if rel not in text:
                    path = pack_dir / rel
                    if not path.is_file() or rel.startswith("instructor_only"):
                        print(f"{row['id']}: gold file {rel} missing or instructor-only")
                        problems += 1
                        continue
                    text[rel] = re.sub(r"\s+", " ", extract_text(path, preserve_pdf_pages=True))
            for pattern in row.get("evidence", []):
                if not any(re.search(pattern, text.get(rel, ""), re.I) for rel in row["gold"]):
                    print(f"{row['id']}: evidence {pattern!r} not found in the gold files")
                    problems += 1
    print("question files ok" if not problems else f"{problems} problem(s)")
    return problems


def fmt(value) -> str:
    return "-" if value is None else f"{value:.2f}"


def write_report(summary: dict, packs: list[dict], k: int, smoke: bool, path: Path) -> None:
    lines = ["# Retrieval evaluation on the open course packs (S11)", ""]
    if smoke:
        lines += ["Smoke run (3 questions per course): not a result.", ""]
    lines += [
        f"Retrieval of k={k} passages by `IndexedCourseRetriever` (word and character TF-IDF), index built "
        "behind the real privacy scan. *Scoped*: restricted to the question's module plus the course-level "
        "files, as the product does when a module is chosen. *Course-wide*: `module_id=None`. "
        "A hit at rank r "
        "means the r-th passage comes from a gold file; hit@1, hit@k and MRR are over passages. Questions "
        "without a module (logistics, course-level) are the same in both modes.", ""]
    for pack in packs:
        s = summary[pack["pack"]]
        lines += [f"## {pack['pack']}", "",
                  f"Course type `{pack['course_type']}`; {pack['passages']} passages; index built "
                  f"{pack['index']}.", ""]
        if pack["refused_files"]:
            lines += ["Files refused by the privacy scan (not indexed): "
                      + ", ".join(f"`{f}`" for f in pack["refused_files"]) + ".", ""]
        if s["skipped_gold_refused"]:
            lines += ["Questions left out because every gold file was refused: "
                      + ", ".join(s["skipped_gold_refused"]) + ".", ""]
        lines += [f"| Type | n | scoped hit@1 | scoped hit@{k} | scoped MRR | course-wide hit@1 | "
                  f"course-wide hit@{k} | course-wide MRR |", "|---|---|---|---|---|---|---|---|"]
        for t in (*TYPES, "all"):
            a, b = s["scoped"][t], s["course"][t]
            lines.append(f"| {t} | {a['n']} | {fmt(a['hit@1'])} | {fmt(a[f'hit@{k}'])} | {fmt(a['mrr'])} | "
                         f"{fmt(b['hit@1'])} | {fmt(b[f'hit@{k}'])} | {fmt(b['mrr'])} |")
        c = s["course_top_score"]
        lines += ["", f"Top score (course-wide): answerable median {fmt(c['answerable_median'])}, 10th "
                  f"percentile {fmt(c['answerable_p10'])}; {c['unanswerable_n']} questions not in the "
                  "material: "
                  f"mean {fmt(c['unanswerable_mean'])}, max {fmt(c['unanswerable_max'])}; chance that an "
                  f"answerable question outscores an unanswerable one {fmt(c['auc'])}.", ""]
    lines += ["## All packs", "", f"| Pack | scoped hit@1 | scoped hit@{k} | scoped MRR | "
              f"course-wide hit@1 | course-wide hit@{k} | course-wide MRR | unanswerable max top score |",
              "|---|---|---|---|---|---|---|---|"]
    for pack in packs:
        s = summary[pack["pack"]]
        a, b = s["scoped"]["all"], s["course"]["all"]
        lines.append(f"| {pack['pack']} | {fmt(a['hit@1'])} | {fmt(a[f'hit@{k}'])} | {fmt(a['mrr'])} | "
                     f"{fmt(b['hit@1'])} | {fmt(b[f'hit@{k}'])} | {fmt(b['mrr'])} | "
                     f"{fmt(s['course_top_score']['unanswerable_max'])} |")
    lines += ["", "## Misses (course-wide, no gold file in the top results)", ""]
    for pack in packs:
        for r in pack["results"]:
            if r["gold"] and not r["gold_refused"] and r["course"]["rank"] is None:
                top = r["course"]["files"][0] if r["course"]["files"] else "nothing"
                lines.append(f"- `{r['id']}` ({r['type']}): gold {', '.join(f'`{g}`' for g in r['gold'])}; "
                             f"top result `{top}` (score {r['course']['top_score']:.2f}); scoped rank "
                             f"{r['scoped']['rank']}")
    if not smoke:
        lines += ["", ANALYSIS.rstrip(), ""]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--smoke", action="store_true", help="3 questions per course, for CI")
    parser.add_argument("--packs", help="comma-separated pack names (default: every pack with questions)")
    parser.add_argument("--k", type=int, default=4)
    parser.add_argument("--out", type=Path, help="output folder (default: results/; none for --smoke)")
    parser.add_argument("--check", action="store_true", help="verify the question files and stop")
    args = parser.parse_args()
    packs = args.packs.split(",") if args.packs else sorted(
        p.stem for p in (HERE / "questions").glob("*.jsonl"))
    missing = [p for p in packs if not (PACKS_DIR / p / "manifest.json").is_file()]
    if missing:
        print(f"Not unpacked: {', '.join(missing)}. Run: python scripts/fetch_open_courses.py unpack")
        return 2
    if args.check:
        return 1 if check_questions(packs) else 0

    results, summary = [], {}
    for pack in packs:
        rows = load_questions(pack)
        if args.smoke:
            rows = smoke_subset(rows)
        result = evaluate_pack(pack, rows, args.k)
        results.append(result)
        summary[pack] = summarize(result, args.k)
        a = summary[pack]["course"]["all"]
        print(f"{pack}: n={a['n']} course-wide hit@1={fmt(a['hit@1'])} "
              f"hit@{args.k}={fmt(a[f'hit@{args.k}'])} mrr={fmt(a['mrr'])}; "
              f"refused files: {len(result['refused_files'])}")
    if args.smoke:
        weak = [p for p in packs if (summary[p]["course"]["all"][f"hit@{args.k}"] or 0) < 0.5]
        print("smoke ok" if not weak else f"smoke: hit@{args.k} below 0.5 for {', '.join(weak)}")
        out = args.out
    else:
        weak = []
        out = args.out or HERE / "results"
    if out:
        out.mkdir(parents=True, exist_ok=True)
        (out / "metrics.json").write_text(json.dumps(
            {"k": args.k, "smoke": args.smoke, "packs": summary,
             "details": {r["pack"]: {"index": r["index"], "passages": r["passages"],
                                     "refused_files": r["refused_files"], "questions": r["results"]}
                         for r in results}}, indent=2) + "\n", encoding="utf-8")
        write_report(summary, results, args.k, args.smoke, out / "report.md")
        print(f"wrote {out / 'metrics.json'} and {out / 'report.md'}")
    return 1 if weak else 0


if __name__ == "__main__":
    sys.exit(main())
