"""E6: privacy-filter evaluation (full version: benchmark, upgrades, ablation, gaps).

    .venv\\Scripts\\python eval\\privacy-filter\\run.py                 # everything (needs Ollama, GLiNER, trf)
    .venv\\Scripts\\python eval\\privacy-filter\\run.py --fast          # rule/spaCy configurations only
    .venv\\Scripts\\python eval\\privacy-filter\\run.py --smoke         # CI: small spaCy model only

Configurations (same 404 cases, same metrics):
  presidio_default   Presidio out of the box (its own recognizers), en_core_web_lg
  ours_sm / ours_lg  our MVP filter (5 custom recognizers + clean-up + allow-list), small / large spaCy
  app_mvp            ours_lg + the student's own identity terms (the MVP app configuration)
  a2_trf             app_mvp with the transformer spaCy model (en_core_web_trf)
  a5_rules           app_mvp + new rules: postal code, health card, SIN/MRN, date of birth, address, French,
                     extra health patterns (all registered recognizers)
  a3_gliner_only     GLiNER PII model alone (urchade/gliner_multi_pii-v1)
  a3_rules_gliner    a5_rules ∪ GLiNER
  a4_rules_llm       a5_rules ∪ local LLM second pass (Qwen reads the sanitized text and lists what is left)
Ablation: a5_rules minus one component at a time.

An entity is protected when ≥ 80% of its characters are redacted (any overlap for health details), whatever type
was assigned. Outputs: results/report.md, results/metrics.json, results/predictions.jsonl, results/*.svg.
"""
import argparse
import json
import math
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import PrivacyConfig  # noqa: E402
from app.privacy import analyzer as an  # noqa: E402
from app.privacy.analyzer import Finding, PIIAnalyzer, resolve_overlaps  # noqa: E402
from app.privacy.anonymizer import anonymize, restore  # noqa: E402

CORE_TYPES = ["PERSON", "STUDENT_ID", "EMAIL_ADDRESS", "PHONE_NUMBER", "GRADE", "HEALTH_DETAIL"]
NEW_TYPES = ["POSTAL_CODE", "HEALTH_CARD", "ID_NUMBER", "DATE_OF_BIRTH", "ADDRESS"]
MVP_RECOGNIZERS = ["grade", "health_detail", "phone_na", "student_id", "zh_person"]
LOCAL_ONLY = {"HEALTH_DETAIL"}
TARGETS = {  # (direction, ideal, marginal, label)
    "leak_rate": ("max", 0.01, 0.05, "Question-level leak rate, positive set"),
    "recall_min": ("min", 0.95, 0.90, "Lowest per-type recall, positive set"),
    "over_redaction": ("max", 0.05, 0.10, "Over-redaction, negative set"),
    "health_sensitivity": ("min", 0.95, 0.90, "Personal-health questions kept local (sensitivity)"),
    "health_specificity": ("min", 0.95, 0.90, "Other questions left cloud-eligible (specificity)"),
    "restore_ok": ("min", 1.0, 1.0, "Placeholder round trip restores the original text"),
    "latency_p50_ms": ("max", 100, 300, "Median latency per question (ms)"),
}
SCRATCH: dict = {}


# ------------------------------------------------------------------ detectors
def cfg(model: str, recognizers=None, entities=None) -> PrivacyConfig:
    return PrivacyConfig(spacy_model=model, score_threshold=0.5, allow_list=["Abbas"], recognizers=recognizers,
                         entities=entities or CORE_TYPES)


class Rules:
    """Our filter (optionally without identity terms / clean-up / allow-list, for the ablation)."""

    def __init__(self, c: PrivacyConfig, identity=True, clean=True, allow=True):
        self.a = PIIAnalyzer(c) if allow else PIIAnalyzer(c.model_copy(update={"allow_list": []}))
        self.identity, self.clean = identity, clean

    def __call__(self, text, names):
        if self.clean:
            return self.a.analyze(text, names if self.identity else [], [])
        saved = an.clean_person
        an.clean_person = lambda _t, f: f  # noqa: E731
        try:
            return self.a.analyze(text, names if self.identity else [], [])
        finally:
            an.clean_person = saved


class PresidioDefault:
    def __init__(self, model):
        from presidio_analyzer import AnalyzerEngine
        from presidio_analyzer.nlp_engine import NlpEngineProvider
        nlp = NlpEngineProvider(nlp_configuration={"nlp_engine_name": "spacy",
                                                   "models": [{"lang_code": "en", "model_name": model}]}).create_engine()
        self.e = AnalyzerEngine(nlp_engine=nlp, supported_languages=["en"])

    def __call__(self, text, names):
        return [Finding(r.entity_type, r.start, r.end, r.score) for r in self.e.analyze(
            text=text, language="en", entities=["PERSON", "EMAIL_ADDRESS", "PHONE_NUMBER"], score_threshold=0.5)]


GLINER_LABELS = {"person": "PERSON", "email": "EMAIL_ADDRESS", "phone number": "PHONE_NUMBER",
                 "student id number": "STUDENT_ID", "identity card number": "ID_NUMBER",
                 "health insurance number": "HEALTH_CARD", "address": "ADDRESS", "postal code": "POSTAL_CODE",
                 "date of birth": "DATE_OF_BIRTH", "medical condition of the writer": "HEALTH_DETAIL",
                 "medication taken by the writer": "HEALTH_DETAIL", "exam grade": "GRADE"}


class Gliner:
    def __init__(self):
        from gliner import GLiNER
        self.m = GLiNER.from_pretrained("urchade/gliner_multi_pii-v1")

    def __call__(self, text, names):
        ents = self.m.predict_entities(text, list(GLINER_LABELS), threshold=0.5)
        return [Finding(GLINER_LABELS[e["label"]], e["start"], e["end"], float(e["score"])) for e in ents]


LLM_PROMPT = """The text below is a student's message to a health tutor after automatic redaction; placeholders such as
<PERSON_1> or <STUDENT_ID_1> are already removed information. List every remaining piece of PERSONAL information:
names of real people, ID/account/card numbers, contact details (email, phone, address, postal code), dates of birth,
the student's own grades, and personal health details of the student or people they know (their conditions,
symptoms, medicines, readings). Do NOT list general medical words in a general question, course names, or staff
named Abbas. Copy each item exactly as it appears. Reply with JSON {"items": [{"text": "...", "type": "name|id|contact|grade|health|other"}]}.

Text: """
LLM_TYPE = {"name": "PERSON", "id": "ID_NUMBER", "contact": "EMAIL_ADDRESS", "grade": "GRADE",
            "health": "HEALTH_DETAIL", "other": "OTHER"}


class LocalLLM:
    """Second pass by the local model on the sanitized text (what would be cloud-bound)."""

    def __init__(self):
        import httpx
        from app.core.config import get_settings
        self.s, self.http = get_settings(), httpx.Client(timeout=120)

    def __call__(self, text, names, first: list[Finding]):
        sanitized, _, _ = anonymize(text, first)
        schema = {"type": "object", "properties": {"items": {"type": "array", "items": {
            "type": "object", "properties": {"text": {"type": "string"}, "type": {"type": "string"}},
            "required": ["text", "type"]}}}, "required": ["items"]}
        r = self.http.post(f"{self.s.ollama_url}/api/chat", json={
            "model": self.s.llm.local.model, "stream": False, "think": False, "format": schema,
            "options": {"temperature": 0, "num_ctx": self.s.llm.local.num_ctx},
            "messages": [{"role": "user", "content": LLM_PROMPT + sanitized}]})
        try:
            items = json.loads(r.json()["message"]["content"]).get("items", [])
        except (ValueError, KeyError):
            items = []
        out = []
        for it in items:
            val = (it.get("text") or "").strip()
            if len(val) < 2 or "<" in val:
                continue
            i = text.find(val)
            if i >= 0:
                out.append(Finding(LLM_TYPE.get(it.get("type"), "OTHER"), i, i + len(val), 0.9))
        return out


def union(*parts: list[Finding]) -> list[Finding]:
    return resolve_overlaps([f for p in parts for f in p], prefer=tuple(LOCAL_ONLY))


# ------------------------------------------------------------------ scoring
def protected(e, text, findings):
    start = text.find(e["text"])
    end = start + len(e["text"])
    covered = sum(max(0, min(f.end, end) - max(f.start, start)) for f in findings)
    return covered >= 1 if e["type"] == "HEALTH_DETAIL" else covered >= 0.8 * (end - start)


def names_of(case):
    n = case.get("self_name")
    return list(dict.fromkeys([n] + [w for w in n.split() if len(w) >= 3])) if n else []


def run_config(name, detect, cases):
    detect("warm up: Lucas Bergeron asks about asthma.", [])
    rows, times = [], []
    for c in cases:
        t0 = time.perf_counter()
        findings = detect(c["text"], names_of(c))
        times.append((time.perf_counter() - t0) * 1000)
        sanitized, entities, mapping = anonymize(c["text"], findings)
        rows.append({
            "config": name, "id": c["id"], "group": c["group"], "variant": c["variant"], "text": c["text"],
            "entities": [{**e, "protected": protected(e, c["text"], findings)} for e in c["entities"]],
            "findings": [{"type": f.type, "text": c["text"][f.start:f.end]} for f in findings],
            "predicted_health": any(f.type in LOCAL_ONLY for f in findings), "personal_health": c["personal_health"],
            "keep_ok": all(k in sanitized for k in c["keep"]), "restore_ok": restore(sanitized, mapping) == c["text"],
        })
    return {"rows": rows, "times": times}


def wilson(k, n):
    if not n:
        return float("nan"), float("nan")
    p, z = k / n, 1.96
    d = 1 + z * z / n
    mid, half = (p + z * z / (2 * n)) / d, z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return max(0.0, mid - half), min(1.0, mid + half)


def metrics(res):
    rows = res["rows"]
    by = lambda g: [r for r in rows if r["group"] == g]  # noqa: E731
    pos, neg = by("positive"), by("negative")
    per_type = {}
    for t in CORE_TYPES:
        es = [e for r in pos for e in r["entities"] if e["type"] == t]
        per_type[t] = (sum(e["protected"] for e in es), len(es))
    leak = lambda rs: sum(not all(e["protected"] for e in r["entities"]) for r in rs) / len(rs) if rs else 0  # noqa: E731
    labelled = [r for r in rows if r["group"] != "out_of_scope"]
    ph = [r for r in labelled if r["personal_health"]]
    nh = [r for r in labelled if not r["personal_health"]]
    oos = {}
    for r in by("out_of_scope"):
        k, n = oos.get(r["variant"], (0, 0))
        oos[r["variant"]] = (k + all(e["protected"] for e in r["entities"]), n + 1)
    times = sorted(res["times"])
    return {
        "per_type": per_type, "recall_min": min(k / n for k, n in per_type.values() if n),
        "leak_rate": leak(pos), "leak_hard": leak(by("hard")), "leak_french": leak([r for r in by("french") if r["entities"]]),
        "leak_multiturn": leak([r for r in by("multiturn") if r["entities"]]),
        "over_redaction": sum(bool(r["findings"]) for r in neg) / len(neg),
        "keep_broken": sum(not r["keep_ok"] for r in neg),
        "health_sensitivity": sum(r["predicted_health"] for r in ph) / len(ph),
        "health_specificity": sum(not r["predicted_health"] for r in nh) / len(nh),
        "restore_ok": sum(r["restore_ok"] for r in rows) / len(rows),
        "oos": oos, "oos_caught": sum(k for k, _ in oos.values()), "oos_total": sum(n for _, n in oos.values()),
        "latency_p50_ms": statistics.median(times), "latency_p95_ms": times[int(0.95 * (len(times) - 1))],
    }


def verdict(key, v):
    kind, ideal, marginal, _ = TARGETS[key]
    ok = (lambda x, t: x <= t) if kind == "max" else (lambda x, t: x >= t)
    return "✅ ideal" if ok(v, ideal) else ("🟡 marginal" if ok(v, marginal) else "❌ not met")


def fmt(key, v):
    return f"{v:.0f} ms" if key.endswith("_ms") else f"{v:.1%}"


# ------------------------------------------------------------------ report pieces
def svg_bars(title, labels, series: dict[str, list[float]], colors):
    w, h, left, top, bottom = 900, 360, 60, 40, 80
    gw = (w - left - 20) / len(labels)
    bw = gw / (len(series) + 1)
    y = lambda v: top + (h - top - bottom) * (1 - v)  # noqa: E731
    p = [f'<line x1="{left}" y1="{y(0)}" x2="{w - 20}" y2="{y(0)}" stroke="#94a3b8"/>']
    for t in (0, 0.25, 0.5, 0.75, 1):
        p.append(f'<text x="{left - 6}" y="{y(t) + 4:.1f}" text-anchor="end" font-size="11">{t:.0%}</text>'
                 f'<line x1="{left}" y1="{y(t):.1f}" x2="{w - 20}" y2="{y(t):.1f}" stroke="#e2e8f0"/>')
    for gi, lab in enumerate(labels):
        gx = left + gi * gw
        for si, (name, vals) in enumerate(series.items()):
            v = vals[gi]
            p.append(f'<rect x="{gx + (si + 0.5) * bw:.1f}" y="{y(v):.1f}" width="{bw * 0.9:.1f}" '
                     f'height="{y(0) - y(v):.1f}" fill="{colors[si % len(colors)]}"/>')
        p.append(f'<text x="{gx + gw / 2:.1f}" y="{h - bottom + 16}" text-anchor="middle" font-size="11">{lab}</text>')
    for si, name in enumerate(series):
        p.append(f'<rect x="{left + (si % 4) * 210}" y="{h - 44 + (si // 4) * 18}" width="12" height="12" '
                 f'fill="{colors[si % len(colors)]}"/><text x="{left + (si % 4) * 210 + 16}" y="{h - 34 + (si // 4) * 18}" '
                 f'font-size="12">{name}</text>')
    return (f'<svg xmlns="http://www.w3.org/2000/svg" width="{w}" height="{h}" font-family="sans-serif">'
            f'<rect width="100%" height="100%" fill="white"/><text x="12" y="22" font-size="15" font-weight="bold">'
            f'{title}</text>{"".join(p)}</svg>')


def main(argv=None) -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--fast", action="store_true", help="skip GLiNER, transformer and LLM configurations")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--cases", type=Path, default=HERE / "cases.jsonl", help="e.g. holdout.jsonl")
    a = ap.parse_args(argv)
    a.out.mkdir(parents=True, exist_ok=True)
    cases = [json.loads(x) for x in a.cases.read_text("utf-8").splitlines() if x.strip()]
    ALL = sorted(an.custom_recognizer_names())
    a5 = lambda: Rules(cfg("en_core_web_lg", ALL, CORE_TYPES + NEW_TYPES))  # noqa: E731

    if a.smoke:
        configs = {"ours_sm": Rules(cfg("en_core_web_sm", MVP_RECOGNIZERS), identity=False)}
    else:
        configs = {
            "presidio_default": PresidioDefault("en_core_web_lg"),
            "ours_sm": Rules(cfg("en_core_web_sm", MVP_RECOGNIZERS), identity=False),
            "ours_lg": Rules(cfg("en_core_web_lg", MVP_RECOGNIZERS), identity=False),
            "app_mvp": Rules(cfg("en_core_web_lg", MVP_RECOGNIZERS)),
            "a5_rules": a5(),
        }
        if not a.fast:
            configs["a2_trf"] = Rules(cfg("en_core_web_trf", MVP_RECOGNIZERS))
            gl = Gliner()
            configs["a3_gliner_only"] = gl
            rules = a5()
            configs["a3_rules_gliner"] = lambda t, n: union(rules(t, n), gl(t, n))
            llm = LocalLLM()
            configs["a4_rules_llm"] = lambda t, n: (lambda first: union(first, llm(t, n, first)))(rules(t, n))
    results = {}
    for name, det in configs.items():
        t0 = time.perf_counter()
        results[name] = run_config(name, det, cases)
        print(f"{name}: {time.perf_counter() - t0:.0f} s", file=sys.stderr)
    m = {k: metrics(v) for k, v in results.items()}

    ablation = {}
    if not a.smoke:
        base = m["a5_rules"]
        variants = {f"− {r}": Rules(cfg("en_core_web_lg", [x for x in ALL if x != r], CORE_TYPES + NEW_TYPES)) for r in ALL}
        variants["− identity terms"] = Rules(cfg("en_core_web_lg", ALL, CORE_TYPES + NEW_TYPES), identity=False)
        variants["− person clean-up"] = Rules(cfg("en_core_web_lg", ALL, CORE_TYPES + NEW_TYPES), clean=False)
        variants["− staff allow-list"] = Rules(cfg("en_core_web_lg", ALL, CORE_TYPES + NEW_TYPES), allow=False)
        for vn, det in variants.items():
            x = metrics(run_config(vn, det, cases))
            ablation[vn] = {k: x[k] - base[k] for k in ("leak_rate", "leak_hard", "leak_french", "over_redaction",
                                                        "health_sensitivity", "health_specificity")}
            ablation[vn]["oos_caught"] = x["oos_caught"] - base["oos_caught"]

    with (a.out / "predictions.jsonl").open("w", encoding="utf-8") as f:
        for r in results.values():
            for row in r["rows"]:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
    (a.out / "metrics.json").write_text(json.dumps({"configs": m, "ablation": ablation}, indent=1, default=list),
                                        encoding="utf-8")
    colors = ["#94a3b8", "#fbbf24", "#f59e0b", "#0f766e", "#14b8a6", "#1d4ed8", "#a855f7", "#db2777", "#65a30d"]
    (a.out / "recall_by_type.svg").write_text(svg_bars(
        "E6: recall per PII type (positive set)", [t.replace("_", " ").lower() for t in CORE_TYPES],
        {n: [x["per_type"][t][0] / x["per_type"][t][1] for t in CORE_TYPES] for n, x in m.items()}, colors), encoding="utf-8")
    (a.out / "leak_by_group.svg").write_text(svg_bars(
        "E6: question-level leak rate by group (lower is better)", ["positive", "hard", "french", "multi-turn"],
        {n: [x["leak_rate"], x["leak_hard"], x["leak_french"], x["leak_multiturn"]] for n, x in m.items()}, colors),
        encoding="utf-8")
    print(report(cases, results, m, ablation, a.out, a.cases.name))
    return 0


def report(cases, results, m, ablation, out: Path, source: str = "cases.jsonl") -> str:
    groups = {}
    for c in cases:
        groups[c["group"]] = groups.get(c["group"], 0) + 1
    chosen = "a5_rules" if "a5_rules" in m else next(iter(m))
    L = ["# E6: privacy filter evaluation\n",
         f"{len(cases)} fictional questions ({', '.join(f'{v} {k}' for k, v in groups.items())}); "
         + ("generated by `make_cases.py` from templates and a question bank written by the local model. "
            if source == "cases.jsonl" else
            f"`{source}`: held-out set written by a different model after the rules were final "
            "(`make_holdout.py`), labels checked by hand. ")
         + "An entity counts as protected when ≥ 80% of its characters are redacted (any overlap for health details).\n",
         f"## Expected vs actual — recommended configuration `{chosen}`\n",
         "| Metric | Expected (ideal / marginal) | Actual | Verdict |", "|---|---|---|---|"]
    for k, (kind, ideal, marg, label) in TARGETS.items():
        sign = "≤" if kind == "max" else "≥"
        L.append(f"| {label} | {sign} {fmt(k, ideal)} / {sign} {fmt(k, marg)} | {fmt(k, m[chosen][k])} | {verdict(k, m[chosen][k])} |")
    L += ["", "## All configurations\n",
          "| Configuration | Leak: positive | hard | French | multi-turn | Lowest type recall | Over-redaction | "
          "Health sens. / spec. | Out-of-scope caught | p50 / p95 |", "|---|---|---|---|---|---|---|---|---|---|"]
    for n, x in m.items():
        L.append(f"| {n} | {x['leak_rate']:.1%} | {x['leak_hard']:.1%} | {x['leak_french']:.1%} | {x['leak_multiturn']:.1%} | "
                 f"{x['recall_min']:.1%} | {x['over_redaction']:.1%} | {x['health_sensitivity']:.1%} / "
                 f"{x['health_specificity']:.1%} | {x['oos_caught']}/{x['oos_total']} | "
                 f"{x['latency_p50_ms']:.0f} / {x['latency_p95_ms']:.0f} ms |")
    L += ["", "![Recall per type](recall_by_type.svg)", "", "![Leak by group](leak_by_group.svg)", "",
          "## Recall per type, positive set (95% Wilson interval)\n", "| Type | " + " | ".join(m) + " |",
          "|---|" + "---|" * len(m)]
    for t in CORE_TYPES:
        cells = []
        for x in m.values():
            k, n = x["per_type"][t]
            lo, hi = wilson(k, n)
            cells.append(f"{k}/{n} [{lo:.0%}–{hi:.0%}]")
        L.append(f"| {t} | " + " | ".join(cells) + " |")
    if ablation:
        L += ["", "## Ablation (a5_rules minus one component; change in percentage points, + = worse for leak/over-redaction)\n",
              "| Removed | Leak positive | Leak hard | Leak French | Over-redaction | Health sens. | Health spec. | Out-of-scope caught |",
              "|---|---|---|---|---|---|---|---|"]
        for vn, d in ablation.items():
            L.append(f"| {vn} | {d['leak_rate'] * 100:+.1f} | {d['leak_hard'] * 100:+.1f} | {d['leak_french'] * 100:+.1f} | "
                     f"{d['over_redaction'] * 100:+.1f} | {d['health_sensitivity'] * 100:+.1f} | "
                     f"{d['health_specificity'] * 100:+.1f} | {d['oos_caught']:+d} |")
    rows = results[chosen]["rows"]
    L += ["", f"## Misses of `{chosen}` by group and variant\n"]
    for g in ("positive", "hard", "french", "multiturn"):
        missed = [r for r in rows if r["group"] == g and not all(e["protected"] for e in r["entities"])]
        L.append(f"**{g}** — {len(missed)} questions with a leak:")
        L += [f"- {r['id']} [{r['variant']}]: " + "; ".join(e["type"] + ": " + e["text"] for e in r["entities"] if not e["protected"])
              + f" — “{r['text']}”" for r in missed] or ["- none"]
        L.append("")
    over = [r for r in rows if r["group"] == "negative" and r["findings"]]
    L.append(f"**negative** — {len(over)} over-redacted:")
    L += [f"- {r['id']}: " + ", ".join(f["type"] + ": " + f["text"] for f in r["findings"]) + f" — “{r['text']}”" for r in over] or ["- none"]
    wrong_h = [r for r in rows if r["group"] != "out_of_scope" and r["predicted_health"] != r["personal_health"]]
    L += ["", f"**local-only decision** — {len(wrong_h)} wrong:"]
    L += [f"- {r['id']} [{r['group']}/{r['variant']}] expected {'local' if r['personal_health'] else 'cloud-eligible'} — “{r['text']}”"
          for r in wrong_h] or ["- none"]
    L += ["", "## Known gaps (out-of-scope set)\n", "| Type | " + " | ".join(m) + " |", "|---|" + "---|" * len(m)]
    for t in sorted(next(iter(m.values()))["oos"]):
        L.append(f"| {t} | " + " | ".join(f"{x['oos'][t][0]}/{x['oos'][t][1]}" for x in m.values()) + " |")
    text = "\n".join(L) + "\n"
    (out / "report.md").write_text(text, encoding="utf-8")
    return text


if __name__ == "__main__":
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.exit(main())
