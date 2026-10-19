"""E4: does any profile or identity data reach the cloud? (design §11 E4)

    .venv\\Scripts\\python eval\\privacy-audit\\run.py --smoke   # CI: fake local models, 2 personas, few questions
    .venv\\Scripts\\python eval\\privacy-audit\\run.py           # all personas x all questions, real local models

Every question is forced to the cloud route (ROUTING__STUB_SCORE=1.0), and the recording cloud client
(LLM__CLOUD__AUDIT_LOG, app/llm/audit.py) captures every CloudRequest and the exact messages. The provider is
replaced by a local echo (LLM__CLOUD__AUDIT_ECHO) unless --real-cloud is given, so the audit needs no cloud
account and sends nothing anywhere. Personas are real student accounts created through admin/students, with
onboarding, preferences and check answers (so they have a rich learner profile and an open misconception).

Questions: the E3 set, the E1 tagging cases, and questions with planted PII (pii_questions.jsonl).
Checks: allow-list fields, identity, profile and PII in every payload; identity and typed PII in the
database (outside `account`) and the logs. Exit code 1 on any leak, so the run can gate CI.
"""
import argparse
import json
import os
import sqlite3
import sys
from pathlib import Path

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent / "common"))
sys.path.insert(0, str(HERE))

import harness  # noqa: E402
from audit import Ask, Finding, Secrets, analyze, contains, storage_findings  # noqa: E402

E1_CASES = HERE.parent / "understand-tagging" / "cases.jsonl"
E6_CASES = HERE.parent / "privacy-filter" / "cases.jsonl"
E6_GROUPS = ("positive", "hard", "french", "multiturn")
TARGETS = "fields outside the allow-list: 0 · profile or identity leak: 0 · PII leak ≤ 1% ideal / 5% marginal"


def jsonl(path: Path) -> list[dict]:
    return [json.loads(line) for line in path.read_text(encoding="utf-8").splitlines() if line.strip()]


def e6_questions(smoke: bool) -> list[dict]:
    """E6 cases with PII, asked end to end. The student's own name is replaced by the persona's display name, as
    in the app (identity terms come from the account); multi-turn messages are asked one by one."""
    out = []
    for c in jsonl(E6_CASES):
        if c["group"] not in E6_GROUPS:
            continue
        text, planted = c["text"], [e["text"] for e in c["entities"]]
        if c.get("self_name"):
            text = text.replace(c["self_name"], "{display_name}")
            planted = [v.replace(c["self_name"], "{display_name}") for v in planted]
        out.append({"id": c["id"], "question": text, "planted": planted, "expect_local": c["personal_health"]})
    return out[:6] if smoke else out


def question_set(smoke: bool) -> list[dict]:
    e3 = [{"id": q["id"], "question": q["question"], "planted": []} for q in harness.load_questions()]
    e1 = [{"id": c["id"], "question": c["question"], "planted": []} for c in jsonl(E1_CASES)]
    pii = jsonl(HERE / "pii_questions.jsonl")
    if smoke:
        return e3[:2] + pii[:3] + pii[7:8]
    return e3 + e1 + pii


def fill(text: str, p: harness.Persona) -> str:
    return text.replace("{display_name}", p.display_name).replace("{username}", p.username)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true", help="fake local models, 2 personas, 6 questions")
    ap.add_argument("--real-cloud", action="store_true", help="send to the configured cloud provider")
    ap.add_argument("--e6", action="store_true", help="ask the E6 privacy-filter cases (1 persona) instead")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args(argv)
    if a.e6 and a.out == HERE / "results":
        a.out = HERE / "results" / "e6"
    if a.e6 and not a.smoke:
        os.environ.setdefault("EVAL_SPACY_MODEL", "en_core_web_lg")  # the app's model; the harness defaults to sm
    a.out.mkdir(parents=True, exist_ok=True)
    log_path = a.out / "cloud_requests.jsonl"
    log_path.unlink(missing_ok=True)
    # the stub router forces every question to the cloud route, so every payload is audited (semantic
    # routing would keep most questions local and leave the cloud path untested)
    env = {"ROUTING__IMPL": "stub", "ROUTING__STUB_SCORE": "1.0", "LLM__CLOUD__AUDIT_LOG": str(log_path),
           "LLM__CLOUD__AUDIT_ECHO": "false" if a.real_cloud else "true"}
    personas = harness.PERSONAS[:1] if a.e6 else harness.PERSONAS[:2] if a.smoke else harness.PERSONAS
    questions = e6_questions(a.smoke) if a.e6 else question_set(a.smoke)

    asks: list[Ask] = []
    with harness.Harness(env, fake=a.smoke) as h:
        accounts = {}
        for p in personas:
            client, account = h.persona_client(p)
            accounts[p.key] = (client, account)
        # typed values are checked against the rows each ask adds: course content and general answers to other
        # questions contain words like "asthma" too, so a whole-database match would be meaningless
        stored: list[str] = []
        rows_before = set(db_dump(h).splitlines())
        for p in personas:
            client, _ = accounts[p.key]
            for q in questions:
                text = fill(q["question"], p)
                before = sum(1 for _ in log_path.open(encoding="utf-8")) if log_path.exists() else 0
                r = client.post("/api/v1/ask", json={"topic": harness.TOPIC, "question": text})
                rows_after = db_dump(h).splitlines()
                stored.append("\n".join(line for line in rows_after if line not in rows_before))
                rows_before = set(rows_after)
                if r.status_code != 200:
                    print(f"ask failed ({r.status_code}) for {p.key}/{q['id']}: {r.text[:200]}", file=sys.stderr)
                    return 2
                after = sum(1 for _ in log_path.open(encoding="utf-8")) if log_path.exists() else 0
                body = r.json()
                asks.append(Ask(p.key, text, [fill(v, p) for v in q["planted"]], list(range(before, after)),
                                body["route_target"], body["warnings"], q.get("expect_local", False)))
        services = h.services
        rows = services.accounts.list_students()
        identities = sorted({v for p in personas for v in (p.username, p.display_name, p.display_name.split()[-1])}
                            | {"eval.prof"})
        secrets = Secrets(identities=identities, student_ids=[s.student_id for s in rows],
                          misconception_texts=[t for m in services.content.all_misconceptions()
                                               for t in (m.statement, m.correction)])
        records = jsonl(log_path) if log_path.exists() else []
        findings = analyze(records, asks, secrets, analyzer=_analyzer(services))
        findings += [Finding("health", f"cloud#{x.record_ids[0]}", f"personal health question reached the cloud: "
                             f"'{x.question[:60]}'") for x in asks if x.expect_local and x.record_ids]
        findings += storage_findings(db_dump(h), "\n".join(h.log_lines), secrets, [])  # identities, everywhere
        for ask, new_rows in zip(asks, stored, strict=True):
            findings += [Finding("pii", "db", f"raw typed value stored '{v}' (ask: '{ask.question[:50]}')")
                         for v in ask.planted if contains(new_rows, v)
                         and not any(contains(v, i) or contains(i, v) for i in secrets.identities)]
        log_text = "\n".join(h.log_lines)
        findings += [Finding("pii", "log", f"raw typed value logged '{v}'")
                     for v in sorted({v for ask in asks for v in ask.planted}) if contains(log_text, v)]

    return report(a, asks, records, findings)


def db_dump(h) -> str:
    db_path = h.services.settings.database_url.removeprefix("sqlite:///")
    with sqlite3.connect(db_path) as con:
        return "\n".join(line for line in con.iterdump() if 'INSERT INTO "account"' not in line)


def _analyzer(services):
    from app.privacy.analyzer import PIIAnalyzer

    return PIIAnalyzer(services.settings.privacy)


def report(a, asks: list[Ask], records: list[dict], findings: list[Finding]) -> int:
    by_kind = {k: [f for f in findings if f.kind == k] for k in ("field", "identity", "profile", "pii", "health")}
    cloud_pii = {f.where for f in by_kind["pii"] if f.where.startswith("cloud#")}
    pii_rate = len(cloud_pii) / len(records) if records else 0.0
    to_cloud = sum(1 for x in asks if x.record_ids)
    kept_local = [x for x in asks if not x.record_ids]
    blocked = [x for x in asks if any("privacy" in w.lower() for w in x.warnings)]
    lines = [
        "# E4: privacy audit of cloud requests (design §11 E4)\n",
        f"{'Smoke run (fake local models). ' if a.smoke else ''}"
        f"{len({x.persona for x in asks})} personas × {len(asks) // max(1, len({x.persona for x in asks}))} "
        f"questions = {len(asks)} asks, all forced to the cloud route; "
        f"provider: {'real cloud' if a.real_cloud else 'local echo (nothing left the machine)'}.\n",
        f"Targets: {TARGETS}.\n",
        "| Result | Value |", "|---|---|",
        f"| Cloud requests recorded | {len(records)} (from {to_cloud} asks) |",
        f"| Asks kept local (not cloud-safe, or blocked by the pre-send guard) | {len(kept_local)} "
        f"(guard warnings: {len(blocked)}) |",
        f"| Fields outside the allow-list | {len(by_kind['field'])} |",
        f"| Identity leaks | {len(by_kind['identity'])} |",
        f"| Profile leaks | {len(by_kind['profile'])} |",
        f"| PII leaks in cloud requests | {len(cloud_pii)} ({pii_rate:.1%} of requests) |",
        *([f"| Personal health questions that reached the cloud | {len(by_kind['health'])} of "
           f"{sum(x.expect_local for x in asks)} |"] if any(x.expect_local for x in asks) else []),
        f"| Typed PII or identity stored in the DB or logs | "
        f"{sum(1 for f in findings if f.where in ('db', 'log'))} |",
        "",
        "## Findings\n",
        *([f"- **{f.kind}** in {f.where}: {f.detail}" for f in findings] or ["- none"]),
        "",
        "## Asks kept local\n",
        *([f"- {x.persona}: {x.question}" for x in kept_local] or ["- none"]),
        "",
    ]
    leak = bool(findings)
    lines.append(f"**Verdict: {'LEAK — release blocked (design §11 E4)' if leak else 'no leak'}**\n")
    (a.out / "report.md").write_text("\n".join(lines), encoding="utf-8")
    print("\n".join(lines))
    return 1 if leak else 0


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")  # reports contain ≥, ×, ∈ (Windows consoles)
    sys.exit(main())
