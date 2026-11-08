"""Instructor AI tier 4: can the local model handle this course? Local vs cloud evaluation (guide 4.9; task
Z12).

Two background jobs with the instructor in between:
1. `ai_evaluation.generate`: the **local** model writes test questions from each module's course material
   (the material stays on the course's own server). The evaluation waits in `review`: the instructor reads,
   edits or removes the questions.
2. `ai_evaluation.run`, started only with the instructor's consent that course material and the questions go
   to the cloud model (refused in a `local_only` course): each question is answered with RAG by the local and
   by the cloud model, then the judge model scores both answers (blind, in random order). The report gives
   scores, wins, latency and tokens per module and per question type. The instructor can add spot checks.

Only generated questions and course material are used: no student data, no learner model (guide 4.9).
Models only through the model gateway (`services.gateway`).
"""
import json
import random
import re
import statistics

from sqlmodel import Session, select

from app.platform import jobs
from app.storage.models import AiEvaluation, Kc, Module, utcnow

QUESTION_TYPES = ("concept", "application", "logistics")
GENERATE = "ai_evaluation.generate"
RUN = "ai_evaluation.run"
MAX_PASSAGE_CHARS = 1200

GENERATE_SYSTEM = (
    "You write test questions for a course from its material. Write questions that a student of the course "
    "would ask, answerable from the passages. Reply with JSON only: "
    '{"questions": [{"question": "...", "type": "concept" | "application" | "logistics", '
    '"reference": "<a short correct answer from the passages>"}]}')
ANSWER_SYSTEM = ("You are a tutor for this course. Answer the student's question in at most 150 words, using "
                 "the course passages when they help. Say so when the passages do not answer it.")
JUDGE_SYSTEM = (
    "You score two answers to a course question, given the course passages and a reference answer. Score "
    "each from 1 (wrong or unhelpful) to 5 (correct, complete, uses the passages). Reply with JSON only: "
    '{"score_a": 1-5, "score_b": 1-5, "reason": "<one sentence>"}')


# ------------------------------------------------------------------------------------------- passages
def passages(services, course_id: int, module: Module, query: str, k: int = 4) -> list[str]:
    """Course material for the question: the course index (S4) when the course has one; for the demo course
    without one, the v1 retriever by topic (= the module code)."""
    retriever = getattr(services, "course_retriever", None)
    chunks = []
    if retriever is not None:
        try:
            chunks = retriever.retrieve(course_id, module.id, query, k)
        except Exception:  # noqa: BLE001 - no index yet: fall back below
            chunks = []
    if not chunks and course_id == services.content.course_id:
        chunks = services.retriever.retrieve(query, module.code, k=k)
    return [c.text[:MAX_PASSAGE_CHARS] for c in chunks]


def _context(texts: list[str]) -> str:
    return "Course passages:\n" + ("\n---\n".join(texts) if texts else "(none found)")


def _json(text: str) -> dict:
    m = re.search(r"\{.*\}", text or "", re.S)
    try:
        return json.loads(m.group(0)) if m else {}
    except ValueError:
        return {}


async def _ask(services, role: str, system: str, user: str, settings, trust: str):
    messages = [{"role": "system", "content": system}, {"role": "user", "content": user}]
    return await services.gateway.complete(role, messages, settings=settings, trust_required=trust)


def _save(engine, evaluation_id: int, **changes) -> None:
    with Session(engine) as db:
        row = db.get(AiEvaluation, evaluation_id)
        for name, value in changes.items():
            setattr(row, name, value)
        row.updated_at = utcnow()
        db.add(row)
        db.commit()


# ------------------------------------------------------------------------------------- 1. generate
@jobs.handler(GENERATE)
async def generate(services, job) -> None:
    with Session(services.engine) as db:
        evaluation = db.get(AiEvaluation, job.ref_id)
        options = dict(evaluation.options)
        q = select(Module).where(Module.course_id == evaluation.course_id)
        chosen = options.get("module_ids")
        modules = [m for m in db.exec(q.order_by(Module.position, Module.id)).all()
                   if not chosen or m.id in chosen]
        kc_names = {m.id: [k.name for k in db.exec(select(Kc).where(Kc.module_id == m.id,
                                                                     Kc.status == "active")).all()]
                    for m in modules}
    settings = services.effective(evaluation.course_id)
    per_module = options.get("questions_per_module", 5)
    types = options.get("question_types") or QUESTION_TYPES
    questions = []
    try:
        for i, module in enumerate(modules):
            query = " ".join([module.title, *kc_names[module.id][:6]])
            texts = passages(services, evaluation.course_id, module, query, k=6)
            if not texts:
                continue
            user = (f"{_context(texts)}\n\nModule: {module.title}\nWrite {per_module} questions; types to "
                    f"use: {', '.join(types)}.")
            result = await _ask(services, "local", GENERATE_SYSTEM, user, settings, "trusted_local")
            for item in (_json(result.text).get("questions") or [])[:per_module]:
                text = str(item.get("question", "")).strip()
                if text:
                    kind = item.get("type") if item.get("type") in types else types[0]
                    questions.append({"id": len(questions) + 1, "module_id": module.id,
                                      "module": module.title, "type": kind, "question": text[:500],
                                      "reference": str(item.get("reference", ""))[:800]})
            jobs.set_progress(services.engine, job.id, int(100 * (i + 1) / max(1, len(modules))))
    except Exception as e:
        _save(services.engine, job.ref_id, status="failed", error=jobs._message(e))
        raise
    status = "review" if questions else "failed"
    _save(services.engine, job.ref_id, questions=questions, status=status,
          error=None if questions else "no module has indexed material to write questions from")


# ------------------------------------------------------------------------------------------ 2. run
@jobs.handler(RUN)
async def run(services, job) -> None:
    with Session(services.engine) as db:
        evaluation = db.get(AiEvaluation, job.ref_id)
        modules = {m.id: m for m in db.exec(select(Module).where(Module.course_id == evaluation.course_id))}
    settings = services.effective(evaluation.course_id)
    rng = random.Random(evaluation.id)
    results = []
    try:
        for i, q in enumerate(evaluation.questions):
            module = modules.get(q["module_id"])
            texts = passages(services, evaluation.course_id, module, q["question"]) if module else []
            user = f"{_context(texts)}\n\nStudent question: {q['question']}"
            local = await _ask(services, "local", ANSWER_SYSTEM, user, settings, "trusted_local")
            cloud = await _ask(services, "cloud", ANSWER_SYSTEM, user, settings, "external_ok")
            order = ["local", "cloud"]
            rng.shuffle(order)
            answers = {"local": local, "cloud": cloud}
            verdict_prompt = (f"{user}\n\nReference answer: {q.get('reference') or '(none)'}\n\n"
                              f"Answer A:\n{answers[order[0]].text}\n\nAnswer B:\n{answers[order[1]].text}")
            verdict = await _ask(services, "judge", JUDGE_SYSTEM, verdict_prompt, settings, "external_ok")
            scores = _json(verdict.text)
            by_role = {order[0]: scores.get("score_a"), order[1]: scores.get("score_b")}
            results.append({
                "question_id": q["id"], "module": q["module"], "type": q["type"],
                "local": _answer(local, by_role["local"]), "cloud": _answer(cloud, by_role["cloud"]),
                "judge_model": verdict.model, "judge_reason": str(scores.get("reason", ""))[:300],
                "spot_check": None})
            jobs.set_progress(services.engine, job.id, int(100 * (i + 1) / max(1, len(evaluation.questions))))
    except Exception as e:
        _save(services.engine, job.ref_id, results=results, status="failed", error=jobs._message(e))
        raise
    _save(services.engine, job.ref_id, results=results, report=report(results), status="done")


def _answer(result, score) -> dict:
    valid = score if isinstance(score, int) and 1 <= score <= 5 else None
    return {"text": result.text[:2000], "model": result.model, "score": valid,
            "latency_ms": round(result.latency_ms), "prompt_tokens": result.prompt_tokens,
            "completion_tokens": result.completion_tokens}


# --------------------------------------------------------------------------------------------- report
def _group(rows: list[dict]) -> dict:
    def mean(values):
        values = [v for v in values if v is not None]
        return round(statistics.mean(values), 2) if values else None

    def median(values):
        values = [v for v in values if v is not None]
        return round(statistics.median(values)) if values else None

    local = [r["local"]["score"] for r in rows]
    cloud = [r["cloud"]["score"] for r in rows]
    pairs = [(a, b) for a, b in zip(local, cloud, strict=True) if a is not None and b is not None]
    return {
        "questions": len(rows),
        "local_score": mean(local), "cloud_score": mean(cloud),
        "local_better": sum(1 for a, b in pairs if a > b), "cloud_better": sum(1 for a, b in pairs if b > a),
        "ties": sum(1 for a, b in pairs if a == b), "unscored": len(rows) - len(pairs),
        "local_latency_ms": median(r["local"]["latency_ms"] for r in rows),
        "cloud_latency_ms": median(r["cloud"]["latency_ms"] for r in rows),
        "local_tokens": sum((r["local"]["prompt_tokens"] or 0) + (r["local"]["completion_tokens"] or 0)
                            for r in rows),
        "cloud_tokens": sum((r["cloud"]["prompt_tokens"] or 0) + (r["cloud"]["completion_tokens"] or 0)
                            for r in rows),
    }


def report(results: list[dict]) -> dict:
    """Totals, per module and per question type; spot checks counted when the instructor added them."""
    by_module: dict[str, list] = {}
    by_type: dict[str, list] = {}
    for r in results:
        by_module.setdefault(r["module"], []).append(r)
        by_type.setdefault(r["type"], []).append(r)
    checks = [r["spot_check"] for r in results if r.get("spot_check")]
    agree = sum(1 for r in results if r.get("spot_check") and r["spot_check"].get("agrees_with_judge"))
    return {"overall": _group(results),
            "by_module": {k: _group(v) for k, v in by_module.items()},
            "by_type": {k: _group(v) for k, v in by_type.items()},
            "spot_checks": len(checks), "spot_checks_agreeing": agree}
