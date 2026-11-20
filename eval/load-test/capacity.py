"""Z23: capacity of a vLLM server in tokens per second at 1, 4, 8, 16, 32 requests at the same time.

Streams short fictional course questions straight to the OpenAI-compatible endpoint (no gateway, so the
server limit is measured, not the app's `max_concurrent`) and counts the real completion tokens from the
server's usage record. Thinking is off, as in the app.

    python eval/load-test/capacity.py --env <path to .env> --levels 1,4,8,16,32 --out eval/load-test/results

The base URL and key are read from the env file (VLLM_BASE_URL, VLLM_KEY) and never printed.
"""
import argparse
import asyncio
import json
import statistics
import time
from pathlib import Path

import httpx

QUESTIONS = [  # fictional / generic course questions
    "Explain in a short paragraph what a binary search does and why it needs a sorted list.",
    "What does the current law for a circuit node say, and how is it used to analyse a node?",
    "Give a short explanation of what a recursive function is, with a small example.",
    "How does an RC low-pass filter change the amplitude of a high-frequency signal?",
    "What is the difference between a stack and a queue? Answer with an example for each.",
    "Explain what the time complexity O(n log n) means for a sorting algorithm.",
    "Why is a diode used in a rectifier circuit? Describe the idea briefly.",
    "What is a pointer in C, and why can it be dangerous?",
]


def read_env(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def auth(key):
    return {"Authorization": f"Bearer {key}"} if key else {}


async def one(client, url, key, model, i, max_tokens, timeout, context_words=0):
    context = ""
    if context_words:  # fictional passages like retrieved course text; unique per request (no prefix cache)
        passages = " ".join(
            f"Passage {i}-{j}: the fictional module {j} covers topic {i * 7 + j} with definitions and examples."
            for j in range(context_words // 14))
        context = "Course passages (fictional).\n" + passages + "\n\n"
    body = {"model": model, "stream": True, "max_tokens": max_tokens, "temperature": 0.2,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": [{"role": "system", "content": "Answer clearly and completely."},
                         {"role": "user", "content": context + QUESTIONS[i % len(QUESTIONS)]}]}
    t0 = time.perf_counter()
    first = None
    tokens = None
    chunks = 0
    try:
        async with client.stream("POST", url + "/chat/completions", json=body, timeout=timeout,
                                 headers=auth(key)) as r:
            if r.status_code != 200:
                return {"ok": False, "error": f"HTTP {r.status_code}", "latency": time.perf_counter() - t0}
            async for line in r.aiter_lines():
                if not line.startswith("data:") or line.strip() == "data: [DONE]":
                    continue
                d = json.loads(line[5:])
                if d.get("usage"):
                    tokens = d["usage"].get("completion_tokens")
                ch = d.get("choices") or []
                if ch and ch[0].get("delta", {}).get("content"):
                    chunks += 1
                    first = first or time.perf_counter() - t0
        lat = time.perf_counter() - t0
        tokens = tokens or chunks
        gen = max(lat - (first or 0), 1e-6)
        return {"ok": True, "latency": lat, "first": first, "tokens": tokens,
                "tps": tokens / lat, "decode_tps": tokens / gen}
    except Exception as e:  # noqa: BLE001 - counted, the run goes on
        return {"ok": False, "error": type(e).__name__, "latency": time.perf_counter() - t0}


def pct(v, p):
    v = sorted(v)
    return v[min(len(v) - 1, int(round(p * (len(v) - 1))))] if v else None


async def level(url, key, model, n, rounds, max_tokens, timeout, context_words=0):
    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=n + 4)) as client:
        t0 = time.perf_counter()
        rs = []
        for _ in range(rounds):
            rs += await asyncio.gather(*(one(client, url, key, model, i, max_tokens, timeout, context_words)
                                         for i in range(n)))
        wall = time.perf_counter() - t0
    ok = [r for r in rs if r["ok"]]
    errs: dict[str, int] = {}
    for r in rs:
        if not r["ok"]:
            errs[r["error"]] = errs.get(r["error"], 0) + 1
    tot = sum(r["tokens"] for r in ok)
    return {"concurrent": n, "requests": len(rs), "ok": len(ok), "errors": errs, "wall_s": wall,
            "p50": pct([r["latency"] for r in ok], .5), "p95": pct([r["latency"] for r in ok], .95),
            "first_p50": pct([r["first"] for r in ok if r["first"]], .5),
            "first_p95": pct([r["first"] for r in ok if r["first"]], .95),
            "tokens_per_answer": statistics.mean(r["tokens"] for r in ok) if ok else None,
            "tps_per_request": statistics.mean(r["tps"] for r in ok) if ok else None,
            "decode_tps_per_request": statistics.mean(r["decode_tps"] for r in ok) if ok else None,
            "total_tps": tot / wall if wall else 0}


async def main_async(a):
    env = read_env(a.env)
    url, key = env["VLLM_BASE_URL"].rstrip("/"), env.get("VLLM_KEY", "")
    if not url.endswith("/v1"):
        url += "/v1"
    model = a.model
    if not model:
        async with httpx.AsyncClient() as c:
            r = await c.get(url + "/models", headers=auth(key), timeout=20)
            model = r.json()["data"][0]["id"]
    async with httpx.AsyncClient() as c:
        await one(c, url, key, model, 0, 20, a.timeout)  # warm-up
    rows = []
    for n in a.levels:
        r = await level(url, key, model, n, a.rounds, a.max_tokens, a.timeout, a.context_words)
        rows.append(r)
        print(n, {k: (round(v, 2) if isinstance(v, float) else v) for k, v in r.items()}, flush=True)
    return model, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, required=True)
    ap.add_argument("--model", default="")
    ap.add_argument("--levels", type=lambda s: [int(x) for x in s.split(",")], default=[1, 4, 8, 16, 32])
    ap.add_argument("--rounds", type=int, default=2, help="waves of N requests per level")
    ap.add_argument("--max-tokens", type=int, default=400)
    ap.add_argument("--context-words", type=int, default=0,
                    help="fictional passages added to every question (the app sends about 1500 words)")
    ap.add_argument("--name", default="capacity")
    ap.add_argument("--timeout", type=float, default=300)
    ap.add_argument("--out", type=Path, required=True)
    a = ap.parse_args()
    model, rows = asyncio.run(main_async(a))

    def s(v):
        return "-" if v is None else f"{v:.2f}"

    lines = [f"# vLLM capacity (Z23): {model}", "",
             f"Streaming, max_tokens {a.max_tokens}, thinking off, {a.rounds} waves per level, "
             f"fictional course questions plus {a.context_words} words of fictional passages, straight to the server (no app queue).", "",
             "| At the same time | OK / sent | Errors | Latency p50 (s) | p95 (s) | First token p50 / p95 (s) | "
             "Tokens per answer | Tokens/s per request | Total tokens/s |",
             "|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['concurrent']} | {r['ok']} / {r['requests']} | {r['errors'] or 0} | {s(r['p50'])} | "
                     f"{s(r['p95'])} | {s(r['first_p50'])} / {s(r['first_p95'])} | {s(r['tokens_per_answer'])} | "
                     f"{s(r['tps_per_request'])} | {s(r['total_tps'])} |")
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / f"{a.name}.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (a.out / f"{a.name}.json").write_text(json.dumps({"model": model, "rows": rows}, indent=1), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
