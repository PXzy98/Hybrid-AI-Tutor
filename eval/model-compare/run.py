"""Z2: Qwen3.5 9B vs 27B on the same course questions, both with RAG, plus a vLLM sizing estimate.

Both models are called through OpenRouter (same family, same prompts, temperature 0, thinking off), so the
comparison isolates model size; the course's own server was not reachable when this ran, so local latency
and throughput are not measured here (eval/load-test/run.py does that on the server).

1. Check items (content/topics, 84 multiple-choice questions with an answer key): accuracy without RAG and
   with RAG (4 passages from the app's retriever), per model and level.
2. Open course questions (eval/medical_rag_cases.json, 20): both models answer with RAG; a judge of another
   family compares each pair blind, once in each order (a win counts only when both agree), for correctness,
   use of the passages and clarity.
3. A vLLM memory estimate per model (weights + KV cache), from the parameter counts.

Only course content goes to the hosted models (no student data). The key is OPENROUTER_API_KEY (environment
or the repository's .env). Answers are cached in results/answers.jsonl under a hash of the prompts, so a
rerun only asks what is new or changed. Course material: the bundled MedlinePlus pages only, no uploads.

    .venv\\Scripts\\python eval\\model-compare\\run.py            # full run (costs a few cents to dollars)
    .venv\\Scripts\\python eval\\model-compare\\run.py --smoke    # 3 items, 2 questions: checks the pipeline
"""

import argparse
import hashlib
import json
import os
import re
import statistics
import sys
import time
from pathlib import Path

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))

MODELS = {"9b": "qwen/qwen3.5-9b", "27b": "qwen/qwen3.5-27b"}
JUDGE = "anthropic/claude-sonnet-5.5"
BASE_URL = "https://openrouter.ai/api/v1"
# vLLM sizing, from the models' config.json on Hugging Face (Qwen/Qwen3.5-9B, Qwen/Qwen3.5-27B): a hybrid
# architecture where only every fourth layer is full attention, so only those layers keep a KV cache that
# grows with the context (the linear-attention layers keep a small fixed state per request)
SIZES = {
    "9b": {"params_b": 9.0, "layers": 8, "kv_heads": 4, "head_dim": 256},  # 32 layers, 8 full attention
    "27b": {"params_b": 27.0, "layers": 16, "kv_heads": 4, "head_dim": 256},
}  # 64 layers, 16 full attention

MCQ_SYSTEM = (
    "You are a tutor for a general medical knowledge course. Answer the multiple-choice question. "
    "Reply with the letter of the correct option only (A, B, C or D)."
)
OPEN_SYSTEM = (
    "You are a tutor for a general medical knowledge course. Answer the student's question in at most "
    "120 words, using the course passages when they help. This is education, not medical advice."
)
JUDGE_SYSTEM = (
    "You compare two answers to a student's question in a general medical knowledge course, given the "
    "course passages. Judge correctness first, then use of the passages, then clarity. Reply with JSON "
    'only: {"winner": "A" | "B" | "tie", "reason": "<one sentence>"}.'
)


# ---------------------------------------------------------------------------------------------- inputs
def check_items() -> list[dict]:
    from app.learner.content import load_yaml_topics

    out = []
    for topic in load_yaml_topics(ROOT / "content" / "topics"):
        for item in topic.items:
            out.append(
                {
                    "id": item.id,
                    "topic": topic.topic,
                    "level": item.level,
                    "stem": item.stem,
                    "options": {k: o.text for k, o in sorted(item.options.items())},
                    "answer": item.answer,
                }
            )
    return out


def open_questions() -> list[dict]:
    return json.loads((ROOT / "eval" / "medical_rag_cases.json").read_text(encoding="utf-8"))


class Passages:
    def __init__(self) -> None:
        import tempfile

        from app.rag.medical_hybrid import MedicalHybridRetriever

        # Only the bundled MedlinePlus pages (data/medical_rag), never instructor uploads: an upload has not
        # been through scan_document and must not go to a hosted model. An empty folder as the uploads
        # folder, and no settings (the developer's .env is not read).
        self._empty = tempfile.TemporaryDirectory()
        self.retriever = MedicalHybridRetriever(Path(self._empty.name))

    def __call__(self, query: str, topic: str, k: int = 4) -> list[str]:
        return [p.text for p in self.retriever.retrieve(query, topic, k=k)]


def mcq_prompt(item: dict, passages: list[str] | None) -> str:
    options = "\n".join(f"{k}. {v}" for k, v in item["options"].items())
    context = ("Course passages:\n" + "\n---\n".join(passages) + "\n\n") if passages else ""
    return f"{context}Question: {item['stem']}\n{options}\nAnswer:"


def parse_letter(text: str) -> str | None:
    m = re.search(r"\b([ABCD])\b", (text or "").strip().upper())
    return m.group(1) if m else None


# ------------------------------------------------------------------------------------------------ model
class OpenRouter:
    def __init__(self, key: str) -> None:
        from openai import OpenAI

        self.client = OpenAI(base_url=BASE_URL, api_key=key, timeout=120, max_retries=3)

    def complete(self, model: str, system: str, user: str, max_tokens: int) -> dict:
        start = time.perf_counter()
        r = self.client.chat.completions.create(
            model=model,
            temperature=None if model == JUDGE else 0,
            max_tokens=max_tokens,
            messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
            # the compared models answer without thinking (as the app runs them); the judge requires reasoning
            extra_body={"reasoning": {"effort": "low"} if model == JUDGE else {"enabled": False},
                        "usage": {"include": True}},
        )
        usage = r.usage
        return {
            "text": (r.choices[0].message.content or "") if r.choices else "",
            "seconds": round(time.perf_counter() - start, 2),
            "prompt_tokens": getattr(usage, "prompt_tokens", 0) or 0,
            "completion_tokens": getattr(usage, "completion_tokens", 0) or 0,
            "cost": float(getattr(usage, "cost", 0) or 0),
        }


class Cache:
    def __init__(self, path: Path) -> None:
        self.path = path
        self.rows = {}
        if path.exists():
            for line in path.read_text(encoding="utf-8").splitlines():
                row = json.loads(line)
                self.rows[row["key"]] = row

    def ask(self, api, kind: str, model: str, system: str, user: str, max_tokens: int) -> dict:
        """The cached answer of exactly this request: the key includes a hash of the prompts and the limit, so
        a changed question, passage or prompt is asked again."""
        digest = hashlib.sha256(json.dumps([system, user, max_tokens]).encode("utf-8")).hexdigest()[:20]
        return self.get(f"{kind}|{model}|{digest}", lambda: api.complete(model, system, user, max_tokens))

    def get(self, key: str, make):
        if key not in self.rows:
            row = {"key": key, **make()}
            self.rows[key] = row
            with self.path.open("a", encoding="utf-8") as f:
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
        return self.rows[key]


# ----------------------------------------------------------------------------------------------- report
def kv_gib_per_token(size: dict, kv_bytes: int = 2) -> float:
    return 2 * size["layers"] * size["kv_heads"] * size["head_dim"] * kv_bytes / 2**30


def sizing() -> list[str]:
    lines = [
        "| Model | Weights BF16 | Weights 4-bit (AWQ/GPTQ) | KV cache per 8k-token request (FP16) | "
        "Fits on one 24 GB GPU with 4 parallel 8k requests | 48 GB |",
        "|---|---|---|---|---|---|",
    ]
    for name, s in SIZES.items():
        bf16, q4 = s["params_b"] * 2, s["params_b"] * 0.56  # 4-bit plus scales and unquantized layers
        kv8k = kv_gib_per_token(s) * 8192
        need24 = q4 + 4 * kv8k + 2  # 2 GiB for activations and the CUDA graphs
        lines.append(
            f"| {name} | {bf16:.0f} GiB | {q4:.1f} GiB | {kv8k:.2f} GiB | "
            f"{'yes' if need24 <= 24 else 'no'} ({need24:.1f} GiB) | "
            f"{'yes' if need24 <= 48 else 'no'} |"
        )
    return lines


def accuracy(rows: list[dict]) -> float:
    return statistics.mean(r["correct"] for r in rows) if rows else 0.0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--smoke", action="store_true")
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args()
    key = os.environ.get("OPENROUTER_API_KEY") or _from_dotenv("OPENROUTER_API_KEY")
    if not key:
        sys.exit("set OPENROUTER_API_KEY (environment or .env)")
    a.out.mkdir(parents=True, exist_ok=True)
    api, cache, passages = OpenRouter(key), Cache(a.out / "answers.jsonl"), Passages()
    items, questions = check_items(), open_questions()
    if a.smoke:
        items, questions = items[:3], questions[:2]

    # 1) multiple choice, without and with RAG
    mcq = []
    for item in items:
        ctx = passages(item["stem"], item["topic"])
        for name, model in MODELS.items():
            for rag in (False, True):
                prompt = mcq_prompt(item, ctx if rag else None)
                row = cache.ask(api, "mcq", model, MCQ_SYSTEM, prompt, 16)
                choice = parse_letter(row["text"])
                mcq.append(
                    {
                        "model": name,
                        "rag": rag,
                        "level": item["level"],
                        "id": item["id"],
                        "choice": choice,
                        "correct": choice == item["answer"],
                        "seconds": row["seconds"],
                        "cost": row["cost"],
                        "completion_tokens": row["completion_tokens"],
                    }
                )

    # 2) open questions with RAG, judged blind in both orders
    judged = []
    for q in questions:
        ctx = passages(q["query"], q["topic"])
        user = "Course passages:\n" + "\n---\n".join(ctx) + f"\n\nStudent question: {q['query']}"
        answers = {
            name: cache.ask(api, "open", model, OPEN_SYSTEM, user, 400) for name, model in MODELS.items()
        }
        # judged twice, once in each order: a model wins only when both verdicts agree, else a tie (a single
        # verdict of a reasoning judge changed between runs, and judges prefer one position)
        verdicts, winners = [], []
        for order in (["9b", "27b"], ["27b", "9b"]):
            verdict_prompt = (
                user + f"\n\nAnswer A:\n{answers[order[0]]['text']}\n\nAnswer B:\n{answers[order[1]]['text']}"
            )
            verdict = cache.ask(api, "judge", JUDGE, JUDGE_SYSTEM, verdict_prompt, 4000)
            verdicts.append(verdict)
            winners.append(_winner(verdict["text"], order))
        if "unparsed" in winners:
            winner = "unparsed"
        else:
            winner = winners[0] if winners[0] == winners[1] else "tie"
        judged.append(
            {
                "query": q["query"],
                "topic": q["topic"],
                "winner": winner,
                "verdicts": winners,
                "reason": _reason(verdicts[0]["text"]),
                "words": {n: len(answers[n]["text"].split()) for n in answers},
                "seconds": {n: answers[n]["seconds"] for n in answers},
                "cost": sum(answers[n]["cost"] for n in answers) + sum(v["cost"] for v in verdicts),
            }
        )

    write_report(a.out, mcq, judged, cache, smoke=a.smoke)


def _winner(text: str, order: list[str]) -> str:
    try:
        w = json.loads(re.search(r"\{.*\}", text, re.S).group(0)).get("winner")
    except (AttributeError, ValueError):
        return "unparsed"
    return {"A": order[0], "B": order[1]}.get(w, "tie" if w == "tie" else "unparsed")


def _reason(text: str) -> str:
    try:
        return json.loads(re.search(r"\{.*\}", text, re.S).group(0)).get("reason", "")[:300]
    except (AttributeError, ValueError):
        return ""


def _from_dotenv(name: str) -> str | None:
    path = ROOT / ".env"
    if not path.exists():
        return None
    for line in path.read_text(encoding="utf-8").splitlines():
        if line.strip().startswith(f"{name}="):
            return line.split("=", 1)[1].strip().strip('"').strip("'") or None
    return None


def write_report(out: Path, mcq: list[dict], judged: list[dict], cache: Cache, smoke: bool) -> None:
    total_cost = sum(r.get("cost", 0) for r in cache.rows.values())
    lines = [
        "# Z2: Qwen3.5 9B vs 27B (both with RAG)",
        "",
        f"{'SMOKE RUN: ' if smoke else ''}{len({r['id'] for r in mcq})} check items, {len(judged)} open "
        f"questions. Models through OpenRouter ({MODELS['9b']}, {MODELS['27b']}), temperature 0, thinking "
        f"off; judge {JUDGE} (another family), blind, each pair judged in both orders (a win only when both "
        f"agree). Total cost of the cached calls: "
        f"${total_cost:.2f}.",
        "",
        "## 1. Check items (multiple choice, answer key)",
        "",
        "| Model | Without RAG | With RAG | basic | intermediate | advanced | Median s per answer |",
        "|---|---|---|---|---|---|---|",
    ]
    for name in MODELS:
        rows = [r for r in mcq if r["model"] == name]
        rag = [r for r in rows if r["rag"]]
        by_level = {
            lv: accuracy([r for r in rag if r["level"] == lv]) for lv in ("basic", "intermediate", "advanced")
        }
        lines.append(
            f"| {name} | {accuracy([r for r in rows if not r['rag']]):.1%} | {accuracy(rag):.1%} | "
            f"{by_level['basic']:.1%} | {by_level['intermediate']:.1%} | {by_level['advanced']:.1%} | "
            f"{statistics.median(r['seconds'] for r in rows):.2f} |"
        )
    unparsed = sum(1 for r in mcq if r["choice"] is None)
    if mcq and min(accuracy([r for r in mcq if r["model"] == n]) for n in MODELS) >= 0.95:
        lines += ["", "**Ceiling effect**: both models answer (almost) every item correctly, even without "
                  "RAG. These items do not separate the models; the open questions below do."]
    lines += [
        "",
        f"Answers without a readable letter count as wrong: {unparsed}.",
        "",
        "Items both models get wrong with RAG: "
        + (
            ", ".join(
                sorted(
                    i
                    for i in {r["id"] for r in mcq}
                    if all(not r["correct"] for r in mcq if r["id"] == i and r["rag"])
                )
            )
            or "none"
        )
        + ".",
        "",
        "## 2. Open questions with RAG (pairwise, judged)",
        "",
    ]
    wins = {k: sum(1 for j in judged if j["winner"] == k) for k in ("9b", "27b", "tie", "unparsed")}
    lines += [
        "| 9B better | 27B better | Tie | Unparsed |",
        "|---|---|---|---|",
        f"| {wins['9b']} | {wins['27b']} | {wins['tie']} | {wins['unparsed']} |",
        "",
    ]
    if judged:
        lines += ["| Question | Winner | Judge's reason |", "|---|---|---|"]
        lines += [f"| {j['query']} | {j['winner']} | {j['reason'].replace('|', '/')} |" for j in judged]
    lines += [
        "",
        "## 3. vLLM memory estimate (not measured)",
        "",
        "Weights from the parameter count; KV cache 2 × full-attention layers × KV heads × head size × "
        "2 bytes per token, from the models' config.json (only every fourth layer is full attention; the "
        "fixed state of the linear-attention layers is left out). An estimate to plan with, not a "
        "measurement.",
        "",
        *sizing(),
        "",
        "## Limits",
        "",
        "- Hosted inference, not the course server: quality is comparable, latency and throughput are not "
        "(run eval/load-test on the server).",
        "- The check items are the unreviewed draft bank of the demo course; a wrong answer key counts "
        "against both models alike.",
        "- One judge model; 20 open questions give a wide margin of error.",
    ]
    (out / "report.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (out / "summary.json").write_text(
        json.dumps({"mcq": mcq, "judged": judged, "cost": total_cost}, indent=2, ensure_ascii=False),
        encoding="utf-8",
    )
    print("\n".join(lines))


if __name__ == "__main__":
    main()
