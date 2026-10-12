"""Grade raw answers.

  python grade.py                                   # auto-grade mcq / numeric / short / rule
  python grade.py --judge-model gpt-4o              # + LLM judge for the 6 open questions
  python grade.py --judge-model qwen3.5:27b --base-url http://192.168.2.25:11434/v1 --api-key ollama

Without a judge, open questions are written to results/manual_review.csv.
Fill the 'correct' column with 1 or 0, save, and run grade.py again.
Output: results/graded.jsonl and results/graded.csv
"""
import argparse, csv, json, os, re, unicodedata
from pathlib import Path

import requests

# ------------------------------------------------------------------ helpers
THINK_RE = re.compile(r"<think>.*?</think>", re.S | re.I)
FINAL_RE = re.compile(r"(?:final\s+answer|answer|答案)\s*[:：]\s*(.+)", re.I)
NUM_RE = re.compile(r"-?\d[\d,]*\.?\d*(?:e-?\d+)?|-?\.\d+")


def clean(text):
    return THINK_RE.sub("", text or "").strip()


def strip_md(s):
    return re.sub(r"[*_`#]", "", s).strip()


def final_line(text):
    m = None
    for m in FINAL_RE.finditer(text):
        pass
    return strip_md(m.group(1)) if m else None


def parse_number(s):
    if s is None:
        return None
    s = s.replace("−", "-").replace("$", "")
    m = NUM_RE.search(s)
    if not m:
        return None
    try:
        v = float(m.group(0).replace(",", ""))
    except ValueError:
        return None
    # handle '26.9%' when a fraction is expected (checked by caller)
    return v, ("%" in s[m.end(): m.end() + 2])


# ------------------------------------------------------------------ graders
def grade_mcq(t, text):
    f = final_line(text)
    letter = None
    if f:
        m = re.search(r"\b([A-D])\b", f.upper()) or re.search(r"([A-D])", f.upper())
        letter = m.group(1) if m else None
    fmt = letter is not None
    if not letter:  # fallback patterns
        m = (re.findall(r"answer\s+is\s*:?\s*\(?([A-D])\b", text, re.I)
             or re.findall(r"^\s*\(?([A-D])[\).:]?\s*$", text, re.M)
             or re.findall(r"\*\*\(?([A-D])[\).:]", text))
        letter = m[-1].upper() if m else None
    return letter == t["answer"], fmt, f"got {letter}"


def grade_numeric(t, text):
    f = final_line(text)
    fmt = f is not None and parse_number(f) is not None
    src = f if fmt else None
    if not fmt:  # fallback: last number in the answer
        nums = NUM_RE.findall(text.replace("−", "-"))
        src = nums[-1] if nums else None
    p = parse_number(src)
    if p is None:
        return False, fmt, "no number"
    v, pct = p
    exp, tol = t["answer"], t["tol"]
    ok = abs(v - exp) <= tol
    if not ok and abs(exp) < 1 and (pct or v > 1):  # 26.87 / 26.87% for 0.2687
        ok = abs(v / 100 - exp) <= tol
    return ok, fmt, f"got {v}{'%' if pct else ''}"


def grade_short(t, text):
    f = final_line(text)
    hay = (f or text).lower().replace("-", "").replace(" ", "")
    ok = any(all(s.replace("-", "").replace(" ", "") in hay for s in alt) for alt in t["accept"])
    return ok, f is not None, f"got {f!r}" if f else "no ANSWER line"


VERBS = set("""remove use apply encrypt limit restrict anonymize anonymise deidentify de-identify pseudonymize
pseudonymise store ensure obtain replace mask aggregate implement conduct perform train monitor audit
delete minimize minimise generalize generalise suppress review control collect share add avoid keep follow
require enforce secure protect separate document check get hash redact employ establish adopt set strip
drop exclude grant log manage obscure perturb tokenize tokenise classify assess define educate restrict
truncate round shift swap""".split())


def words(s):
    return re.findall(r"[A-Za-z0-9][A-Za-z0-9'’\-]*", s)


def sentences(s):
    s = re.sub(r"\b(e\.g|i\.e|etc|vs|Dr|Prof)\.", r"\1", s)
    return [x for x in re.split(r"(?<=[.!?。！？])\s*", s.strip()) if x.strip()]


def is_cjk(c):
    return "一" <= c <= "鿿"


def bullet_lines(s):
    return [l for l in s.splitlines() if re.match(r"^\s*[-*•]\s+\S", l)]


def numbered_lines(s):
    return [l for l in s.splitlines() if re.match(r"^\s*(\d+[.)、．]|[一二三四五六七八九十][、.．])\s*\S", l)]


def grade_rule(t, text):
    r, fails = t["rules"], []
    body = text.strip()
    low = body.lower()
    if "exact_any" in r:
        norm = re.sub(r"[^\w]", "", low)
        if norm not in r["exact_any"]:
            fails.append(f"not exactly {r['exact_any']}")
    if "exact_number" in r:
        p = parse_number(body)
        if not p or abs(p[0] - r["exact_number"]) > 1e-6 or len(words(body)) > 1:
            fails.append("not just the number")
    if "max_words" in r and len(words(body)) > r["max_words"]:
        fails.append(f"{len(words(body))} words > {r['max_words']}")
    if "max_sentences" in r and len(sentences(body)) > r["max_sentences"]:
        fails.append(f"{len(sentences(body))} sentences")
    if "sentence_count" in r and len(sentences(body)) != r["sentence_count"]:
        fails.append(f"{len(sentences(body))} sentences != {r['sentence_count']}")
    if "min_commas" in r and body.count(",") + body.count("，") < r["min_commas"]:
        fails.append("too few commas")
    if "max_lines" in r and len([l for l in body.splitlines() if l.strip()]) > r["max_lines"]:
        fails.append("too many lines")
    if "bullet_count" in r:
        b = bullet_lines(body)
        if len(b) != r["bullet_count"]:
            fails.append(f"{len(b)} bullets != {r['bullet_count']}")
        if r.get("bullets_start_with_verb"):
            for l in b:
                w = re.sub(r"^\s*[-*•]\s+", "", l)
                w = strip_md(w).split()[0].lower().strip(":,.") if strip_md(w).split() else ""
                if w not in VERBS and not re.search(r"(ize|ise|ify)$", w):
                    fails.append(f"bullet starts with '{w}'")
                    break
    if "numbered_count" in r and len(numbered_lines(body)) != r["numbered_count"]:
        fails.append(f"{len(numbered_lines(body))} numbered != {r['numbered_count']}")
    if "must_include" in r:
        for s in r["must_include"]:
            if s.lower() not in low:
                fails.append(f"missing '{s}'")
    if "must_include_any" in r and not any(s.lower() in low for s in r["must_include_any"]):
        fails.append("missing required content")
    if "must_not_include" in r:
        for s in r["must_not_include"]:
            if s and s.lower() in low:
                fails.append(f"contains '{s}'")
    if "must_not_include_words" in r:
        for s in r["must_not_include_words"]:
            if re.search(rf"\b{re.escape(s)}\b", low):
                fails.append(f"uses word '{s}'")
                break
    if r.get("no_digits") and re.search(r"\d", body):
        fails.append("contains digits")
    if r.get("lang") == "zh":
        allowed = set(r.get("allowed_english", []))
        rest = " ".join(w for w in re.findall(r"[A-Za-z]+", body) if len(w) > 2 and w.lower() not in allowed)
        cjk = sum(is_cjk(c) for c in body)
        lat = len(re.sub(r"\s", "", rest))
        if cjk == 0 or cjk / (cjk + lat) < 0.6:
            fails.append("not mainly Chinese")
    if "max_chars" in r:
        n = sum(1 for c in body if not c.isspace() and not unicodedata.category(c).startswith("P"))
        if n > r["max_chars"]:
            fails.append(f"{n} chars > {r['max_chars']}")
    if "allowed_english" in r:
        bad = [w for w in re.findall(r"[A-Za-z]{3,}", body) if w.lower() not in r["allowed_english"]]
        if bad:
            fails.append(f"English words: {bad[:3]}")
    if "last_line_startswith" in r:
        lines = [strip_md(l) for l in body.splitlines() if l.strip()]
        if not lines or not lines[-1].startswith(r["last_line_startswith"]):
            fails.append("last line format")
    if r.get("json_only"):
        try:
            obj = json.loads(body)
            if "json_keys" in r and not all(k in obj for k in r["json_keys"]):
                fails.append("missing json keys")
            for k, v in r.get("json_equals", {}).items():
                if str(obj.get(k, "")).upper() != v:
                    fails.append(f"{k}={obj.get(k)}")
            if "json_number" in r:
                jn = r["json_number"]
                try:
                    if abs(float(obj.get(jn["key"])) - jn["value"]) > jn["tol"]:
                        fails.append("wrong number")
                except (TypeError, ValueError):
                    fails.append("answer not a number")
        except (json.JSONDecodeError, AttributeError):
            fails.append("invalid JSON (or extra text / code fences)")
    return not fails, True, "; ".join(fails) or "ok"


# --------------------------------------------------------------- open: judge
JUDGE = """Grade a tutor's answer.

Question:
{q}

Reference (what a correct answer must do):
{ref}

Tutor answer:
{ans}

Score correctness from 1 (wrong / hallucinated) to 5 (fully correct and complete).
If the reference says the premise is false and the tutor treats it as real, score 1.
Return ONLY JSON: {{"score": int, "reason": "one sentence"}}"""


def judge(a, t, ans):
    body = {"model": a.judge_model, "temperature": 0,
            "messages": [{"role": "user", "content": JUDGE.format(q=t["question"], ref=t["reference"], ans=ans)}]}
    r = requests.post(f"{a.base_url.rstrip('/')}/chat/completions",
                      headers={"Authorization": f"Bearer {a.api_key}"}, json=body, timeout=300)
    r.raise_for_status()
    txt = clean(r.json()["choices"][0]["message"]["content"])
    d = json.loads(re.search(r"\{.*\}", txt, re.S).group(0))
    return int(d["score"]), d.get("reason", "")


# --------------------------------------------------------------------- main
def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--answers", default="results/answers.jsonl")
    ap.add_argument("--testset", default="data/boundary_set.jsonl")
    ap.add_argument("--outdir", default="results")
    ap.add_argument("--judge-model")
    ap.add_argument("--base-url", default=os.environ.get("OPENAI_BASE_URL", "https://api.openai.com/v1"))
    ap.add_argument("--api-key", default=os.environ.get("OPENAI_API_KEY", "ollama"))
    a = ap.parse_args()
    out = Path(a.outdir); out.mkdir(parents=True, exist_ok=True)

    tests = {t["id"]: t for t in (json.loads(l) for l in open(a.testset, encoding="utf-8") if l.strip())}
    answers = [json.loads(l) for l in open(a.answers, encoding="utf-8") if l.strip()]
    answers = [x for x in answers if not x.get("error")]

    # manual grades and cached judge grades
    manual_path, cache_path = out / "manual_review.csv", out / "judge_cache.jsonl"
    manual = {}
    if manual_path.exists():
        for row in csv.DictReader(open(manual_path, encoding="utf-8-sig")):
            if row.get("correct", "").strip() in ("0", "1"):
                manual[row["key"]] = row["correct"].strip() == "1"
    cache = {}
    if cache_path.exists():
        for l in open(cache_path, encoding="utf-8"):
            d = json.loads(l); cache[d["key"]] = d

    graded, pending = [], []
    for x in answers:
        t = tests[x["id"]]
        text = clean(x.get("answer"))
        k = f"{x['model']}|{x.get('think')}|{x.get('repeat', 0)}|{x['id']}"
        rec = {k2: x.get(k2) for k2 in ("model", "think", "repeat", "id", "dimension", "level",
                                         "total_s", "tok_per_s", "out_tokens", "hit_max_tokens")}
        rec.update(answer_type=t["answer_type"], pair_of=t.get("pair_of"))
        at = t["answer_type"]
        if at == "open":
            if k in manual:
                rec.update(correct=manual[k], format_ok=True, detail="manual")
            elif k in cache:
                rec.update(correct=cache[k]["score"] >= 4, format_ok=True,
                           detail=f"judge {cache[k]['score']}: {cache[k]['reason']}")
            elif a.judge_model:
                try:
                    s, why = judge(a, t, text)
                    with open(cache_path, "a", encoding="utf-8") as f:
                        f.write(json.dumps({"key": k, "score": s, "reason": why}, ensure_ascii=False) + "\n")
                    rec.update(correct=s >= 4, format_ok=True, detail=f"judge {s}: {why}")
                except Exception as e:  # noqa: BLE001
                    rec.update(correct=None, format_ok=None, detail=f"judge error {e}")
            else:
                rec.update(correct=None, format_ok=None, detail="needs grading")
                pending.append({"key": k, "model": x["model"], "id": x["id"], "question": t["question"],
                                "reference": t["reference"], "answer": text, "correct": ""})
        else:
            fn = {"mcq": grade_mcq, "numeric": grade_numeric, "short": grade_short, "rule": grade_rule}[at]
            ok, fmt, det = fn(t, text)
            rec.update(correct=ok, format_ok=fmt, detail=det)
        rec["answer_snippet"] = text[-300:]
        graded.append(rec)

    with open(out / "graded.jsonl", "w", encoding="utf-8") as f:
        for r in graded:
            f.write(json.dumps(r, ensure_ascii=False) + "\n")
    with open(out / "graded.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, fieldnames=list(graded[0].keys()))
        w.writeheader(); w.writerows(graded)
    if pending:
        old = []
        if manual_path.exists():
            old = list(csv.DictReader(open(manual_path, encoding="utf-8-sig")))
        have = {r["key"] for r in old}
        rows = old + [p for p in pending if p["key"] not in have]
        with open(manual_path, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.DictWriter(f, fieldnames=["key", "model", "id", "question", "reference", "answer", "correct", "why"])
            w.writeheader(); w.writerows(rows)
        print(f"{len(pending)} open answers need grading -> fill 'correct' (1/0) in {manual_path}, "
              f"or rerun with --judge-model")

    n = sum(r["correct"] is not None for r in graded)
    c = sum(bool(r["correct"]) for r in graded)
    print(f"graded {n}/{len(graded)} answers, {c} correct -> {out/'graded.jsonl'}")


if __name__ == "__main__":
    main()
