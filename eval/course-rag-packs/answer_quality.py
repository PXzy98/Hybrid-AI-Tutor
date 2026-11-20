"""Answer quality of the local model on the open course packs (no app, no accounts).

For each question of `questions/<pack>.jsonl` (public text written from the pack material): retrieve k
passages with the course index (scoped to the question's module, as the product does), build the messages
with the app's own prompt code (`system_prompt` of the pack's privacy profile + `material_block`), let the
trusted local vLLM answer (thinking off, streaming not needed here), and let a judge score the answer against
the passages. The judge is the same trusted local model by default (it judges its own answers: read the scores as
a check, not a neutral grade). Course pack text is real (public) course material, not fictional, so rule 6 keeps
it away from hosted models: `--hosted-judge` sends it to the cloud model only when the project has explicitly
allowed that.

Judge scores: correct 0 wrong / 1 partly / 2 correct; grounded 0 not supported by the passages / 1 partly /
2 supported. A question with `gold: []` is not in the material: the right answer says so (abstain).

    python eval/course-rag-packs/answer_quality.py --env <path to .env> --packs mit_6_002_circuits,harvard_cs50x
        --per-pack 10 --out eval/course-rag-packs/results
`instructor_only/` files are never read (the index stages the student-visible material only).
"""
import argparse
import asyncio
import json
import re
import sys
import tempfile
from pathlib import Path

import httpx

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(HERE))

import run as rag  # noqa: E402  (the retrieval harness of S11)

from app.privacy.profiles import privacy_profile  # noqa: E402
from app.prompts import system_prompt  # noqa: E402
from app.prompts.render import material_block  # noqa: E402

JUDGE = """You grade the answer of a course tutor. You get the student's question, the course passages the tutor
was given, and the tutor's answer. Judge only what is written.
correct: 2 = the answer is correct and answers the question; 1 = partly correct or incomplete; 0 = wrong or
does not answer.
grounded: 2 = the claims that depend on the course are supported by the passages (general textbook knowledge
that is true counts as fine); 1 = partly; 0 = contradicts the passages or invents course facts (dates, rules,
file names).
abstain_ok: only if the question is NOT covered by the passages: true when the answer says the course material
does not contain it (or answers only with clearly general knowledge, labelled as such), else false; else null.
Reply with one JSON object: {"correct": n, "grounded": n, "abstain_ok": true|false|null, "note": "<=20 words"}"""


def read_env(path: Path) -> dict:
    out = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        if "=" in line and not line.lstrip().startswith("#"):
            k, v = line.split("=", 1)
            out[k.strip()] = v.strip().strip('"').strip("'")
    return out


def auth(key):
    return {"Authorization": f"Bearer {key}"} if key else {}


async def chat(client, base, key, model, messages, max_tokens, extra=None):
    body = {"model": model, "messages": messages, "temperature": 0.2, "max_tokens": max_tokens, **(extra or {})}
    r = await client.post(base.rstrip("/") + "/chat/completions", json=body, headers=auth(key), timeout=300)
    r.raise_for_status()
    d = r.json()
    return d["choices"][0]["message"]["content"] or "", d.get("usage", {})


def pick(rows: list[dict], n: int) -> list[dict]:
    """A fixed mix: the unanswerable questions first (up to 2), then by type in turn, in file order."""
    out = [r for r in rows if not r["gold"]][:2]
    by_type = {t: [r for r in rows if r["gold"] and r["type"] == t] for t in rag.TYPES}
    while len(out) < n and any(by_type.values()):
        for t in rag.TYPES:
            if by_type[t] and len(out) < n:
                out.append(by_type[t].pop(0))
    return out


async def run_pack(pack, rows, env, k, tmp, hosted_judge=False):
    pack_dir = rag.PACKS_DIR / pack
    manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
    course_type = manifest["course_type"]
    prompt_subject = privacy_profile(course_type).prompt
    retriever, refused, _ = rag.build_index(pack_dir, manifest, Path(tmp))
    system = system_prompt(subject=prompt_subject)
    vbase = env["VLLM_BASE_URL"].rstrip("/")
    vbase = vbase if vbase.endswith("/v1") else vbase + "/v1"
    async with httpx.AsyncClient() as client:
        model = (await client.get(vbase + "/models", headers=auth(env.get("VLLM_KEY")), timeout=20)
                 ).json()["data"][0]["id"]
        out = []
        for row in rows:
            kind = "logistics" if row["type"] == "logistics" else "concept"
            hits = retriever.retrieve(rag.COURSE_ID, row["module_order"], row["question"], k=k, question_kind=kind)
            passages = [h.text for h in hits]
            user = f"Topic: {pack}\n\n{material_block(passages)}\n\nStudent question: {row['question']}"
            messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
            answer, usage = await chat(client, vbase, env.get("VLLM_KEY"), model, messages, 600,
                                       {"chat_template_kwargs": {"enable_thinking": False}})
            covered = "yes" if row["gold"] else "no"
            jmsg = [{"role": "system", "content": JUDGE},
                    {"role": "user", "content": f"Question: {row['question']}\n\nThe question is covered by the "
                     f"course material: {covered}\n\nPassages:\n{material_block(passages)}\n\n"
                     f"Tutor answer:\n{answer}"}]
            try:
                if hosted_judge:
                    text, _ = await chat(client, env["CLOUD_BASE_URL"], env["CLOUD_API_KEY"], env["CLOUD_MODEL"],
                                         jmsg, 4000)
                else:
                    text, _ = await chat(client, vbase, env.get("VLLM_KEY"), model, jmsg, 800,
                                         {"chat_template_kwargs": {"enable_thinking": False}})
                verdict = json.loads(re.search(r"\{.*\}", text, re.S).group(0))
            except Exception as e:  # noqa: BLE001 - the row stays, without a verdict
                verdict = {"error": type(e).__name__}
            gold_hit = any(rag.source_to_pack_path(h.source, rag.file_map(pack_dir, manifest)) in row["gold"]
                           for h in hits)
            out.append({"id": row["id"], "type": row["type"], "question": row["question"], "covered": bool(row["gold"]),
                        "retrieved_gold": gold_hit, "answer": answer,
                        "completion_tokens": usage.get("completion_tokens"), **verdict})
            print(pack, row["id"], {k2: verdict.get(k2) for k2 in ("correct", "grounded", "abstain_ok")}, flush=True)
    return {"pack": pack, "course_type": course_type, "subject_prompt": prompt_subject, "local_model": model,
            "refused_files": refused, "rows": out}


def table(res):
    rows = [r for r in res["rows"] if "correct" in r]
    ans = [r for r in rows if r["covered"]]
    una = [r for r in rows if not r["covered"]]

    def mean(v):
        return f"{sum(v) / len(v):.2f}" if v else "-"

    return (f"| {res['pack']} | {res['course_type']} / {res['subject_prompt']} | {len(ans)} | "
            f"{sum(r['retrieved_gold'] for r in ans)} / {len(ans)} | "
            f"{sum(r['correct'] == 2 for r in ans)} / {sum(r['correct'] == 1 for r in ans)} / "
            f"{sum(r['correct'] == 0 for r in ans)} | {mean([r['grounded'] for r in ans])} | "
            f"{sum(bool(r['abstain_ok']) for r in una)} / {len(una)} |")


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--env", type=Path, required=True)
    ap.add_argument("--packs", default="mit_6_002_circuits,harvard_cs50x")
    ap.add_argument("--per-pack", type=int, default=10)
    ap.add_argument("--k", type=int, default=4)
    ap.add_argument("--out", type=Path, default=HERE / "results")
    ap.add_argument("--hosted-judge", action="store_true",
                    help="judge with the cloud model: sends real course text to a hosted API (rule 6: only with "
                         "the project's explicit permission)")
    a = ap.parse_args()
    env = read_env(a.env)
    results = []
    for pack in a.packs.split(","):
        rows = pick(rag.load_questions(pack), a.per_pack)
        with tempfile.TemporaryDirectory(prefix="pack-quality-") as tmp:
            results.append(asyncio.run(run_pack(pack, rows, env, a.k, tmp, a.hosted_judge)))
    a.out.mkdir(parents=True, exist_ok=True)
    (a.out / "answer_quality.json").write_text(json.dumps(results, indent=1, ensure_ascii=False), encoding="utf-8")
    lines = ["| Pack | Course type / subject prompt | Answerable n | Gold file retrieved | Correct / partly / wrong | "
             "Grounded (0-2) | Unanswerable handled |", "|---|---|---|---|---|---|---|"]
    lines += [table(r) for r in results]
    print("\n".join(lines))
    (a.out / "answer_quality_table.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
