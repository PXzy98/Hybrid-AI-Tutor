"""E6 utility experiment: what does redaction cost in answer quality? (offline, fictional data)

    .venv\\Scripts\\python eval\\privacy-filter\\utility.py [--n-plain 30 --n-health 15]

For a sample of E6 positive questions, the local model answers several versions of the same question:
  original      the raw question (reference; what a student would get without any filtering)
  placeholder   B1, the app's behaviour: <PERSON_1>, <STUDENT_ID_1>, ...
  surrogate     B2: fake but realistic values (other names, a fake student number, ...)
  hypothetical  B3, health questions only: the local model rewrites the question in the third person
                ("a person with asthma ..."); a rewrite that still contains PII or a personal health
                statement is rejected and counted (it would stay local)
A judge model (gemma4:e4b by default, a different model from the answerer) scores each version against the
reference answer from 1 to 5 and flags redaction artefacts. Placeholders echoed in an answer are restored and
any left over is counted as a restore failure. Writes results/utility.md and results/utility.jsonl.
This is an offline experiment: B2 and B3 are not enabled in the app.
"""
import argparse
import json
import random
import re
import statistics
import sys
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parents[1] / "backend"))

from app.core.config import PrivacyConfig, get_settings  # noqa: E402
from app.privacy.analyzer import PIIAnalyzer, custom_recognizer_names  # noqa: E402
from app.privacy.anonymizer import PLACEHOLDER_RE, anonymize, restore  # noqa: E402
from app.prompts.render import system_prompt  # noqa: E402

FAKE = {"PERSON": ["Alex Morgan", "Jordan Lee", "Sam Rivera", "Casey Brooks"], "STUDENT_ID": ["300000001"],
        "EMAIL_ADDRESS": ["student@example.com"], "PHONE_NUMBER": ["613-555-0000"], "GRADE": ["I got a low mark"]}
REWRITE = ("Rewrite the student's message below as a general question about a hypothetical person, so that it says "
           "nothing about the student or anyone they know (no names, numbers, 'I', 'my', 'my mother'). Keep the "
           "medical condition and what the student actually wants to know. Reply with the rewritten question only.\n\n")
JUDGE = """You compare a tutor's answer with a reference answer.
Student's real question: {q}
Reference answer (the tutor saw the full question):
{ref}

Candidate answer (the tutor saw a modified version of the question):
{cand}

Score the candidate from 1 to 5 for how well it serves the student's real question compared with the reference
(5 = as good or better, 3 = noticeably less useful, 1 = useless or wrong). Set "artifacts" true if the candidate
shows signs of the modification (placeholders like <PERSON_1>, a different name, confusion about missing details).
Reply with JSON only: {{"score": 1-5, "artifacts": true|false}}"""


def chat(http, url, model, prompt, system=None, max_tokens=500):
    msgs = ([{"role": "system", "content": system}] if system else []) + [{"role": "user", "content": prompt}]
    r = http.post(f"{url}/api/chat", json={"model": model, "stream": False, "think": False, "messages": msgs,
                                          "options": {"temperature": 0.2, "num_predict": max_tokens, "seed": 6}})
    return r.json()["message"]["content"].strip()


def judge(http, base, model, q, ref, cand):
    r = http.post(f"{base}/v1/chat/completions", json={
        "model": model, "temperature": 0, "max_tokens": 4000, "response_format": {"type": "json_object"},
        "messages": [{"role": "user", "content": JUDGE.format(q=q, ref=ref, cand=cand)}]})
    text = r.json()["choices"][0]["message"]["content"] or ""
    m = re.search(r"\{.*\}", text, re.S)
    try:
        d = json.loads(m.group(0)) if m else {}
        return int(d.get("score", 0)), bool(d.get("artifacts", False))
    except (ValueError, TypeError):
        return 0, False


def surrogate(text, findings):
    out, mapping, used = text, {}, {}
    for f in sorted(findings, key=lambda f: f.start, reverse=True):
        pool = FAKE.get(f.type)
        if not pool:
            continue
        orig = text[f.start:f.end]
        fake = used.setdefault(orig, pool[len(used) % len(pool)])
        mapping[fake] = orig
        out = out[:f.start] + fake + out[f.end:]
    return out, mapping


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--n-plain", type=int, default=30)
    ap.add_argument("--n-health", type=int, default=15)
    ap.add_argument("--judge-model", default="gemma4:e4b")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args(argv)
    s = get_settings()
    url, model = s.ollama_url.rstrip("/"), s.llm.local.model
    http = httpx.Client(timeout=600)
    an = PIIAnalyzer(PrivacyConfig(spacy_model="en_core_web_lg", allow_list=["Abbas"], recognizers=custom_recognizer_names(),
                                   entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER", "STUDENT_ID", "GRADE", "HEALTH_DETAIL",
                                             "POSTAL_CODE", "HEALTH_CARD", "ID_NUMBER", "DATE_OF_BIRTH", "ADDRESS"]))
    cases = [json.loads(x) for x in (HERE / "cases.jsonl").read_text("utf-8").splitlines() if x.strip()]
    rng = random.Random(6)
    plain = [c for c in cases if c["group"] == "positive" and not c["personal_health"]]
    health = [c for c in cases if c["group"] == "positive" and c["personal_health"]]
    sample = rng.sample(plain, min(a.n_plain, len(plain))) + rng.sample(health, min(a.n_health, len(health)))
    system = system_prompt("intermediate", "example_first", "concise")
    rows = []
    for i, c in enumerate(sample, 1):
        q = c["text"]
        names = [c["self_name"]] if c.get("self_name") else []
        findings = an.analyze(q, names, [])
        sanitized, _, mapping = anonymize(q, findings)
        versions = {"placeholder": sanitized}
        sur, sur_map = surrogate(q, [f for f in findings if f.type != "HEALTH_DETAIL"])
        if c["personal_health"]:
            sur, _, _ = anonymize(sur, [f for f in an.analyze(sur) if f.type == "HEALTH_DETAIL"])
        versions["surrogate"] = sur
        rewrite_rejected = None
        if c["personal_health"]:
            rw = chat(http, url, model, REWRITE + q, max_tokens=120).splitlines()[0].strip('" ')
            left = an.analyze(rw, names, [])
            rewrite_rejected = bool(left)
            if not left:
                versions["hypothetical"] = rw
        ref = chat(http, url, model, q, system)
        row = {"id": c["id"], "health": c["personal_health"], "question": q, "versions": versions,
               "rewrite_rejected": rewrite_rejected, "scores": {}, "artifacts": {}, "restore_left": {}}
        for v, text in versions.items():
            ans = chat(http, url, model, text, system)
            if v == "placeholder":
                ans = restore(ans, mapping)
            elif v == "surrogate":
                for fake, orig in sur_map.items():
                    ans = ans.replace(fake, orig)
            row["restore_left"][v] = len(PLACEHOLDER_RE.findall(ans))
            row["scores"][v], row["artifacts"][v] = judge(http, url, a.judge_model, q, ref, ans)
        rows.append(row)
        print(f"{i}/{len(sample)} {c['id']} {row['scores']}", file=sys.stderr)

    a.out.mkdir(parents=True, exist_ok=True)
    with (a.out / "utility.jsonl").open("w", encoding="utf-8") as f:
        for r in rows:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    L = ["# E6 utility: answer quality after redaction (offline experiment)\n",
         f"{len(rows)} fictional questions ({sum(not r['health'] for r in rows)} with identifiers only, "
         f"{sum(r['health'] for r in rows)} with a personal health detail). Answers by `{model}`, judged by "
         f"`{a.judge_model}` against the answer to the original question (1–5, 5 = as good as the reference).\n",
         "| Version | Questions | Mean score | Score ≥ 4 | Artefacts flagged | Placeholders left after restore |",
         "|---|---|---|---|---|---|"]
    for group, sel in (("identifiers only", [r for r in rows if not r["health"]]), ("personal health", [r for r in rows if r["health"]])):
        for v in ("placeholder", "surrogate", "hypothetical"):
            xs = [r for r in sel if v in r["scores"] and r["scores"][v] > 0]
            if not xs:
                continue
            sc = [r["scores"][v] for r in xs]
            L.append(f"| {group} · {v} | {len(xs)} | {statistics.mean(sc):.2f} | {sum(x >= 4 for x in sc) / len(sc):.0%} | "
                     f"{sum(r['artifacts'][v] for r in xs)} | {sum(r['restore_left'][v] for r in xs)} |")
    rej = [r for r in rows if r["rewrite_rejected"] is not None]
    if rej:
        L.append(f"\nHypothetical rewrite (B3): {sum(r['rewrite_rejected'] for r in rej)} of {len(rej)} rewrites still "
                 "contained PII or a personal health statement and were rejected (those questions would stay local).")
    L.append("\nJudge failures (score 0) are excluded. B2 and B3 are offline experiments; the app uses placeholders (B1).")
    (a.out / "utility.md").write_text("\n".join(L) + "\n", encoding="utf-8")
    print("\n".join(L))
    return 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
