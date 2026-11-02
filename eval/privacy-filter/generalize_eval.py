"""E6: how the hypothetical rewrite (privacy.health_detail_policy: generalize) behaves with the real local model.

    .venv\\Scripts\\python eval\\privacy-filter\\generalize_eval.py

For every personal-health question of the main set and of held-out v2, the local model writes the rewrite exactly
as the app does (app/privacy/generalize.py, including its checks). Reported: how many rewrites pass and would go
to the cloud, and whether any labelled identifier (name, ID, contact, grade) of the original question is left in
a passing rewrite. Writes results/generalize.md and results/generalize.jsonl.
"""
import asyncio
import json
import re
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.core.config import get_settings  # noqa: E402
from app.core.services import build_services  # noqa: E402
from app.privacy.analyzer import PIIAnalyzer  # noqa: E402
from app.privacy.generalize import FIRST_PERSON_RE, GRADE_RE, MAX_CHARS, NUMBER_RE, PROMPT  # noqa: E402

SETS = [("main set", "cases.jsonl"), ("held-out v2", "holdout2.jsonl")]
IDENTIFIER_TYPES = {"PERSON", "STUDENT_ID", "EMAIL_ADDRESS", "PHONE_NUMBER", "GRADE", "USERNAME"}


def contains(text: str, value: str) -> bool:
    return re.search(rf"(?<!\w){re.escape(value)}(?!\w)", text, re.I) is not None


async def rewrite_and_check(llm, analyzer, question: str) -> tuple[str, str]:
    """(rewrite, outcome): outcome is 'sent' or the reason it stays local (same checks as the app)."""
    result = await llm.complete([{"role": "user", "content": PROMPT + question}], max_tokens=120)
    lines = [ln.strip().strip('"“”') for ln in result.text.strip().splitlines() if ln.strip()]
    rw = lines[0] if lines else ""
    if not rw or len(rw) > MAX_CHARS:
        return rw, "empty or too long"
    if FIRST_PERSON_RE.search(rw):
        return rw, "first person"
    if NUMBER_RE.search(rw):
        return rw, "specific number"
    if GRADE_RE.search(rw):
        return rw, "grade"
    known = [question[f.start:f.end] for f in analyzer.analyze(question) if f.type != "HEALTH_DETAIL"]
    if any(contains(rw, v) for v in known):
        return rw, "repeats an identifier"
    found = analyzer.analyze(rw)
    if found:
        return rw, "filter finding: " + ", ".join(sorted({f.type for f in found}))
    return rw, "sent"


async def main() -> int:
    s = build_services(get_settings())
    analyzer = PIIAnalyzer(s.settings.privacy)
    rows = []
    for title, name in SETS:
        cases = [json.loads(x) for x in (HERE / name).read_text("utf-8").splitlines() if x.strip()]
        cases = [c for c in cases if c.get("personal_health")]
        for c in cases:
            rw, outcome = await rewrite_and_check(s.local_llm, analyzer, c["text"])
            left = [e["text"] for e in c["entities"] if e["type"] in IDENTIFIER_TYPES and contains(rw, e["text"])]
            rows.append({"set": title, "id": c["id"], "question": c["text"], "rewrite": rw, "outcome": outcome,
                         "identifiers_left": left})
            print(f"{c['id']} {outcome:28} {rw[:90]}", file=sys.stderr)
    out = HERE / "results"
    with (out / "generalize.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    L = ["# E6: hypothetical rewrite with the real local model\n",
         f"Local model `{s.settings.llm.local.model}`; the same prompt and checks as `app/privacy/generalize.py`. "
         "A rewrite that fails any check keeps the question local (the student still gets a local answer).\n",
         "| Set | Personal-health questions | Rewrite sent to the cloud | Kept local | Identifiers left in a sent rewrite |",
         "|---|---|---|---|---|"]
    for title, _ in SETS:
        sel = [r for r in rows if r["set"] == title]
        sent = [r for r in sel if r["outcome"] == "sent"]
        leaks = sum(bool(r["identifiers_left"]) for r in sent)
        L.append(f"| {title} | {len(sel)} | {len(sent)} ({len(sent) / max(1, len(sel)):.0%}) | "
                 f"{len(sel) - len(sent)} | {leaks} |")
    reasons: dict[str, int] = {}
    for r in rows:
        if r["outcome"] != "sent":
            key = r["outcome"].split(":")[0]
            reasons[key] = reasons.get(key, 0) + 1
    L += ["", "Why rewrites were kept local: " + ", ".join(f"{k} {v}" for k, v in sorted(reasons.items())) + ".",
          "", "## Examples (first 12 of held-out v2)\n", "| Question | Rewrite | Outcome |", "|---|---|---|"]
    for r in [r for r in rows if r["set"] == "held-out v2"][:12]:
        L.append(f"| {r['question'][:90]} | {r['rewrite'][:110]} | {r['outcome']} |")
    (out / "generalize.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(asyncio.run(main()))
