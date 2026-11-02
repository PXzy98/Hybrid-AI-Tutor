"""Build a labelled held-out set from raw generator texts and hand labels (used for v3).

    .venv\\Scripts\\python eval\\privacy-filter\\label_holdout.py labels3.txt holdout3.jsonl holdout3a_raw.jsonl ...

Labels file, one message per line:  <raw_id> | <H or -> | TYPE:text ; TYPE:text ...
H marks a personal health question (must stay local). Entity texts must occur verbatim in the message. A line
"<raw_id> | skip" drops a message (duplicate, not a student message, or unusable). Messages without entities
form the negative set; the generator's own scenario becomes the variant.
"""
import json
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
TYPES = {"PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "STUDENT_ID", "GRADE", "HEALTH_DETAIL"}


def main(argv: list[str]) -> int:
    labels_path, out_name, *raw_names = argv
    raw = {}
    for name in raw_names:
        for line in (HERE / name).read_text("utf-8").splitlines():
            if line.strip():
                r = json.loads(line)
                raw[r["raw_id"]] = r
    out, errors = [], []
    for n, line in enumerate(Path(labels_path).read_text("utf-8").splitlines(), 1):
        if not line.strip() or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        rid = parts[0]
        if rid not in raw:
            errors.append(f"line {n}: unknown id {rid}")
            continue
        if parts[1] == "skip":
            continue
        text, ents = raw[rid]["text"], []
        for item in filter(None, (x.strip() for x in (parts[2] if len(parts) > 2 else "").split(";"))):
            kind, _, value = item.partition(":")
            if kind not in TYPES or value not in text:
                errors.append(f"line {n} ({rid}): bad entity {item!r}")
            ents.append({"type": kind, "text": value})
        health = parts[1] == "H"
        if health and not any(e["type"] == "HEALTH_DETAIL" for e in ents):
            errors.append(f"line {n} ({rid}): H without a HEALTH_DETAIL entity")
        variant = raw[rid]["asked_for"].split("/")[1]
        out.append({"id": f"V{len(out) + 1:03d}", "raw_id": rid, "group": "positive" if ents else "negative",
                    "variant": variant, "text": text, "entities": ents, "personal_health": health, "keep": [],
                    "self_name": None, "conversation": None})
    unlabelled = sorted(set(raw) - {line.split("|")[0].strip() for line in
                                    Path(labels_path).read_text("utf-8").splitlines() if "|" in line})
    if unlabelled:
        errors.append(f"not labelled: {', '.join(unlabelled)}")
    if errors:
        print("\n".join(errors), file=sys.stderr)
        return 1
    (HERE / out_name).write_text("".join(json.dumps(c, ensure_ascii=False) + "\n" for c in out), "utf-8")
    pos = sum(c["group"] == "positive" for c in out)
    print(f"{len(out)} messages: {pos} positive, {len(out) - pos} negative, "
          f"{sum(c['personal_health'] for c in out)} personal health")
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv[1:]))
