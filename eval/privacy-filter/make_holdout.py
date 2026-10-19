"""Generate the texts of the E6 held-out set with a different model than the one that wrote the question bank
(run once; output committed).

    .venv\\Scripts\\python eval\\privacy-filter\\make_holdout.py [--model gemma4:e4b]

The recognizers were tuned on cases.jsonl, so its numbers are optimistic. This set is written after the rules
were frozen, by gemma4 instead of qwen, without the templates: new names, new wordings, new contexts.
The generator's own labels were unusable (it marks every medical term as a health detail, also in general
questions), so only its texts are kept: holdout_raw.jsonl. Every message is then labelled by hand in
holdout.jsonl (entities, personal_health, group), see holdout_review.md.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))
from app.core.config import get_settings  # noqa: E402

COMMON = ("You write test data for a privacy filter in a university health-course tutor (topics: blood pressure, "
          "diabetes, asthma, migraine, pneumonia). Students type short, informal messages, sometimes with typos. "
          "All people and numbers must be invented. Student numbers have 9 digits and start with 300. Phone "
          "numbers are Canadian. Vary names across cultures and vary the wording; do not reuse a sentence shape. ")
SCENARIOS = [
    ("positive", "own_name", 10, "Each message contains the student's own full name and a course question."),
    ("positive", "other_name", 10, "Each message mentions a classmate, friend or relative by full name, plus a "
                                   "course question."),
    ("positive", "student_id", 8, "Each message contains the student's student number (some with spaces or a "
                                  "dash, some with words like 'student no', 'ID', 'stu#')."),
    ("positive", "contact", 8, "Each message contains the student's email address or phone number."),
    ("positive", "grade", 10, "Each message reveals the student's own mark, score, letter grade or GPA."),
    ("positive", "health_self", 12, "Each message reveals the student's own diagnosis, symptom, medication or "
                                    "test result, then asks a general question."),
    ("positive", "health_family", 8, "Each message reveals a named or unnamed family member's or friend's "
                                     "diagnosis, symptom or medication."),
    ("positive", "combo", 8, "Each message combines two or three of: own name, student number, email, grade, "
                             "own health detail."),
    ("negative", "general", 12, "General course questions with NO personal information: may contain medical "
                                "terms, drug names, numbers like doses or readings in general, statistics."),
    ("negative", "eponym", 8, "Course questions that contain a scientist's or disease eponym (e.g. a named "
                              "law, test, sign, syndrome or scale) and NO personal information."),
    ("negative", "hypothetical", 8, "Questions about health in general or about a hypothetical patient ('a "
                                    "patient with...', 'if someone has...') with NO personal information."),
]
FORMAT = ('Write {n} messages. {spec} Reply with JSON only: {{"items": [{{"text": "...", "entities": [{{"type": '
          '"PERSON|EMAIL_ADDRESS|PHONE_NUMBER|STUDENT_ID|GRADE|HEALTH_DETAIL", "text": "exact substring"}}], '
          '"personal_health": true|false}}]}}.')


def generate(http, url, model, n, spec, seed=61):
    r = http.post(f"{url}/v1/chat/completions", json={
        "model": model, "temperature": 0.9, "seed": seed, "max_tokens": 6000,
        "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": COMMON + FORMAT.format(n=n, spec=spec)}]})
    text = r.json()["choices"][0]["message"]["content"] or "{}"
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)).get("items", []) if m else []


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--model", default="gemma4:e4b")
    ap.add_argument("--seed", type=int, default=61)
    ap.add_argument("--out", default="holdout_raw.jsonl", help="v1 (dev): holdout_raw.jsonl, v2 (test): holdout2_raw.jsonl")
    a = ap.parse_args(argv)
    url = get_settings().ollama_url.rstrip("/")
    http = httpx.Client(timeout=600)
    out, seen = [], set()
    for group, variant, n, spec in SCENARIOS:
        items = generate(http, url, a.model, n, spec, a.seed)
        for it in items:
            if not it.get("text") or it["text"] in seen:
                continue
            seen.add(it["text"])
            out.append({"raw_id": f"{'S' if a.seed != 61 else 'R'}{len(out) + 1:03d}", "asked_for": f"{group}/{variant}", "text": it["text"],
                        "generator_labels": it.get("entities", []),
                        "generator_personal_health": it.get("personal_health")})
        print(f"{group}/{variant}: {len(items)} generated", file=sys.stderr)
    with (HERE / a.out).open("w", encoding="utf-8") as f:
        for c in out:
            f.write(json.dumps(c, ensure_ascii=False) + "\n")
    print(f"{len(out)} texts", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
