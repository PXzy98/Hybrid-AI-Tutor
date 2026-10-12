"""Ask every model the boundary test questions and save the raw answers.

Examples
  python bench.py --models qwen3.5:2b qwen3.5:4b qwen3.5:9b
  python bench.py --models qwen3.5:9b qwen3.5:27b --think both
  python bench.py --models qwen3.5:4b --limit 5 --out results/smoke.jsonl      # smoke test
  python bench.py --models gemma4:e4b --repeats 3 --temperature 0.7            # stability test

Answers are appended to results/answers.jsonl. Re-running skips finished
(model, think, repeat, id) combinations, so an interrupted run can continue.
"""
import argparse, json, os, sys, time
from pathlib import Path

import requests

BASE = "You are a helpful tutor for a university course on medical AI and health informatics."
LANG = " Reply in the same language as the question."
SYSTEM = {
    "mcq": BASE + LANG + " You may reason briefly. The LAST line of your reply must be exactly "
                         "'ANSWER: X' where X is one letter (A, B, C or D).",
    "numeric": BASE + LANG + " You may show brief working. The LAST line of your reply must be "
                             "'ANSWER: <number>' with a plain decimal number (no units, no % sign).",
    "short": BASE + LANG + " The LAST line of your reply must be 'ANSWER: <short answer>'.",
    "open": BASE + LANG + " Answer accurately. If a premise of the question is false, or you do not "
                          "know, say so clearly instead of guessing.",
    "rule": BASE + " Follow the user's instructions and formatting requirements exactly.",
}


class ThinkUnsupported(Exception):
    pass


def ask(host, model, t, a, think):
    system = t.get("system") or SYSTEM[t["answer_type"]]
    max_tokens = a.max_tokens or (8192 if think else 2048)
    body = {
        "model": model, "stream": False,
        "messages": [{"role": "system", "content": system},
                     {"role": "user", "content": t["question"]}],
        "options": {"temperature": a.temperature, "seed": 42 + a._rep, "num_ctx": a.num_ctx,
                    "num_predict": max_tokens},
    }
    if think is not None:
        body["think"] = think
    r = requests.post(f"{host}/api/chat", json=body, timeout=a.timeout)
    if r.status_code == 400 and think is not None and "think" in r.text.lower():
        if think:
            raise ThinkUnsupported(model)
        body.pop("think")
        r = requests.post(f"{host}/api/chat", json=body, timeout=a.timeout)
    r.raise_for_status()
    d = r.json()
    ns = 1e9
    gen = d.get("eval_duration", 0) / ns
    return {
        "answer": d["message"].get("content", ""),
        "thinking": d["message"].get("thinking"),
        "out_tokens": d.get("eval_count"),
        "hit_max_tokens": (d.get("eval_count") or 0) >= max_tokens - 1,
        "ttft_s": (d.get("load_duration", 0) + d.get("prompt_eval_duration", 0)) / ns,
        "total_s": d.get("total_duration", 0) / ns,
        "tok_per_s": (d.get("eval_count", 0) / gen) if gen else None,
    }


def ollama_ps(host):
    try:
        out = []
        for m in requests.get(f"{host}/api/ps", timeout=10).json().get("models", []):
            size, vram = m.get("size", 0), m.get("size_vram", 0)
            out.append({"name": m.get("name"), "size_gb": round(size / 1e9, 2),
                        "vram_gb": round(vram / 1e9, 2),
                        "gpu_pct": round(100 * vram / size, 1) if size else None})
        return out
    except Exception as e:  # noqa: BLE001
        return [{"error": str(e)}]


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--host", default=os.environ.get("OLLAMA_URL", "http://192.168.2.25:11434"))
    ap.add_argument("--models", nargs="+", required=True)
    ap.add_argument("--testset", default="data/boundary_set.jsonl")
    ap.add_argument("--out", default="results/answers.jsonl")
    ap.add_argument("--think", choices=["default", "on", "off", "both"], default="off",
                    help="thinking mode for models that support it (default: off)")
    ap.add_argument("--repeats", type=int, default=1)
    ap.add_argument("--temperature", type=float, default=0.0)
    ap.add_argument("--num-ctx", type=int, default=4096)
    ap.add_argument("--max-tokens", type=int, help="default 2048 (8192 with thinking)")
    ap.add_argument("--dimensions", nargs="*", help="e.g. calculation knowledge")
    ap.add_argument("--levels", nargs="*", type=int)
    ap.add_argument("--limit", type=int)
    ap.add_argument("--timeout", type=int, default=900)
    a = ap.parse_args()

    tests = [json.loads(l) for l in open(a.testset, encoding="utf-8") if l.strip()]
    if a.dimensions:
        tests = [t for t in tests if t["dimension"] in a.dimensions]
    if a.levels:
        tests = [t for t in tests if t["level"] in a.levels]
    if a.limit:
        tests = tests[: a.limit]

    out = Path(a.out); out.parent.mkdir(parents=True, exist_ok=True)
    key = lambda m, th, rep, i: f"{m}|{th}|{rep}|{i}"
    done = set()
    if out.exists():
        for l in out.open(encoding="utf-8"):
            if l.strip():
                r = json.loads(l)
                if not r.get("error"):
                    done.add(key(r["model"], r.get("think"), r.get("repeat", 0), r["id"]))

    modes = {"default": [None], "on": [True], "off": [False], "both": [False, True]}[a.think]
    status = out.parent / "server_status.jsonl"

    for model in a.models:
        # warm-up (also checks that the model is pulled)
        try:
            requests.post(f"{a.host}/api/chat", json={
                "model": model, "stream": False, "messages": [{"role": "user", "content": "hi"}],
                "options": {"num_ctx": a.num_ctx, "num_predict": 1}}, timeout=a.timeout).raise_for_status()
        except Exception as e:  # noqa: BLE001
            print(f"[{model}] warm-up failed: {e}\n  -> run `ollama pull {model}` on the server")
            continue
        ps = ollama_ps(a.host)
        with status.open("a", encoding="utf-8") as f:
            f.write(json.dumps({"model": model, "num_ctx": a.num_ctx,
                                "time": time.strftime("%Y-%m-%d %H:%M:%S"), "ollama_ps": ps}) + "\n")
        for m in ps:
            if m.get("name") == model and m.get("gpu_pct") is not None and m["gpu_pct"] < 100:
                print(f"  WARNING: {model} is only {m['gpu_pct']}% on GPU (part runs on CPU, slower). "
                      f"Results are still valid for quality; note it for speed.")

        for think in modes:
            for rep in range(a.repeats):
                a._rep = rep
                todo = [t for t in tests if key(model, think, rep, t["id"]) not in done]
                if not todo:
                    continue
                print(f"\n=== {model}  think={think}  repeat={rep}: {len(todo)} questions ===")
                stop = False
                for i, t in enumerate(todo, 1):
                    rec = {"model": model, "think": think, "repeat": rep, "temperature": a.temperature,
                           "id": t["id"], "dimension": t["dimension"], "level": t["level"]}
                    try:
                        rec.update(ask(a.host, model, t, a, think))
                        flag = "  (hit max tokens)" if rec["hit_max_tokens"] else ""
                        print(f"  [{i}/{len(todo)}] {t['id']:8s} {rec['total_s']:6.1f}s "
                              f"{(rec['tok_per_s'] or 0):6.1f} tok/s{flag}")
                    except ThinkUnsupported:
                        print(f"  {model} has no thinking mode -> skip think=True")
                        stop = True
                        break
                    except Exception as e:  # noqa: BLE001
                        rec["error"] = str(e)
                        print(f"  [{i}/{len(todo)}] {t['id']} ERROR {e}")
                    with out.open("a", encoding="utf-8") as f:
                        f.write(json.dumps(rec, ensure_ascii=False) + "\n")
                if stop:
                    break


if __name__ == "__main__":
    main()
