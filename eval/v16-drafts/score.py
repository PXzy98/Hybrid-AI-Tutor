"""V16: the rubric table of the drafts (automatic checks plus the reviewer's scores).

`--blind FILE` writes every draft of results/drafts_before.jsonl and drafts_after.jsonl in a random order
with neutral IDs (D01, D02, ...) and the key to FILE.key.json, for scoring without seeing the version.
Without `--blind` the script reads results/scores.json (the reviewer's scores per draft, keyed
"<label>|<case>|<kind>"), adds the automatic checks and prints the tables of the report.

Rubric (the same for every version and kind):
- valid: the draft passed the version's own validators (`parse_content`, or `parse_questions` for quiz
  questions); a failed draft scores edit 3 and nothing else;
- wrong: items (or, for one-text drafts, statements) that are factually wrong or, for questions, have no or
  more than one correct answer (the reviewer's judgement, with the reason in `note`);
- fit: 2 everything is about the module's material, 1 partly generic or off the material, 0 not about it;
- dup: KC drafts only, items that repeat a KC the course already has (same name, or the same idea renamed);
- edit: how much an instructor would have to change: 0 none, 1 small, 2 large, 3 unusable or failed.
Automatic: items, exact repeats of existing KC names in the model's raw answer and in the kept draft, and
quiz questions written about the material ("the text", "passage 3"; V17 W24): in the stem or options, in the
explanation, and with a passage number.

Usage: python eval/v16-drafts/score.py [--blind FILE] [--labels before,after]
"""
import argparse
import json
import random
import re
from pathlib import Path

HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
KINDS = ("kcs", "check_items", "misconceptions", "quiz", "project_ideas", "sample_proposal", "faq")
# what V17 W24 forbids: questions written about the material instead of the subject
_PASSAGE = re.compile(r"\b(the|this|that) (passage|text|excerpt|lecture|notes|course material)s?\b"
                      r"|\bpassages? \d|\bevidence \d", re.I)
_NUMBER = re.compile(r"\bpassages? \d|\bevidence \d", re.I)


def load(label: str) -> list[dict]:
    path = RESULTS / f"drafts_{label}.jsonl"
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def raw_items(row: dict) -> list[dict]:
    try:
        text = row["raw"][-1]
        body = text[text.find("{"):text.rfind("}") + 1]
        return json.loads(body).get("items") or []
    except (IndexError, ValueError, AttributeError):
        return []


def automatic(row: dict, existing: set[str]) -> dict:
    content = row.get("content") or {}
    auto = {"items": None, "raw_repeats": None, "kept_repeats": None, "about_passage": None}
    if row["kind"] == "quiz":
        questions = content.get("questions") or []
        auto["items"] = len(questions)
        auto["about_passage"] = (sum(bool(_PASSAGE.search(" ".join([q["stem"], *q["options"]])))
                                     for q in questions),
                                 sum(bool(_PASSAGE.search(q["explanation"])) for q in questions),
                                 sum(bool(_NUMBER.search(q["explanation"])) for q in questions))
    elif "items" in content:
        auto["items"] = len(content["items"])
    if row["kind"] == "kcs":
        auto["raw_repeats"] = sum(str(i.get("name", "")).casefold() in existing for i in raw_items(row))
        auto["kept_repeats"] = sum(i["name"].casefold() in existing for i in content.get("items") or [])
    return auto


def render(row: dict) -> str:
    """A draft as plain text for the reviewer."""
    if not row["ok"]:
        return f"FAILED: {row['error']}"
    content = row["content"]
    if "title" in content:
        return f"# {content['title']}\n{content['body']}"
    if row["kind"] == "quiz":
        lines = []
        for n, q in enumerate(content["questions"], 1):
            opts = " / ".join(f"[{'x' if i == q['answer'] else ' '}] {o}" for i, o in enumerate(q["options"]))
            answer = "" if q["options"] else f" (answer: {'True' if q['answer'] == 0 else 'False'})"
            lines.append(f"{n}. ({q['kind']}, kc={q['kc']}) {q['stem']}{answer}\n   {opts}\n"
                         f"   why: {q['explanation']}")
        return "\n".join(lines)
    lines = []
    for n, item in enumerate(content["items"], 1):
        if row["kind"] == "kcs":
            lines.append(f"{n}. {item['name']}: {item['definition']} (prereq: {item['prerequisite_names']})")
        elif row["kind"] == "check_items":
            opts = " / ".join(f"[{'x' if i == item['correct_index'] else ' '}] {o}"
                              for i, o in enumerate(item["options"]))
            lines.append(f"{n}. {item['question']} (kc: {item['kc_names']})\n   {opts}\n"
                         f"   why: {item['explanation']}")
        else:
            lines.append(f"{n}. {item['name']} (kc: {item['kc_name']})\n"
                         f"   wrong: {item['incorrect_belief']}\n   right: {item['correction']}")
    return "\n".join(lines)


def blind(out: Path, labels: list[str]) -> None:
    rows = [r for label in labels for r in load(label)]
    random.Random(16).shuffle(rows)
    key, parts = {}, []
    # grouped by kind and case (so the two versions of one input are scored side by side), in random order
    order = sorted(range(len(rows)), key=lambda i: (KINDS.index(rows[i]["kind"]), rows[i]["case"], i))
    for n, i in enumerate(order, 1):
        row = rows[i]
        did = f"D{n:02d}"
        key[did] = f"{row['label']}|{row['case']}|{row['kind']}"
        parts.append(f"===== {did} {row['case']} {row['kind']}\n{render(row)}\n")
    out.write_text("\n".join(parts), encoding="utf-8")
    out.with_suffix(".key.json").write_text(json.dumps(key, indent=1), encoding="utf-8")
    print(f"wrote {len(rows)} drafts to {out}")


def mean(values: list) -> str:
    values = [v for v in values if v is not None]
    return f"{sum(values) / len(values):.1f}" if values else "-"


def table(labels: list[str]) -> None:
    inputs = json.loads((RESULTS / "inputs.json").read_text(encoding="utf-8"))
    existing = {c["id"]: {k["name"].casefold() for k in c["existing_kcs"]} for c in inputs["cases"]}
    scores = json.loads((RESULTS / "scores.json").read_text(encoding="utf-8"))
    print("| Kind | Version | Valid | Items (mean) | Wrong items | Fit (0-2) | KC repeats raw / kept / "
          "same idea | \"The text\" in stem / explanation / passage number | Edit (0-3) |")
    print("|---|---|---|---|---|---|---|---|---|")
    for kind in KINDS:
        for label in labels:
            rows = [r for r in load(label) if r["kind"] == kind]
            autos = [automatic(r, existing[r["case"]]) for r in rows]
            marks = [scores[f"{label}|{r['case']}|{kind}"] for r in rows]
            ok = [m for r, m in zip(rows, marks, strict=True) if r["ok"]]
            repeats = "-"
            if kind == "kcs":
                repeats = (f"{sum(a['raw_repeats'] for a in autos)} / {sum(a['kept_repeats'] for a in autos)}"
                           f" / {sum(m.get('dup', 0) for m in ok)}")
            passage = " / ".join(str(sum(a["about_passage"][n] for a in autos)) for n in range(3)) \
                if kind == "quiz" else "-"
            print(f"| {kind} | {label} | {sum(r['ok'] for r in rows)}/{len(rows)} | "
                  f"{mean([a['items'] for a in autos])} | {sum(m.get('wrong', 0) for m in ok)} | "
                  f"{mean([m.get('fit') for m in ok])} | {repeats} | {passage} | "
                  f"{mean([m['edit'] for m in marks])} |")


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--blind", type=Path)
    parser.add_argument("--labels", default="before,after")
    args = parser.parse_args()
    labels = args.labels.split(",")
    if args.blind:
        blind(args.blind, labels)
    else:
        table(labels)


if __name__ == "__main__":
    main()
