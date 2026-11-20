"""Manual routing check with the real models: the shipped router decides, the chosen model answers.

For a few public questions of the open course packs (never student data) it runs the semantic router with the
settings of `config.yaml` (capability gate, then the evidence step on passages retrieved from the unpacked
pack), and sends the question to the model the router chose: the trusted local vLLM for "local", the cloud
model for "cloud". It is the routing decision and the two model paths, not the whole app pipeline (no
accounts, no privacy filter, no cloud gate: the questions are public).

    python eval/routing-ece/manual_check.py --env <path to .env> [--out DIR]
"""
import argparse
import asyncio
import json
import sys
import tempfile
import time
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "eval" / "course-rag-packs"))

import answer_quality as aq  # noqa: E402
import run as rag  # noqa: E402

from app.core.config import get_settings  # noqa: E402
from app.core.schemas import PIIResult, RouteInput  # noqa: E402
from app.privacy.profiles import privacy_profile  # noqa: E402
from app.prompts import system_prompt  # noqa: E402
from app.prompts.render import material_block  # noqa: E402
from app.routing.semantic import SemanticRouter  # noqa: E402

CASES = [  # (pack, question id), then free questions without a pack
    ("harvard_cs50x", "cs50-02"), ("harvard_cs50x", "cs50-03"), ("mit_6_002_circuits", "circ-01"),
    ("mit_6_002_circuits", "circ-02"),
]
FREE = [("harvard_cs50x", "Prove that the average running time of quicksort is O(n log n) with a full "
                          "recurrence analysis and compare it with merge sort."),
        ("mit_6_002_circuits", "What changed in the most recent standard for USB power delivery this year?")]


def pii_stub(text: str) -> PIIResult:
    return PIIResult(sanitized_text=text, redacted_original=text, entities=[], cloud_safe=True)


async def main_async(a):
    env = aq.read_env(a.env)
    cfg = get_settings()
    router = SemanticRouter()
    rows = []
    vbase = env["VLLM_BASE_URL"].rstrip("/")
    vbase = vbase if vbase.endswith("/v1") else vbase + "/v1"
    async with httpx.AsyncClient() as client:
        lmodel = (await client.get(vbase + "/models", headers=aq.auth(env.get("VLLM_KEY")), timeout=20)
                  ).json()["data"][0]["id"]
        for pack in sorted({p for p, _ in CASES} | {p for p, _ in FREE}):
            pack_dir = rag.PACKS_DIR / pack
            manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
            questions = [(q, None) for p, q in CASES if p == pack] + [(None, t) for p, t in FREE if p == pack]
            by_id = {r["id"]: r for r in rag.load_questions(pack)}
            with tempfile.TemporaryDirectory(prefix="route-check-") as tmp:
                retriever, _, _ = rag.build_index(pack_dir, manifest, Path(tmp))
                for qid, text in questions:
                    row = by_id[qid] if qid else {"question": text, "module_order": None, "type": "free"}
                    hits = retriever.retrieve(rag.COURSE_ID, row["module_order"], row["question"], k=4)
                    x = RouteInput(sanitized_question=row["question"], topic="general", pii=pii_stub(row["question"]),
                                   passage_count=len(hits), passages=hits)
                    t0 = time.perf_counter()
                    score = router.route_score(x)
                    route_ms = (time.perf_counter() - t0) * 1000
                    system = system_prompt(subject=privacy_profile(manifest["course_type"]).prompt)
                    user = f"Topic: {pack}\n\n{material_block([h.text for h in hits])}\n\nStudent question: {row['question']}"
                    msgs = [{"role": "system", "content": system}, {"role": "user", "content": user}]
                    t0 = time.perf_counter()
                    if score.target == "local":
                        text_out, usage = await aq.chat(client, vbase, env.get("VLLM_KEY"), lmodel, msgs, 400,
                                                        {"chat_template_kwargs": {"enable_thinking": False}})
                        used = lmodel
                    else:
                        text_out, usage = await aq.chat(client, env["CLOUD_BASE_URL"], env["CLOUD_API_KEY"],
                                                        env["CLOUD_MODEL"], msgs, 4000)
                        used = "cloud model"
                    rows.append({"pack": pack, "question": row["question"], "target": score.target,
                                 "cloud_probability": round(score.analysis.cloud_probability, 2),
                                 "reliable": score.analysis.reliable, "evidence": score.evidence.status,
                                 "route_ms": round(route_ms), "answered_by": used,
                                 "answer_s": round(time.perf_counter() - t0, 1),
                                 "answer_start": text_out.strip()[:140].replace("\n", " ")})
                    print(rows[-1], flush=True)
    return cfg, rows


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, required=True)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    a = ap.parse_args()
    cfg, rows = asyncio.run(main_async(a))
    lines = [f"Router settings: threshold {cfg.routing.threshold}, uncertainty margin "
             f"{cfg.routing.uncertainty_margin}, default method {cfg.routing.default_method}.", "",
             "| Question | Route | Cloud prob. | In support | Evidence | Answered by | Answer time (s) |",
             "|---|---|---|---|---|---|---|"]
    for r in rows:
        lines.append(f"| {r['question'][:80]} | {r['target']} | {r['cloud_probability']} | {r['reliable']} | "
                     f"{r['evidence']} | {r['answered_by']} | {r['answer_s']} |")
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "manual_check.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (a.out / "manual_check.json").write_text(json.dumps(rows, indent=1, ensure_ascii=False), encoding="utf-8")
    print("\n".join(lines))


if __name__ == "__main__":
    main()
