# ruff: noqa: E501
"""X10: the held-out E6 set of the biomedical engineering course type (`biomedical_engineering`).

Written blind from the profile: the generators get only the course subject and the kinds of personal data,
never the recognizer rules. Two steps, run once; outputs committed:

    generate   two generator families through OpenRouter (anthropic/claude-haiku-5.5, openai/gpt-6-luna)
               write short fictional student messages -> bme_holdout_raw.jsonl
    label      two stronger labellers (anthropic/claude-sonnet-5.5, openai/gpt-6.1-terra) label
               every message on their own -> bme_holdout.jsonl (both agree) and
               bme_holdout_disagreements.jsonl (a person decides; resolved rows are added to bme_holdout.jsonl)

    set OPENROUTER_API_KEY (environment or the repository's .env)
    .venv\\Scripts\\python eval\\privacy-filter\\make_bme_set.py generate
    .venv\\Scripts\\python eval\\privacy-filter\\make_bme_set.py label

Only invented people, numbers, keys and addresses are asked for (rule 6); no course material is sent. Same
record format as ece_holdout.jsonl; scored by course_sets.py.
"""
import argparse
import json
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1]))
from eval.common.env import env  # noqa: E402

URL = "https://openrouter.ai/api/v1/chat/completions"
GENERATORS = ["anthropic/claude-haiku-5.5", "openai/gpt-6-luna"]
LABELLERS = ["anthropic/claude-sonnet-5.5", "openai/gpt-6.1-terra"]
TYPES = ["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "STUDENT_ID", "GRADE", "HEALTH_DETAIL", "DATE_OF_BIRTH",
         "HEALTH_CARD", "ADDRESS", "POSTAL_CODE", "SECRET", "INTERNAL_ADDRESS", "REPO_URL"]

COMMON = ("You write test data for a privacy filter in the AI tutor of a university biomedical engineering "
          "course (medical devices, biosignals such as ECG, EEG and EMG, sensors and amplifiers, ADC and DAC, "
          "filters, medical imaging, diagnostic tests, lab work with microcontrollers and Python). Students "
          "type short, informal messages, sometimes with typos. Every person, number, e-mail, key and address "
          "must be invented: student numbers have 9 digits and start with 300; phone numbers are Canadian "
          "with 555; e-mails use example domains; keys contain FAKE or notreal; lab hosts use private "
          "address ranges. Vary names across cultures and vary the wording; do not reuse a sentence shape. ")
# (group, variant, messages per generator, what to write)
SCENARIOS = [
    ("positive", "own_name", 4, "Each message has the student's own full name and a course question."),
    ("positive", "other_name", 4, "Each message names a lab partner, TA or relative by full name, plus a course question."),
    ("positive", "student_id", 4, "Each message has the student's student number (some with spaces or a dash, some after 'ID', 'student no', 'stu#')."),
    ("positive", "contact", 4, "Each message has the student's e-mail address or phone number."),
    ("positive", "grade", 3, "Each message reveals the student's own mark, score or letter grade in the course."),
    ("positive", "lab_system", 5, "Each message pastes lab details: a private IP address or MAC address of a lab device, a repository URL with an account name, or an API key, token or password in code."),
    ("positive", "health_self", 5, "Each message reveals the student's own condition, symptom, medication, or own physiological reading (e.g. their own heart rate or ECG result), then asks a course question."),
    ("positive", "health_family", 3, "Each message reveals a named or unnamed relative's or friend's diagnosis, medication or test result."),
    ("positive", "combo", 3, "Each message combines two or three of: own name, student number, e-mail, own health detail, a lab key or address."),
    ("negative", "technical", 6, "Course questions with NO personal information: values with units (mV, Hz, dB, bits, kOhm), part numbers, sampling rates, filter design, code."),
    ("negative", "clinical", 4, "Course questions about a hypothetical or textbook patient or a general disease ('a patient with...', 'how does a pulse oximeter detect hypoxemia') with NO personal information about the student or anyone they know."),
    ("negative", "eponym", 3, "Course questions with a named law, lead, method or scale (e.g. Einthoven, Nyquist, Bland-Altman, Fourier) and NO personal information."),
]
GEN_FORMAT = 'Write {n} messages. {spec} Reply with JSON only: {{"items": [{{"text": "..."}}]}}.'
LABEL_PROMPT = (
    "Label one student message for a privacy test. List every piece of personal data as an exact substring "
    "with one type of: " + ", ".join(TYPES) + ". PERSON: full or partial names of real-seeming people (not "
    "eponyms like 'Einthoven triangle', not 'Dr.'). HEALTH_DETAIL: the shortest substring that states the "
    "health of the writer or of a person they know (diagnosis, symptom, medication, own reading); a "
    "hypothetical or textbook patient is NOT personal data. SECRET: only the key, token or password value. "
    "INTERNAL_ADDRESS: a private IP (with port if given) or MAC address. REPO_URL: a code host URL with an "
    "account name. Also give `personal_health` (true when the message reveals the health of the writer or "
    "someone they know) and `keep`: one to three course terms or values in the message that are not personal "
    "data and must not be removed. Reply with JSON only: "
    '{"entities": [{"type": "...", "text": "exact substring"}], "personal_health": true|false, '
    '"keep": ["..."]}\n\nMessage:\n')


def _chat(http: httpx.Client, model: str, content: str, temperature: float) -> dict:
    r = http.post(URL, headers={"Authorization": f"Bearer {env('OPENROUTER_API_KEY')}"}, json={
        "model": model, "temperature": temperature, "max_tokens": 4000,
        "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or "{}"
    start = text.find("{")
    if start < 0:
        return {}
    try:  # the first JSON object; some replies append a second one or prose
        return json.JSONDecoder().raw_decode(text[start:])[0]
    except ValueError:
        return {}


def generate(http: httpx.Client) -> None:
    out, seen = [], set()
    for model in GENERATORS:
        for group, variant, n, spec in SCENARIOS:
            items = _chat(http, model, COMMON + GEN_FORMAT.format(n=n, spec=spec), 0.9).get("items", [])
            for it in items:
                text = (it.get("text") or "").strip()
                if text and text not in seen:
                    seen.add(text)
                    out.append({"raw_id": f"BR{len(out) + 1:03d}", "generator": model,
                                "asked_for": f"{group}/{variant}", "text": text})
            print(f"{model} {group}/{variant}: {len(items)}", file=sys.stderr)
    _write(HERE / "bme_holdout_raw.jsonl", out)
    print(f"{len(out)} texts", file=sys.stderr)


def _clean(label: dict, text: str) -> tuple[frozenset, bool, list[str]]:
    ents = frozenset((e.get("type"), e.get("text")) for e in label.get("entities", [])
                     if e.get("type") in TYPES and e.get("text") and e["text"] in text)
    keep = [k for k in label.get("keep", []) if isinstance(k, str) and k and k in text]
    return ents, bool(label.get("personal_health")), keep


def label(http: httpx.Client) -> None:
    raw = [json.loads(line) for line in (HERE / "bme_holdout_raw.jsonl").read_text(encoding="utf-8").splitlines()]
    agreed, disputed = [], []
    cache_path = HERE / "bme_holdout_labels.jsonl"  # the labellers' raw answers, so a rerun asks no model twice
    cache = {}
    if cache_path.exists():
        for line in cache_path.read_text(encoding="utf-8").splitlines():
            entry = json.loads(line)
            cache[(entry["model"], entry["raw_id"])] = entry["label"]
    with cache_path.open("a", encoding="utf-8") as log:
        for row in raw:
            for m in LABELLERS:
                if (m, row["raw_id"]) not in cache:
                    cache[(m, row["raw_id"])] = _chat(http, m, LABEL_PROMPT + row["text"], 0.0)
                    log.write(json.dumps({"model": m, "raw_id": row["raw_id"],
                                          "label": cache[(m, row["raw_id"])]}, ensure_ascii=False) + "\n")
    for row in raw:
        labels = [_clean(cache[(m, row["raw_id"])], row["text"]) for m in LABELLERS]
        (ents_a, health_a, keep_a), (ents_b, health_b, keep_b) = labels
        keep = [k for k in keep_a if k in keep_b] or keep_a[:1]
        # a keep term inside a labelled entity would count the entity as over-redaction
        keep = [k for k in keep if not any(k in s or s in k for _, s in ents_a | ents_b)]
        record = {"id": row["raw_id"].replace("BR", "BH"), "group": "positive" if ents_a else "negative",
                  "text": row["text"], "entities": [{"type": t, "text": s} for t, s in sorted(ents_a)],
                  "keep": keep, "personal_health": health_a, "asked_for": row["asked_for"],
                  "generator": row["generator"]}
        if ents_a == ents_b and health_a == health_b:
            agreed.append(record)
        else:
            record["labels"] = {m: {"entities": sorted(e), "personal_health": h}
                                for m, (e, h, _) in zip(LABELLERS, labels, strict=True)}
            disputed.append(record)
    _write(HERE / "bme_holdout.jsonl", agreed)
    _write(HERE / "bme_holdout_disagreements.jsonl", disputed)
    print(f"{len(agreed)} agreed, {len(disputed)} to decide by hand", file=sys.stderr)


def _write(path: Path, rows: list[dict]) -> None:
    path.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("step", choices=["generate", "label"])
    a = ap.parse_args(argv)
    if not env("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2
    with httpx.Client(timeout=300) as http:
        (generate if a.step == "generate" else label)(http)
    return 0


if __name__ == "__main__":
    sys.exit(main())
