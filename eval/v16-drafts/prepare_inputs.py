"""V16: the inputs of the draft comparison, built once so "before" and "after" draft from the same passages.

Five cases (one module each of three open course packs). Each pack is staged and indexed with the S11
harness (`eval/course-rag-packs/run.py`: `stage_demo_course`, the course type's privacy scan, the course index
with the semantic encoder; `instructor_only/` is never staged). For every case and draft kind the passages are
retrieved the way the draft jobs do it on main (`draft_jobs._passages` with the default scope,
`quiz_drafts._chunks`): the query is the module title, the kind's query words and the module's existing KCs;
8 passages of at most 1,200 characters for drafts, 6 for quiz questions. The job's query building did not
change between the two versions for these inputs (no focus and no request), so retrieving once is the same as
retrieving in each.

Every case also has three existing KCs (written for this test), so the course is not empty: the KC drafts can
repeat them (#129 leaves them out) and check items and misconceptions must refer to them.

Usage (repository root, packs unpacked): python eval/v16-drafts/prepare_inputs.py [--packs DIR]
`--packs` is the unpacked `data/demo_courses` folder (default: the one of this checkout; a worktree may use
the main checkout's).
Writes eval/v16-drafts/results/inputs.json (open course text, CC BY-NC-SA 4.0).
"""
import argparse
import importlib.util
import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "backend"))

from app.instructor_ai import draft_jobs  # noqa: E402

_spec = importlib.util.spec_from_file_location("course_rag_packs_run", ROOT / "eval/course-rag-packs/run.py")
rag_packs = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rag_packs)

PACKS = ROOT / "data" / "demo_courses"
DRAFT_KINDS = ("kcs", "check_items", "misconceptions", "project_ideas", "sample_proposal", "faq")
QUIZ_PASSAGES = 6

CASES = [
    {"id": "cs50_w2", "pack": "harvard_cs50x", "module_order": 3, "kcs": [
        ("Compilation steps", "Turning C source into machine code: preprocessing, compiling, assembling and "
                              "linking."),
        ("Arrays", "A sequence of values of the same type stored back to back in memory, accessed by index."),
        ("Strings as character arrays", "A C string is an array of chars ended by the NUL character \\0."),
    ]},
    {"id": "cs50_w4", "pack": "harvard_cs50x", "module_order": 5, "kcs": [
        ("Pointers", "A variable that stores the memory address of another value."),
        ("Dynamic memory allocation", "Requesting memory at run time with malloc and returning it with "
                                      "free."),
        ("Hexadecimal notation", "Base-16 numbers, written with the prefix 0x, used to show memory "
                                 "addresses."),
    ]},
    {"id": "e6002_l2", "pack": "mit_6_002_circuits", "module_order": 2, "kcs": [
        ("Kirchhoff's voltage law", "The sum of the voltages around any closed loop of a circuit is zero."),
        ("Kirchhoff's current law", "The sum of the currents flowing into any node of a circuit is zero."),
        ("Series and parallel resistors", "Resistances in series add; conductances in parallel add."),
    ]},
    {"id": "hst151_l1", "pack": "mit_hst151_pharmacology", "module_order": 1, "kcs": [
        ("Drug-receptor binding", "A drug binds reversibly to its receptor; occupancy follows the law of "
                                  "mass action with dissociation constant Kd."),
        ("Dose-response curve", "The graded response to a drug plotted against the log of its concentration; "
                                "EC50 is the concentration giving half the maximal effect."),
        ("Agonists and antagonists", "An agonist binds and activates a receptor; an antagonist binds without "
                                     "activating it and blocks the agonist."),
    ]},
    {"id": "hst151_l2", "pack": "mit_hst151_pharmacology", "module_order": 2, "kcs": [
        ("Volume of distribution", "The apparent volume a drug dose would occupy at the plasma "
                                   "concentration."),
        ("Clearance", "The volume of plasma cleared of the drug per unit time."),
        ("Elimination half-life", "The time for the plasma concentration to fall by half; "
                                  "t1/2 = 0.693 Vd/CL."),
    ]},
]


def _plain(chunk) -> dict:
    return {"source": chunk.source, "text": chunk.text[:draft_jobs.PASSAGE_CHARS]}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--packs", type=Path, default=PACKS)
    packs = parser.parse_args().packs
    out = {"license": "Passages are from MIT OpenCourseWare and Harvard CS50x, CC BY-NC-SA 4.0 "
                      "(see data/demo_courses/<pack>/README.md).", "cases": []}
    by_pack: dict[str, list[dict]] = {}
    for case in CASES:
        by_pack.setdefault(case["pack"], []).append(case)
    for pack, cases in by_pack.items():
        pack_dir = packs / pack
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        with tempfile.TemporaryDirectory() as tmp:
            retriever, refused, how = rag_packs.build_index(pack_dir, manifest, Path(tmp))
            print(f"{pack}: indexed {how}; refused {len(refused)} files")
            for case in cases:
                module = next(m for m in manifest["modules"] if m["module_order"] == case["module_order"])
                kc_text = [f"{name} {definition}" for name, definition in case["kcs"]]
                passages = {}
                for kind in DRAFT_KINDS:  # as draft_jobs.generate (no focus, no request)
                    query = " ".join([module["title"], draft_jobs._QUERY.get(kind, ""), *kc_text]).strip()
                    found = retriever.retrieve(rag_packs.COURSE_ID, case["module_order"], query,
                                               draft_jobs.PASSAGES)
                    passages[kind] = [_plain(c) for c in found]
                query = " ".join([module["title"], *kc_text])  # as quiz_drafts.draft
                found = retriever.retrieve(rag_packs.COURSE_ID, case["module_order"], query, QUIZ_PASSAGES)
                passages["quiz"] = [_plain(c) for c in found]
                out["cases"].append({"id": case["id"], "pack": pack, "course_type": manifest["course_type"],
                                     "module_order": case["module_order"], "module_title": module["title"],
                                     "existing_kcs": [{"name": n, "definition": d} for n, d in case["kcs"]],
                                     "refused_files": refused, "passages": passages})
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "results" / "inputs.json").write_text(json.dumps(out, indent=1, ensure_ascii=False) + "\n",
                                                  encoding="utf-8")
    print("wrote", HERE / "results" / "inputs.json")


if __name__ == "__main__":
    main()
