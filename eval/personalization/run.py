"""E3: does personalization give better-fitting answers without losing accuracy? (design §11 E3)

    .venv\\Scripts\\python eval\\personalization\\run.py --smoke        # CI: fake models, 2 personas x 3 questions
    .venv\\Scripts\\python eval\\personalization\\run.py                # 4 personas x 20 questions x on/off = 160
    .venv\\Scripts\\python eval\\personalization\\run.py --questions 5  # a shorter real run

Personas are student accounts created through admin/students, with onboarding answers, preferences and
scripted check answers (eval/common/harness.py). Each persona asks every question twice: personalization on,
and off (`learner.personalize: false`, i.e. LearnerContext(personalized=False)). Answers come from the real
local model unless --smoke; questions stay on the local route.

A blind pairwise judge (any OpenAI-compatible API: JUDGE_BASE_URL, JUDGE_MODEL, JUDGE_API_KEY; default: the
Ollama server's OpenAI endpoint with gemma4:e4b) sees the persona description, the question and the two
answers in random A/B order. It only ever sees fictional personas, never real student data.

Outputs in results/: report.md, pairs.jsonl (all answers and verdicts), abbas_sample.csv (30 blind pairs for
Dr. Abbas, A/B as shown) and abbas_key.csv (which side was personalized; keep it away from the rater).
"""
import argparse
import asyncio
import csv
import json
import os
import random
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))

import harness  # noqa: E402

TARGETS = {"win": (0.65, 0.55), "misconception": (0.80, 0.70), "preference": (0.90, 0.90)}
SAMPLE_SIZE = 30
PREF_TEXT = {"example_first": "an everyday example first, then the idea", "concept_first": "the idea first",
             "concise": "short answers", "detailed": "detailed answers"}

JUDGE_INSTRUCTIONS = """You compare two tutor answers for one student in a health-education course.
Student: {description}
The student prefers {preferences}.
{misconception}
Question: {question}

Answer A:
{a}

Answer B:
{b}

Reply with JSON only:
{{"level_fit": "A" | "B" | "tie",          // which answer fits THIS student's level better
  "correct_A": "correct" | "minor_error" | "critical_error",
  "correct_B": "correct" | "minor_error" | "critical_error",
  "preference_A": true | false,            // does A follow the student's presentation preference?
  "preference_B": true | false,
  "misconception_A": true | false | null,  // does A correct the misunderstanding? null if none is given
  "misconception_B": true | false | null}}
A critical error is medically wrong or unsafe information."""


# ------------------------------------------------------------------------------------------- judges
class LLMJudge:
    def __init__(self, base_url: str, model: str, api_key: str) -> None:
        sys.path.insert(0, str(harness.ROOT / "backend"))
        from app.llm.openai_compat import OpenAICompatClient

        self.model = model
        # generous token limit: some judges (gemma4 on Ollama's OpenAI endpoint) reason before answering
        self.client = OpenAICompatClient(base_url, api_key, model, timeout_s=300, max_tokens=4000,
                                         temperature=0.0)

    async def _one(self, prompt: str) -> dict:
        res = await self.client.complete([{"role": "user", "content": prompt}], json_schema={})
        m = re.search(r"\{.*\}", res.text, re.S)
        return json.loads(re.sub(r"//[^\n]*", "", m.group(0))) if m else {}

    def judge_many(self, prompts: list[str]) -> list[dict | Exception]:
        """One event loop for all calls (the HTTP client is bound to it); a failed call is returned."""
        async def run_all() -> list[dict | Exception]:
            out: list[dict | Exception] = []
            for p in prompts:
                try:
                    out.append(await self._one(p))
                except Exception as e:  # noqa: BLE001
                    out.append(e)
            return out

        return asyncio.run(run_all())


class FakeJudge:
    """Smoke mode: prefers the answer whose fake level tag matches the persona; everything correct."""

    model = "fake-judge"

    def judge_many(self, prompts: list[str]) -> list[dict | Exception]:
        return [self.judge(p) for p in prompts]

    def judge(self, prompt: str) -> dict:
        a = re.search(r"Answer A:\n\[([^\]]*)\]", prompt)
        b = re.search(r"Answer B:\n\[([^\]]*)\]", prompt)
        tag_a, tag_b = (a.group(1) if a else ""), (b.group(1) if b else "")
        fit = "A" if "unpersonalized" in tag_b else ("B" if "unpersonalized" in tag_a else "tie")
        mc = "The student has this misunderstanding" in prompt
        return {"level_fit": fit, "correct_A": "correct", "correct_B": "correct",
                "preference_A": "unpersonalized" not in tag_a, "preference_B": "unpersonalized" not in tag_b,
                "misconception_A": ("Known misunderstandings" in tag_a) if mc else None,
                "misconception_B": ("Known misunderstandings" in tag_b) if mc else None}


# ------------------------------------------------------------------------------------------ helpers
def judge_prompt(p: harness.Persona, q: dict, a: str, b: str, content) -> str:
    mc = ""
    if p.misconception:
        m = content.misconception(p.misconception)
        if m and m.kc in q["kc_ids"]:
            mc = (f'The student has this misunderstanding: "{m.statement}" '
                  f"A good answer for this student corrects it.")
    prefs = f"{PREF_TEXT[p.preferences['sequencing']]} and {PREF_TEXT[p.preferences['detail']]}"
    return JUDGE_INSTRUCTIONS.format(description=p.description, preferences=prefs, misconception=mc,
                                     question=q["question"], a=a, b=b)


def side(verdict: dict, key: str, personalized_is_a: bool, mine: bool):
    """The verdict for the personalized (mine=True) or the unpersonalized answer."""
    letter = "A" if personalized_is_a == mine else "B"
    return verdict.get(f"{key}_{letter}")


def rate(values: list) -> float | None:
    vals = [v for v in values if v is not None]
    return sum(1 for v in vals if v) / len(vals) if vals else None


def verdict_label(value: float | None, ideal: float, marginal: float) -> str:
    if value is None:
        return "n/a"
    return "✅ ideal" if value >= ideal else ("🟡 marginal" if value >= marginal else "❌ below marginal")


def pct(v: float | None) -> str:
    return "n/a" if v is None else f"{v:.0%}"


# --------------------------------------------------------------------------------------------- main
def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--questions", type=int, help="first N questions only (default: all 20)")
    ap.add_argument("--personas", help="comma-separated persona keys (default: all)")
    ap.add_argument("--judge-base-url", default=os.environ.get("JUDGE_BASE_URL"))
    ap.add_argument("--judge-model", default=os.environ.get("JUDGE_MODEL", "gemma4:e4b"))
    ap.add_argument("--seed", type=int, default=3)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--report-only", action="store_true", help="rebuild the report from <out>/pairs.jsonl")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    personas = harness.PERSONAS[:2] if a.smoke else harness.PERSONAS
    if a.personas:
        personas = [p for p in harness.PERSONAS if p.key in a.personas.split(",")]
    if a.report_only:
        pairs = [json.loads(line) for line in (a.out / "pairs.jsonl").read_text("utf-8").splitlines() if line.strip()]
        keys = {p["persona"] for p in pairs}
        return report(a, pairs, [p for p in harness.PERSONAS if p.key in keys], a.judge_model)
    questions = harness.load_questions(3 if a.smoke else a.questions)
    rng = random.Random(a.seed)
    env = {"ROUTING__STUB_SCORE": "0.0", "POST_RESPONSE": "[]"}  # local route; no learning between on/off

    pairs = []
    with harness.Harness(env, fake=a.smoke) as h:
        services, content = h.services, h.services.content
        clients = {p.key: h.persona_client(p)[0] for p in personas}
        base = services.settings
        for p in personas:
            for q in questions:
                answers = {}
                for on in (True, False):
                    learner = base.learner.model_copy(update={"personalize": on})
                    services.settings = base.model_copy(update={"learner": learner})
                    r = clients[p.key].post("/api/v1/ask", json={"topic": harness.TOPIC, "question": q["question"]})
                    if r.status_code != 200:
                        print(f"ask failed ({r.status_code}) {p.key}/{q['id']}", file=sys.stderr)
                        return 2
                    body = r.json()
                    answers[on] = {"answer": body["answer"], "level": body.get("kc_level"),
                                   "model": body["model_used"], "warnings": body["warnings"]}
                services.settings = base
                pairs.append({"persona": p.key, "question_id": q["id"], "question": q["question"],
                              "kc_ids": q["kc_ids"], "personalized": answers[True], "plain": answers[False],
                              "personalized_is_a": rng.random() < 0.5})
        if a.smoke:
            judge = FakeJudge()
        else:
            base_url = a.judge_base_url or f"{services.settings.ollama_url.rstrip('/')}/v1"
            judge = LLMJudge(base_url, a.judge_model, os.environ.get("JUDGE_API_KEY", "ollama"))
        by_key = {p.key: p for p in personas}
        prompts = []
        for pr in pairs:
            first, second = ((pr["personalized"], pr["plain"]) if pr["personalized_is_a"]
                             else (pr["plain"], pr["personalized"]))
            prompts.append(judge_prompt(by_key[pr["persona"]], {"question": pr["question"], "kc_ids": pr["kc_ids"]},
                                        first["answer"], second["answer"], content))
        for pr, verdict in zip(pairs, judge.judge_many(prompts), strict=True):
            if isinstance(verdict, Exception):  # a failed judgement is reported, not fatal
                pr["verdict"], pr["judge_error"] = {}, type(verdict).__name__
            else:
                pr["verdict"] = verdict
    return report(a, pairs, personas, judge.model)


def report(a, pairs: list[dict], personas, judge_model: str) -> int:
    judged = [p for p in pairs if p.get("verdict")]
    wins = ties = 0
    for p in judged:
        fit = p["verdict"].get("level_fit")
        if fit == "tie" or fit not in ("A", "B"):
            ties += 1
        elif (fit == "A") == p["personalized_is_a"]:
            wins += 1
    win_rate = (wins + 0.5 * ties) / len(judged) if judged else None
    correct = {mine: rate([side(p["verdict"], "correct", p["personalized_is_a"], mine) == "correct"
                           for p in judged]) for mine in (True, False)}
    critical = {mine: sum(1 for p in judged
                          if side(p["verdict"], "correct", p["personalized_is_a"], mine) == "critical_error")
                for mine in (True, False)}
    mc = rate([side(p["verdict"], "misconception", p["personalized_is_a"], True) for p in judged])
    mc_plain = rate([side(p["verdict"], "misconception", p["personalized_is_a"], False) for p in judged])
    pref = rate([side(p["verdict"], "preference", p["personalized_is_a"], True) for p in judged])
    no_drop = (correct[True] or 0) >= (correct[False] or 0) and critical[True] <= critical[False]
    below = (win_rate is not None and win_rate < TARGETS["win"][1]) or (pref is not None and pref < TARGETS["preference"][1])

    with (a.out / "pairs.jsonl").open("w", encoding="utf-8") as f:
        for p in pairs:
            f.write(json.dumps(p, ensure_ascii=False) + "\n")
    sample = random.Random(a.seed + 1).sample(pairs, min(SAMPLE_SIZE, len(pairs)))
    desc = {p.key: p.description for p in harness.PERSONAS}
    with (a.out / "abbas_sample.csv").open("w", encoding="utf-8", newline="") as f, \
            (a.out / "abbas_key.csv").open("w", encoding="utf-8", newline="") as k:
        w, wk = csv.writer(f), csv.writer(k)
        w.writerow(["pair_id", "student", "question", "answer_A", "answer_B", "better_fit_A_B_tie",
                    "correct_A", "correct_B", "critical_error_A", "critical_error_B", "notes"])
        wk.writerow(["pair_id", "personalized_side"])
        for i, p in enumerate(sample, 1):
            first, second = ((p["personalized"], p["plain"]) if p["personalized_is_a"] else (p["plain"], p["personalized"]))
            w.writerow([f"P{i:02d}", desc[p["persona"]], p["question"], first["answer"], second["answer"],
                        "", "", "", "", "", ""])
            wk.writerow([f"P{i:02d}", "A" if p["personalized_is_a"] else "B"])

    lines = [
        "# E3: personalization on vs off (design §11 E3)\n",
        f"{'Smoke run (fake models): the numbers only show that the harness works. ' if a.smoke else ''}"
        f"{len(personas)} personas × {len({p['question_id'] for p in pairs})} questions × on/off = "
        f"{2 * len(pairs)} answers · judge `{judge_model}`, blind, random A/B order · "
        f"{len(judged)} of {len(pairs)} pairs judged.\n",
        "| Metric | Personalized | Not personalized | Target (ideal / marginal) | Verdict |", "|---|---|---|---|---|",
        f"| Win rate, \"level fits this student\" (ties = ½) | {pct(win_rate)} | — | ≥ 65% / 55% | "
        f"{verdict_label(win_rate, *TARGETS['win'])} |",
        f"| Correct answers | {pct(correct[True])} | {pct(correct[False])} | no drop | "
        f"{'✅' if no_drop else '❌'} |",
        f"| Critical errors | {critical[True]} | {critical[False]} | no rise | "
        f"{'✅' if critical[True] <= critical[False] else '❌'} |",
        f"| Known misconception addressed | {pct(mc)} | {pct(mc_plain)} | ≥ 80% / 70% | "
        f"{verdict_label(mc, *TARGETS['misconception'])} |",
        f"| Preference respected | {pct(pref)} | — | ≥ 90% | {verdict_label(pref, *TARGETS['preference'])} |",
        "",
        "**Decision (design §11 E3):** " + (
            "below marginal → keep only level adaptation and the misconception note; turn off the preference "
            "templates." if below else "keep personalization as designed (level, misconception note, preference "
            "templates)."),
        *([] if no_drop else [
            "",
            "**Correctness criterion not met** (\"no drop in correctness or rise in critical errors\"). Review "
            "these personalized answers before relying on the decision above:",
            "",
            *[f"- {p['persona']} {p['question_id']}: judged `{side(p['verdict'], 'correct', p['personalized_is_a'], True)}`"
              f" — {p['personalized']['answer'][:160].strip()}…"
              for p in judged if side(p["verdict"], "correct", p["personalized_is_a"], True) != "correct"]]),
        "",
        "## By persona\n",
        "| Persona | Pairs | Personalized wins | Ties |", "|---|---|---|---|",
    ]
    for per in personas:
        mine = [p for p in judged if p["persona"] == per.key]
        w_ = sum(1 for p in mine if p["verdict"].get("level_fit") in ("A", "B")
                 and (p["verdict"]["level_fit"] == "A") == p["personalized_is_a"])
        t_ = sum(1 for p in mine if p["verdict"].get("level_fit") not in ("A", "B"))
        lines.append(f"| {per.key} | {len(mine)} | {w_} | {t_} |")
    failed = [p for p in pairs if p.get("judge_error")]
    lines += ["", f"Judge failures: {len(failed)}.",
              f"Dr. Abbas sample: `abbas_sample.csv` ({len(sample)} pairs, blind); key in `abbas_key.csv`.", ""]
    (a.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 0 if judged else 1


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # reports contain ≥, ×, ∈ (Windows consoles)
    sys.exit(main())
