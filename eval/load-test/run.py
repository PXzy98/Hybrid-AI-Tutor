"""Load test of a model connection through the model gateway (task Z6).

Sends `--requests` short, fictional questions with `--concurrency` at a time through `Gateway.complete`
(the same queue and limits as the app: `limits.models.max_concurrent`, `queue_timeout_seconds`) and writes
throughput, latency (p50/p95/max), time to the first token (with --stream) and errors to a report.

Real model (fictional prompts only; never student data):
    python eval/load-test/run.py --kind openai_compat --base-url http://<vllm-host>:8000/v1 \\
        --model Qwen/Qwen3.5-9B --concurrency 20 --requests 200 --out eval-out/load
Smoke (CI, no model): python eval/load-test/run.py --smoke --out eval-out/load
"""
import argparse
import asyncio
import os
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from app.core.config import Settings  # noqa: E402
from app.core.schemas import EffectiveSettings  # noqa: E402
from app.llm.fake import FakeLLMClient  # noqa: E402
from app.llm.gateway import Gateway  # noqa: E402

QUESTIONS = [  # fictional, general health-education questions (scale H3: up to 20 at the same time)
    "What does the top number of a blood pressure reading mean?",
    "Why is regular measurement important when high blood pressure has no symptoms?",
    "What are common triggers of asthma symptoms?",
    "How is type 2 diabetes usually diagnosed?",
    "What is the difference between a migraine and a tension headache?",
]


class _Services:
    """The two attributes the gateway needs, without starting the app."""

    def __init__(self, settings: Settings, client) -> None:
        self.settings, self.local_llm, self.engine, self.cloud_llm = settings, client, None, None


def _client(a):
    if a.smoke:
        async def slow(messages):
            await asyncio.sleep(0.02)
            return "A short fictional answer about blood pressure."
        return _SlowFake(slow)
    from app.llm.ollama_client import OllamaClient
    from app.llm.openai_compat import OpenAICompatClient

    if a.kind == "ollama":
        return OllamaClient(a.base_url, a.model, timeout_s=a.timeout, max_tokens=a.max_tokens)
    return OpenAICompatClient(a.base_url, os.environ.get("LOAD_TEST_API_KEY", "none"), a.model,
                              timeout_s=a.timeout, max_tokens=a.max_tokens)


class _SlowFake(FakeLLMClient):
    def __init__(self, reply) -> None:
        super().__init__("x", model="fake-load")
        self._reply = reply

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        text = await self._reply(messages)
        return (await FakeLLMClient(text, model="fake-load").complete(messages))


async def _one(gateway, eff, i: int, stream: bool) -> dict:
    messages = [{"role": "system", "content": "Answer in at most three sentences."},
                {"role": "user", "content": QUESTIONS[i % len(QUESTIONS)]}]
    t0 = time.perf_counter()
    try:
        if stream:
            tokens = await gateway.complete("local", messages, settings=eff, trust_required="trusted_local",
                                            stream=True)
            first = None
            async for _ in tokens:
                first = first or time.perf_counter() - t0
            return {"ok": True, "latency": time.perf_counter() - t0, "first": first}
        await gateway.complete("local", messages, settings=eff, trust_required="trusted_local")
        return {"ok": True, "latency": time.perf_counter() - t0, "first": None}
    except Exception as e:  # noqa: BLE001 - every failure is counted, the run goes on
        return {"ok": False, "latency": time.perf_counter() - t0, "error": type(e).__name__}


async def run(a) -> dict:
    settings = Settings(_env_file=None)  # defaults of config.yaml; the connection comes from the arguments
    limits = settings.limits.models.model_copy(update={"max_concurrent": a.concurrency,
                                                       "queue_timeout_seconds": a.queue_timeout})
    settings = settings.model_copy(update={"limits": settings.limits.model_copy(update={"models": limits})})
    gateway = Gateway(_Services(settings, _client(a)))
    eff = EffectiveSettings(course_id=0)
    t0 = time.perf_counter()
    results = await asyncio.gather(*(_one(gateway, eff, i, a.stream) for i in range(a.requests)))
    wall = time.perf_counter() - t0
    ok = [r for r in results if r["ok"]]
    lat = sorted(r["latency"] for r in ok)
    errors: dict[str, int] = {}
    for r in results:
        if not r["ok"]:
            errors[r["error"]] = errors.get(r["error"], 0) + 1

    def pct(values, p):
        return values[min(len(values) - 1, int(round(p * (len(values) - 1))))] if values else None

    firsts = sorted(r["first"] for r in ok if r.get("first") is not None)
    return {"requests": a.requests, "concurrency": a.concurrency, "ok": len(ok), "errors": errors,
            "wall_s": wall, "throughput_rps": len(ok) / wall if wall else 0,
            "p50_s": pct(lat, 0.5), "p95_s": pct(lat, 0.95), "max_s": lat[-1] if lat else None,
            "mean_s": statistics.mean(lat) if lat else None,
            "first_token_p50_s": pct(firsts, 0.5), "first_token_p95_s": pct(firsts, 0.95)}


def main(argv=None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--smoke", action="store_true", help="fake model, no network (CI)")
    ap.add_argument("--kind", choices=["ollama", "openai_compat"], default="openai_compat")
    ap.add_argument("--base-url", default="http://127.0.0.1:8000/v1")
    ap.add_argument("--model", default="Qwen/Qwen3.5-9B")
    ap.add_argument("--concurrency", type=int, default=20)
    ap.add_argument("--requests", type=int, default=100)
    ap.add_argument("--queue-timeout", type=float, default=120)
    ap.add_argument("--timeout", type=float, default=120)
    ap.add_argument("--max-tokens", type=int, default=200)
    ap.add_argument("--stream", action="store_true", help="measure the time to the first token")
    ap.add_argument("--out", type=Path, default=ROOT / "eval-out" / "load")
    a = ap.parse_args(argv)
    if a.smoke:
        a.requests, a.concurrency = min(a.requests, 40), min(a.concurrency, 8)
    r = asyncio.run(run(a))

    def s(v):
        return "-" if v is None else f"{v:.2f}"

    model = "fake (smoke)" if a.smoke else f"{a.kind} {a.model} at {a.base_url}"
    lines = [f"# Load test: {model}", "",
             f"{r['requests']} requests, {r['concurrency']} at a time, through the model gateway.", "",
             "| OK | Errors | Wall time (s) | Throughput (req/s) | p50 (s) | p95 (s) | max (s) | "
             "first token p50 / p95 (s) |",
             "|---|---|---|---|---|---|---|---|",
             f"| {r['ok']} | {sum(r['errors'].values())} {r['errors'] or ''} | {s(r['wall_s'])} | "
             f"{s(r['throughput_rps'])} | {s(r['p50_s'])} | {s(r['p95_s'])} | {s(r['max_s'])} | "
             f"{s(r['first_token_p50_s'])} / {s(r['first_token_p95_s'])} |"]
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    print("\n".join(lines))
    return 0 if r["ok"] == r["requests"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
