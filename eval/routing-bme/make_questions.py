# ruff: noqa: E501
"""X10: routing questions of the biomedical engineering course type -> data/routing/bme_questions.jsonl.

The labels follow the labelling rule of `data/routing/seed.jsonl` and `ece_cs_questions.jsonl`: the label is
set by the question's category (`label_origin` prototype_policy: intended policy, not measured local-model
ability):

    basic_concepts, simple_application, mechanism_explanation   local, no evidence      (0, 0, 0)
    course_evidence                                              needs the course files  (0, 1, 0)
    current_information                                          needs fresh evidence    (0, 1, 1)
    complex_reasoning                                            cloud                   (1, 0, 0)

Two generator families through OpenRouter write the questions in paraphrase pairs (a pair shares `group`);
a labeller of another size (anthropic/claude-sonnet-5.5) assigns each question a category on its own, and a
pair is kept only when the labeller agrees with the category asked for on both questions. Only the subject
is sent, never course material (rule 6).

    set OPENROUTER_API_KEY (environment or the repository's .env)
    .venv\\Scripts\\python eval\\routing-bme\\make_questions.py
"""
import json
import re
import sys
from collections import Counter
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from eval.common.env import env  # noqa: E402

URL = "https://openrouter.ai/api/v1/chat/completions"
GENERATORS = ["anthropic/claude-haiku-5.5", "openai/gpt-6-luna"]
LABELLER = "anthropic/claude-sonnet-5.5"
OUT = ROOT / "data" / "routing" / "bme_questions.jsonl"
LABELS = {"basic_concepts": (0, 0, 0), "simple_application": (0, 0, 0), "mechanism_explanation": (0, 0, 0),
          "course_evidence": (0, 1, 0), "current_information": (0, 1, 1), "complex_reasoning": (1, 0, 0)}
RATIONALE = {
    "basic_concepts": "Stable introductory concept; intended local/no-external-evidence policy.",
    "simple_application": "Bounded classroom application; context alone is not a reason to require Cloud.",
    "mechanism_explanation": "Explains a standard mechanism; intended local/no-external-evidence policy.",
    "course_evidence": "Depends on this course's own material (syllabus, notes, deliverables).",
    "current_information": "Depends on current external information (standards, approvals, versions).",
    "complex_reasoning": "Multi-step design, derivation or trade-off analysis; intended Cloud policy.",
}
DEFINITIONS = (
    "basic_concepts: what a term or component is (e.g. 'What is an instrumentation amplifier?'). "
    "simple_application: a short bounded calculation or use of one formula (e.g. 'What is the resolution of a 10-bit ADC with a 5 V range?'). "
    "mechanism_explanation: how or why a standard device, signal or method works (e.g. 'Why does a pulse oximeter use two wavelengths?'). "
    "course_evidence: needs this course's own documents: the syllabus, lecture notes, project phases, deliverables, deadlines, grading (e.g. 'What does lecture 4 say about electrode placement?', 'When is the phase 2 report due?'). "
    "current_information: needs up-to-date outside information: the newest standard, a recent regulatory approval, the current version of a tool (e.g. 'What is the latest IEC 60601 edition?'). "
    "complex_reasoning: multi-step design, derivation, debugging or trade-off analysis (e.g. 'Design a two-stage ECG front end with a gain of 1000 and a 0.5-150 Hz band, and justify each component')."
)
# groups (paraphrase pairs) per generator and category
PLAN = {"basic_concepts": 6, "simple_application": 9, "mechanism_explanation": 7, "course_evidence": 7,
        "current_information": 2, "complex_reasoning": 9}
SUBJECT = ("a university biomedical engineering course on medical diagnostic engineering: biosignals (ECG, "
           "EEG, EMG, blood pressure, SpO2), sensors and transducers, instrumentation and differential "
           "amplifiers, filters and noise, ADC and DAC, microcontrollers and Python for signal processing, "
           "medical imaging basics, diagnostic test accuracy (sensitivity, specificity, ROC), device safety "
           "and regulation, and a design project with phases and deliverables")


def _chat(http: httpx.Client, model: str, content: str, temperature: float) -> dict:
    r = http.post(URL, headers={"Authorization": f"Bearer {env('OPENROUTER_API_KEY')}"}, json={
        "model": model, "temperature": temperature, "max_tokens": 6000,
        "response_format": {"type": "json_object"}, "messages": [{"role": "user", "content": content}]})
    r.raise_for_status()
    text = r.json()["choices"][0]["message"]["content"] or "{}"
    m = re.search(r"\{.*\}", text, re.S)
    return json.loads(m.group(0)) if m else {}


def generate(http: httpx.Client, model: str, category: str, n: int) -> list[list[str]]:
    prompt = (f"Write student questions for the AI tutor of {SUBJECT}. Categories: {DEFINITIONS}\n\n"
              f"Write {n} different questions of the category {category}, each with one paraphrase a "
              "student might type instead (informal, sometimes with typos or abbreviations). No personal "
              "data. Reply with JSON only: {\"pairs\": [[\"question\", \"paraphrase\"]]}.")
    pairs = _chat(http, model, prompt, 0.9).get("pairs", [])
    return [p for p in pairs if isinstance(p, list) and len(p) == 2 and all(isinstance(q, str) and q.strip() for q in p)]


def categorize(http: httpx.Client, question: str) -> str | None:
    prompt = (f"A student asked the AI tutor of {SUBJECT}:\n{question}\n\nWhich one category fits? {DEFINITIONS}\n"
              "Reply with JSON only: {\"category\": \"...\"}.")
    return _chat(http, LABELLER, prompt, 0.0).get("category")


def main() -> int:
    if not env("OPENROUTER_API_KEY"):
        print("OPENROUTER_API_KEY is not set", file=sys.stderr)
        return 2
    rows, seen, dropped = [], set(), Counter()
    with httpx.Client(timeout=300) as http:
        for model in GENERATORS:
            for category, n in PLAN.items():
                for pair in generate(http, model, category, n):
                    pair = [q.strip() for q in pair]
                    if any(q.casefold() in seen for q in pair) or pair[0].casefold() == pair[1].casefold():
                        dropped["duplicate"] += 1
                        continue
                    judged = [categorize(http, q) for q in pair]
                    if any(LABELS.get(j) != LABELS[category] for j in judged):
                        dropped[f"{category} judged {judged}"] += 1
                        continue
                    group = f"bme-{len(rows) // 2 + 1:03d}"
                    cloud, evidence, fresh = LABELS[category]
                    for q in pair:
                        seen.add(q.casefold())
                        rows.append({"id": f"bme-{len(rows) + 1:03d}", "topic": "biomedical_engineering",
                                     "category": category, "question": q, "group": group,
                                     "source_family": group, "cloud_required": cloud,
                                     "requires_evidence": evidence, "requires_fresh_evidence": fresh,
                                     "label_origin": "prototype_policy", "label_rationale": RATIONALE[category],
                                     "answer_included": False, "generator": model})
                print(f"{model} {category}: {len(rows)} rows so far", file=sys.stderr)
    OUT.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in rows), encoding="utf-8")
    print(f"{len(rows)} rows; dropped: {dict(dropped)}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    sys.exit(main())
