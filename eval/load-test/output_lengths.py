"""Output lengths of the local model per call kind, cut-offs and slot time (2048-token limit research).

Measurement only: it calls the lab vLLM, so it is never part of CI or the unit tests (nothing imports it).
It uses the app's own prompts and request builders (imported from `backend/app`), the open course packs
(`python scripts/fetch_open_courses.py unpack` first; `instructor_only/` is never read) and the passages of
`eval/v16-drafts/results/inputs.json`. Only counts are written to `eval/load-test/results/`: completion and
prompt tokens, finish reasons, durations, a loop flag. The model's text goes only to `--raw-dir` (keep it
outside the repository, for example `var/token-research`). The server address and key are read from the env
file (VLLM_BASE_URL, VLLM_KEY, and for the cloud phase CLOUD_*) and are never printed or written.

Phases (one per run):
  answers     student answers: the generate step's prompt (`render_local`, k=4 passages of the pack's course
              index) for S11 and paraphrase questions; `--detailed N` adds N questions asked for a long
              answer with a table (a stress case, reported apart)
  understand  the understand step on the same questions (max_tokens 200, schema of the topic's KCs)
  drafts      tier 2 structure drafts (kcs, check_items, misconceptions) with the app's request, schema and
              limit (`STRUCTURE_MAX_TOKENS`)
  quiz        quiz drafts as `quiz_drafts.draft` sends them (no schema, the connection's limit)
  slots       time per call and tokens/s at 1, 8 and 16 at the same time for answers of a given length
  cloud       the hosted model with FICTIONAL prompts only: completion and hidden reasoning tokens
  summary     the tables from the results files

    python eval/load-test/output_lengths.py answers --env-file ../.env --raw-dir ../var/token-research
    python eval/load-test/output_lengths.py summary
`--rerun-cut` repeats every call that was cut at the limit with a larger limit (4096), to tell a loop from a
long text.
"""

import argparse
import asyncio
import hashlib
import importlib.util
import json
import statistics
import sys
import tempfile
import time
import zlib
from pathlib import Path
from types import SimpleNamespace

ROOT = Path(__file__).resolve().parents[2]
HERE = Path(__file__).resolve().parent
RESULTS = HERE / "results"
sys.path.insert(0, str(ROOT / "backend"))

_spec = importlib.util.spec_from_file_location("course_rag_packs_run", ROOT / "eval/course-rag-packs/run.py")
rag = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(rag)

ALL_PACKS = (
    "harvard_cs50x",
    "mit_6_002_circuits",
    "mit_6_006_algorithms",
    "mit_7_016_intro_biology",
    "mit_7_03_genetics",
    "mit_hst035_pathology",
    "mit_hst151_pharmacology",
    "mit_res_6_007_signals",
)
PARAPHRASE_PACKS = ("harvard_cs50x", "mit_6_002_circuits")
DETAILED_SUFFIX = " Explain it in detail with a worked example and a comparison table."
RERUN_LIMIT = 4096
INPUTS = ROOT / "eval/v16-drafts/results/inputs.json"
STRUCTURE_KINDS = ("kcs", "check_items", "misconceptions")


# ------------------------------------------------------------------------------------------- helpers
def load_settings(env_file: Path):
    from app.core.config import Settings

    return Settings(_env_file=env_file)


def local_client(settings, max_tokens: int | None = None, timeout_s: float = 300):
    """The app's local client (thinking off, schema output, the configured temperature and limit)."""
    from app.llm import factory

    loc = settings.llm.local
    client = factory.build_local_client(
        settings,
        loc.model,
        temperature=loc.temperature,
        timeout_s=timeout_s,
        max_tokens=max_tokens or loc.max_tokens,
    )
    if isinstance(client, factory.NoLocalServer):
        raise SystemExit("VLLM_BASE_URL is not set in the env file")
    return client


def tail_loop(text: str) -> dict:
    """Is the end of a text a repetition? Counts only: the compression ratio of the last 1500 characters, the
    share of distinct words among the last 150 words, and the share of white space in the last 600."""
    tail = text[-1500:]
    if not tail:
        return {"loop": False}
    ratio = len(zlib.compress(tail.encode("utf-8"))) / max(1, len(tail.encode("utf-8")))
    words = text.split()[-150:]
    distinct = len(set(words)) / len(words) if words else 1.0
    last = text[-600:]
    blank = sum(c.isspace() for c in last) / max(1, len(last))
    return {
        "compress": round(ratio, 3),
        "distinct_words": round(distinct, 3),
        "blank": round(blank, 3),
        "loop": ratio < 0.12 or (len(words) >= 50 and distinct < 0.25) or blank > 0.6,
    }


async def timed(client, messages, *, json_schema=None, max_tokens=None) -> dict:
    """One call: counts, finish reason (cut_off) and duration; the text under `_text` (not in results)."""
    from app.llm.base import LLMError

    t0 = time.perf_counter()
    try:
        r = await client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)
    except LLMError as e:  # includes "cut off before any text"
        cut = "cut off" in str(e)
        return {
            "ok": False,
            "error": type(e).__name__,
            "seconds": round(time.perf_counter() - t0, 1),
            "cut_off": cut,
            # the limit was spent only when the answer was cut off; a timeout or refused call has no usage
            "completion_tokens": (max_tokens or client.max_tokens) if cut else None,
            "_text": "",
        }
    return {
        "ok": True,
        "completion_tokens": r.completion_tokens,
        "prompt_tokens": r.prompt_tokens,
        "cut_off": r.cut_off,
        "seconds": round(time.perf_counter() - t0, 1),
        "_text": r.text,
    }


class Out:
    """Writes the counts to results/ (no text) and the texts to the raw directory (not in the repository)."""

    def __init__(self, phase: str, raw_dir: Path | None, append: bool = False) -> None:
        RESULTS.mkdir(exist_ok=True)
        self.path = RESULTS / f"token_research_{phase}.jsonl"
        if not append:
            self.path.write_text("", encoding="utf-8")
        self.raw = None
        if raw_dir:
            raw_dir.mkdir(parents=True, exist_ok=True)
            self.raw = raw_dir / f"{phase}.jsonl"
            if not append:
                self.raw.write_text("", encoding="utf-8")

    def add(self, row: dict) -> None:
        text = row.pop("_text", "")
        if text:
            row.update(tail_loop(text))
        with self.path.open("a", encoding="utf-8") as f:
            f.write(json.dumps(row) + "\n")
        if self.raw is not None and text:
            with self.raw.open("a", encoding="utf-8") as f:
                f.write(json.dumps({"id": row.get("id"), "text": text}, ensure_ascii=False) + "\n")


async def with_rerun(client, messages, row: dict, rerun: bool, **kw) -> dict:
    """Repeat a call that was cut off with RERUN_LIMIT and note how it ended."""
    if rerun and row.get("cut_off"):
        again = await timed(client, messages, max_tokens=RERUN_LIMIT, **kw)
        row.update(
            rerun_tokens=again["completion_tokens"],
            rerun_cut=again["cut_off"],
            rerun_loop=tail_loop(again["_text"])["loop"] if again["_text"] else None,
        )
    return row


# ------------------------------------------------------------------------------------- the questions
def pick(rows: list[dict], n: int) -> list[dict]:
    """Up to n questions: one without an answer in the material, then the types in turn."""
    out = [r for r in rows if not r["gold"]][:1]
    by_type = {t: [r for r in rows if r["gold"] and r["type"] == t] for t in rag.TYPES}
    while len(out) < n and any(by_type.values()):
        for t in rag.TYPES:
            if by_type[t] and len(out) < n:
                out.append(by_type[t].pop(0))
    return out


def build_prompts(
    packs, per_pack: int, para_per_pack: int, twins_per_pack: int, cache_dir=None
) -> list[dict]:
    """The generate step's messages for the sampled questions of each pack, built with the app's code.
    `twins_per_pack` S11 concept or application questions are also asked for a long answer with a table.
    Indexing the packs is slow, so the prompts are kept in `cache_dir` (the raw directory: course text)."""
    selection = hashlib.sha256("|".join(packs).encode()).hexdigest()[:12]  # full pack names: no collisions
    key = f"prompts_{selection}_{per_pack}_{para_per_pack}_{twins_per_pack}.json"
    cached = cache_dir / key if cache_dir else None
    if cached and cached.exists():
        return json.loads(cached.read_text(encoding="utf-8"))
    from app.core.schemas import AskRequest, Chunk, RequestContext
    from app.privacy.profiles import privacy_profile
    from app.prompts import render_local

    items = []
    for pack in packs:
        pack_dir = rag.PACKS_DIR / pack
        manifest = json.loads((pack_dir / "manifest.json").read_text(encoding="utf-8"))
        profile = privacy_profile(manifest["course_type"])
        questions = [("s11", r) for r in pick(rag.load_questions(pack), per_pack)]
        if pack in PARAPHRASE_PACKS and para_per_pack:
            questions += [
                ("paraphrase", r)
                for r in pick(rag.load_questions(pack, "paraphrase_questions"), para_per_pack)
            ]
        twins = 0
        with tempfile.TemporaryDirectory(prefix="token-research-") as tmp:
            retriever, _, _ = rag.build_index(pack_dir, manifest, Path(tmp))
            modules = [{"id": f"M{m['module_order']}", "name": m["title"]} for m in manifest["modules"]]
            for qset, row in questions:
                kind = "logistics" if row["type"] == "logistics" else "concept"
                hits = retriever.retrieve(
                    rag.COURSE_ID, row["module_order"], row["question"], k=4, question_kind=kind
                )
                variants = [("", row["question"])]
                if qset == "s11" and row["gold"] and row["type"] != "logistics" and twins < twins_per_pack:
                    variants.append(("d", row["question"] + DETAILED_SUFFIX))
                    twins += 1
                for tag, text in variants:
                    chunks = [Chunk(text=h.text, source=h.source, topic=pack, score=h.score) for h in hits]
                    ctx = RequestContext(
                        request_id="research",
                        request=AskRequest(student_id="research", topic=pack, question=text),
                        passages=chunks,
                        profile=profile,
                    )
                    items.append(
                        {
                            "id": f"{row['id']}{'-d' if tag else ''}",
                            "pack": pack,
                            "set": qset,
                            "type": row["type"],
                            "detailed": bool(tag),
                            "question": text,
                            "messages": render_local(ctx),
                            "modules": modules,
                            "covered": bool(row["gold"]),
                        }
                    )
    if cached:
        cached.parent.mkdir(parents=True, exist_ok=True)
        cached.write_text(json.dumps(items, ensure_ascii=False), encoding="utf-8")
    return items


# ------------------------------------------------------------------------------------------- phases
async def phase_answers(a, settings) -> None:
    client = local_client(settings)
    items = build_prompts(a.packs, a.per_pack, a.paraphrase_per_pack, a.twins, a.raw_dir)
    twins = [it for it in items if it["detailed"]]  # repeated: the long answers are the ones near the limit
    items += [{**it, "id": f"{it['id']}-r{n}"} for n in range(2, a.twin_reps + 1) for it in twins]
    if a.append:  # more runs of the long-answer questions only, added to the results already written
        items = [
            it for it in items if it["detailed"] and it["id"].endswith(tuple(f"-r{n}" for n in range(2, 99)))
        ]
    out, slots = Out("answers", a.raw_dir, a.append), asyncio.Semaphore(a.parallel)

    async def one(it):
        async with slots:
            row = await timed(client, it["messages"])
            row = await with_rerun(client, it["messages"], row, a.rerun_cut)
        out.add(
            {
                "id": it["id"],
                "pack": it["pack"],
                "set": it["set"],
                "type": it["type"],
                "detailed": it["detailed"],
                "covered": it["covered"],
                **row,
            }
        )
        print(it["id"], row["completion_tokens"], "CUT" if row["cut_off"] else "", flush=True)

    await asyncio.gather(*(one(it) for it in items))


async def phase_understand(a, settings) -> None:
    from app.learner import understand

    client = local_client(settings, max_tokens=200)
    items = build_prompts(a.packs, a.per_pack, a.paraphrase_per_pack, 0, a.raw_dir)
    out, slots = Out("understand", a.raw_dir), asyncio.Semaphore(a.parallel)

    class Store:  # the shape of ContentStore that `understand.messages` and `schema` read
        def __init__(self, modules):
            self._kcs = [SimpleNamespace(id=m["id"], name=m["name"], definition="") for m in modules]

        def kcs(self, topic):
            return self._kcs

        def misconceptions(self, kc_id):
            return []

    async def one(it):
        store = Store(it["modules"])
        msgs = understand.messages(store, it["pack"], it["question"])
        schema = understand.schema(store, it["pack"])
        async with slots:
            row = await timed(client, msgs, json_schema=schema, max_tokens=200)
            row = await with_rerun(client, msgs, row, a.rerun_cut, json_schema=schema)
        out.add({"id": it["id"], "pack": it["pack"], "kcs": len(it["modules"]), **row})

    await asyncio.gather(*(one(it) for it in items))


class Recorder:
    """Wraps the client of a draft: keeps the counts and the finish reason of the draft's model call."""

    def __init__(self, client, slots) -> None:
        self.client, self.slots, self.calls = client, slots, []

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        async with self.slots:
            r = await self.client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)
        self.calls.append(
            {
                "completion_tokens": r.completion_tokens,
                "prompt_tokens": r.prompt_tokens,
                "cut_off": r.cut_off,
                "seconds": round(r.latency_ms / 1000, 1),
                "_text": r.text,
                "limit": max_tokens or self.client.max_tokens,
            }
        )
        return r


async def phase_drafts(a, settings) -> None:
    from app.core.schemas import Chunk
    from app.instructor_ai import structure_drafts
    from app.llm.gateway import FakeGateway

    cases = [c for c in json.loads(INPUTS.read_text(encoding="utf-8"))["cases"] if c["id"] in a.cases]
    client = local_client(settings)
    out, slots = Out("drafts", a.raw_dir), asyncio.Semaphore(a.parallel)

    async def one(case, kind, rep):
        rec = Recorder(client, slots)
        gateway = FakeGateway({"local": rec}, trusted=frozenset({"local"}))
        passages = case["passages"][kind]
        chunks = [
            Chunk(text=p["text"], source=p["source"], topic=case["id"], score=0.0, metadata={"course_id": 1})
            for p in passages
        ]
        names = [k["name"] for k in case["existing_kcs"]]
        ok, error = True, None
        try:
            await structure_drafts.generate_structure_draft(
                course_id=1,
                kind=kind,
                passages=chunks,
                gateway=gateway,
                settings=SimpleNamespace(local_only=False),
                known_kc_names=names,
            )
        except Exception as e:  # noqa: BLE001 - recorded
            ok, error = False, type(e).__name__
        for call in rec.calls:
            row = {
                "id": f"{case['id']}-{kind}-{rep}",
                "pack": case["pack"],
                "kind": kind,
                "valid": ok,
                "error": error,
                "limit": call.pop("limit"),
                **call,
            }
            if a.rerun_cut and row["cut_off"]:  # the same request with a larger limit
                msgs = structure_drafts.structure_messages(
                    kind,
                    [{"number": i, "source": c.source, "text": c.text} for i, c in enumerate(chunks, 1)],
                    names,
                )
                again = await timed(
                    client,
                    msgs,
                    json_schema=structure_drafts.response_schema(kind, names),
                    max_tokens=RERUN_LIMIT,
                )
                row.update(rerun_tokens=again["completion_tokens"], rerun_cut=again["cut_off"])
            out.add(row)
            print(row["id"], row["completion_tokens"], "CUT" if row["cut_off"] else "", flush=True)

    await asyncio.gather(*(one(c, k, r) for c in cases for k in STRUCTURE_KINDS for r in range(a.reps)))


async def phase_quiz(a, settings) -> None:
    from app.instructor_ai import quiz_drafts

    cases = [c for c in json.loads(INPUTS.read_text(encoding="utf-8"))["cases"] if c["id"] in a.cases]
    client = local_client(settings)
    out, slots = Out("quiz", a.raw_dir), asyncio.Semaphore(a.parallel)

    async def one(case, wanted, rep):
        passages = case["passages"]["quiz"]
        codes = {f"{case['id']}-kc{i}": k["name"] for i, k in enumerate(case["existing_kcs"], 1)}
        evidence = [
            {"number": n, "source": p["source"], "text": p["text"][:1200]} for n, p in enumerate(passages, 1)
        ]
        request = {
            "module": case["module_title"],
            "questions_wanted": wanted,
            "kinds": ["mcq", "true_false"],
            "kc_codes": codes,
            "passages": evidence,
        }
        msgs = [
            {"role": "system", "content": quiz_drafts.SYSTEM},
            {"role": "user", "content": json.dumps(request, ensure_ascii=False)},
        ]
        async with slots:
            row = await timed(client, msgs)  # as quiz_drafts.draft: no schema, the connection's limit
            row = await with_rerun(client, msgs, row, a.rerun_cut)
        usable = (
            len(
                quiz_drafts.parse_questions(
                    row["_text"], [p["source"] for p in passages], set(codes), {"mcq", "true_false"}
                )
            )
            if row["_text"]
            else 0
        )
        out.add(
            {
                "id": f"{case['id']}-q{wanted}-{rep}",
                "pack": case["pack"],
                "wanted": wanted,
                "usable": usable,
                **row,
            }
        )
        print(case["id"], wanted, row["completion_tokens"], "CUT" if row["cut_off"] else "", flush=True)

    jobs = [one(c, 5, r) for c in cases for r in range(a.reps)] + [
        one(c, 12, r) for c in cases for r in range(2)
    ]
    await asyncio.gather(*jobs)


async def phase_slots(a, settings) -> None:
    """Time per call at 1, 8 and 16 at the same time, for answers forced to a given length (min_tokens =
    max_tokens), with the real answer prompt of a different question for every request."""
    import httpx

    sys.path.insert(0, str(HERE))
    import capacity  # read_env, auth

    env = capacity.read_env(a.env_file)
    url, key = env["VLLM_BASE_URL"].rstrip("/"), env.get("VLLM_KEY", "")
    url = url if url.endswith("/v1") else url + "/v1"
    items = build_prompts(a.packs, a.per_pack, a.paraphrase_per_pack, 0, a.raw_dir)
    out = Out("slots", None)
    model = settings.llm.local.model
    lengths = [int(x) for x in a.lengths.split(",")]

    async def one(client, it, length):
        body = {
            "model": model,
            "stream": True,
            "max_tokens": length,
            "min_tokens": length,
            "temperature": 0.2,
            "stream_options": {"include_usage": True},
            "chat_template_kwargs": {"enable_thinking": False},
            "messages": it["messages"],
        }
        t0, first, tokens = time.perf_counter(), None, None
        try:
            async with client.stream(
                "POST", url + "/chat/completions", json=body, timeout=900, headers=capacity.auth(key)
            ) as r:
                if r.status_code != 200:
                    return {"ok": False, "error": f"HTTP {r.status_code}"}
                async for line in r.aiter_lines():
                    if not line.startswith("data:") or line.strip() == "data: [DONE]":
                        continue
                    d = json.loads(line[5:])
                    if d.get("usage"):
                        tokens = d["usage"].get("completion_tokens")
                    ch = d.get("choices") or []
                    if ch and ch[0].get("delta", {}).get("content") and first is None:
                        first = time.perf_counter() - t0
        except Exception as e:  # noqa: BLE001 - counted
            return {"ok": False, "error": type(e).__name__}
        total = time.perf_counter() - t0
        return {"ok": True, "total": total, "first": first or 0.0, "tokens": tokens or length}

    async with httpx.AsyncClient(limits=httpx.Limits(max_connections=40)) as client:
        await one(client, items[0], 16)  # warm-up
        n_item = 0
        for length in lengths:
            for level, rounds in ((1, a.rounds_1), (8, a.rounds), (16, a.rounds)):
                results, t0 = [], time.perf_counter()
                for _ in range(rounds):
                    wave = [items[(n_item + i) % len(items)] for i in range(level)]
                    n_item += level
                    results += await asyncio.gather(*(one(client, it, length) for it in wave))
                wall = time.perf_counter() - t0
                ok = [r for r in results if r["ok"]]
                row = {
                    "length": length,
                    "concurrent": level,
                    "sent": len(results),
                    "ok": len(ok),
                    "wall_s": round(wall, 1),
                }
                if ok:
                    gen = [max(r["total"] - r["first"], 1e-6) for r in ok]
                    row.update(
                        call_p50_s=round(statistics.median(r["total"] for r in ok), 1),
                        call_max_s=round(max(r["total"] for r in ok), 1),
                        first_p50_s=round(statistics.median(r["first"] for r in ok), 1),
                        tps_per_call=round(
                            statistics.mean(r["tokens"] / g for r, g in zip(ok, gen, strict=True)), 1
                        ),
                        total_tps=round(sum(r["tokens"] for r in ok) / wall, 1),
                    )
                out.add(row)
                print(row, flush=True)


CLOUD_QUESTIONS = [  # fictional topic only: nothing from the course packs
    "What is the difference between a gleebo and a frindle in the Zorbian number system?",
    "Why does the fictional Quillon engine overheat when the flux valve is closed?",
    "Explain how the Marrow algorithm sorts a list of 7 fictional tokens.",
    "Compare the Vexel method and the Plomb method for balancing a fictional ledger. Use a table.",
    "What happens to a Tarn crystal when it is heated above 40 degrees in the fictional Brannic lab?",
    "Describe the three phases of the Oxbow protocol in the fictional course ZZ 101.",
    "Give a worked example of converting 13 snibs to drubs when 1 snib is 2.5 drubs.",
    "Why is the Fenwick lattice rule needed in the fictional theory of tidal clocks?",
]
CLOUD_MATERIAL = [
    (
        "Course ZZ 101 (fictional) introduces the Zorbian number system, which counts in gleebos "
        "(units of 5) and frindles (units of 7). The Quillon engine is a fictional device with a flux "
        "valve that must stay open."
    ),
    (
        "The Marrow algorithm (fictional) repeatedly swaps the two tokens that are farthest out of order. "
        "The Oxbow protocol has three phases: offer, hold and release. 1 snib is 2.5 drubs."
    ),
]


async def phase_cloud(a, settings) -> None:
    """Hidden reasoning of the hosted model against `llm.cloud.max_tokens`. Fictional prompts only."""
    import openai

    from app.prompts import system_prompt
    from app.prompts.render import material_block

    if not settings.cloud_enabled:
        raise SystemExit("CLOUD_API_KEY / CLOUD_MODEL are not set")
    client = openai.AsyncOpenAI(
        base_url=settings.cloud_base_url,
        api_key=settings.cloud_api_key.get_secret_value(),
        timeout=settings.llm.cloud.timeout_s * 4,
        max_retries=1,
    )
    out, slots = Out("cloud", None), asyncio.Semaphore(3)
    system = system_prompt(subject="general")

    async def one(i, question, limit):
        user = f"Topic: Fictional course\n\n{material_block(CLOUD_MATERIAL)}\n\nStudent question: {question}"
        async with slots:
            t0 = time.perf_counter()
            try:
                r = await client.chat.completions.create(
                    model=settings.cloud_model,
                    temperature=0.2,
                    max_tokens=limit,
                    messages=[{"role": "system", "content": system}, {"role": "user", "content": user}],
                )
            except openai.APIError as e:
                out.add({"id": f"c{i}", "limit": limit, "ok": False, "error": type(e).__name__})
                return
        u = r.usage
        details = getattr(u, "completion_tokens_details", None)
        reasoning = getattr(details, "reasoning_tokens", None) if details else None
        text = r.choices[0].message.content or ""
        out.add(
            {
                "id": f"c{i}",
                "limit": limit,
                "ok": True,
                "completion_tokens": u.completion_tokens,
                "reasoning_tokens": reasoning,
                "finish": r.choices[0].finish_reason,
                "visible_chars": len(text),
                "seconds": round(time.perf_counter() - t0, 1),
            }
        )

    await asyncio.gather(
        *(
            one(i, q, lim)
            for lim in (settings.llm.cloud.max_tokens, a.cloud_small_limit)
            for i, q in enumerate(CLOUD_QUESTIONS)
        )
    )


# ------------------------------------------------------------------------------------------ summary
def load(phase: str) -> list[dict]:
    path = RESULTS / f"token_research_{phase}.jsonl"
    return (
        [json.loads(x) for x in path.read_text(encoding="utf-8").splitlines() if x.strip()]
        if path.exists()
        else []
    )


def pct(values, p):
    v = sorted(values)
    return v[min(len(v) - 1, round(p * (len(v) - 1)))] if v else None


def stats_row(name: str, rows: list[dict], limit: int, big: int | None = None) -> str:
    """Lengths of the measured calls only: an answer, or a cut-off at the limit; failed calls are counted
    apart (a timeout or refused call has no completion length)."""
    failed = [r for r in rows if r.get("ok") is False and not r.get("cut_off")]
    rows = [r for r in rows if r not in failed]
    if failed:
        name = f"{name} ({len(failed)} failed, not counted)"
    tokens = [r["completion_tokens"] for r in rows if r.get("completion_tokens") is not None]
    cut = [r for r in rows if r.get("cut_off")]
    loops = sum(1 for r in cut if r.get("loop"))
    over = f"{sum(t > big for t in tokens)} / {len(tokens)}" if big else "-"
    return (
        f"| {name} | {len(rows)} | {statistics.median(tokens):.0f} | {pct(tokens, 0.95)} | {max(tokens)} | "
        f"{limit} | {len(cut)} / {len(rows)} | {loops} | {over} |"
    )


def summary() -> str:
    lines = [
        "| Kind | Calls | Median | p95 | Max | Limit | Cut at limit | Cut and looping | Over 1024 |",
        "|---|---|---|---|---|---|---|---|---|",
    ]
    answers = load("answers")
    if answers:
        plain = [r for r in answers if not r["detailed"]]
        lines.append(stats_row("answers, S11", [r for r in plain if r["set"] == "s11"], 2048, 1024))
        lines.append(
            stats_row("answers, paraphrase", [r for r in plain if r["set"] == "paraphrase"], 2048, 1024)
        )
        lines.append(stats_row("answers, all plain", plain, 2048, 1024))
        lines.append(
            stats_row(
                "answers, asked for detail and a table", [r for r in answers if r["detailed"]], 2048, 1024
            )
        )
    if load("understand"):
        lines.append(stats_row("understand", load("understand"), 200))
    for kind in STRUCTURE_KINDS:
        rows = [r for r in load("drafts") if r["kind"] == kind]
        if rows:
            lines.append(stats_row(f"draft: {kind}", rows, 4096, 2048))
    quiz = load("quiz")
    for wanted in (5, 12):
        rows = [r for r in quiz if r["wanted"] == wanted]
        if rows:
            lines.append(stats_row(f"quiz draft, {wanted} questions", rows, 2048, 1024))
    out = ["The last column counts calls above 1024 tokens (for the tier 2 drafts: above 2048).", "", *lines]
    cuts = [r for p in ("answers", "understand", "drafts", "quiz") for r in load(p) if r.get("cut_off")]
    if cuts:
        out += [
            "",
            "Cut-offs and the same request with a limit of 4096:",
            "",
            "| Call | Tokens | Loop flag | At 4096: tokens | At 4096: still cut |",
            "|---|---|---|---|---|",
        ]
        out += [
            f"| {r['id']} | {r['completion_tokens']} | {r.get('loop')} | {r.get('rerun_tokens', '-')} | "
            f"{r.get('rerun_cut', '-')} |"
            for r in cuts
        ]
    slots = load("slots")
    if slots:
        out += [
            "",
            (
                "| Length | At once | OK / sent | Call p50 (s) | Slowest (s) | First token p50 (s) | "
                "Tokens/s per call | Total tokens/s |"
            ),
            "|---|---|---|---|---|---|---|---|",
        ]
        out += [
            f"| {r['length']} | {r['concurrent']} | {r['ok']} / {r['sent']} | {r.get('call_p50_s', '-')} | "
            f"{r.get('call_max_s', '-')} | {r.get('first_p50_s', '-')} | {r.get('tps_per_call', '-')} | "
            f"{r.get('total_tps', '-')} |"
            for r in slots
        ]
    cloud = load("cloud")
    if cloud:
        out += [
            "",
            "| Limit | Calls | Finish: length | Completion median | Reasoning median | Reasoning max |",
            "|---|---|---|---|---|---|",
        ]
        for limit in sorted({r["limit"] for r in cloud}):
            rows = [r for r in cloud if r["limit"] == limit and r["ok"]]
            if rows:
                reasoning = [r["reasoning_tokens"] or 0 for r in rows]
                out.append(
                    f"| {limit} | {len(rows)} | {sum(r['finish'] == 'length' for r in rows)} | "
                    f"{statistics.median(r['completion_tokens'] for r in rows):.0f} | "
                    f"{statistics.median(reasoning):.0f} | {max(reasoning)} |"
                )
    return "\n".join(out)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("phase", choices=["answers", "understand", "drafts", "quiz", "slots", "cloud", "summary"])
    ap.add_argument("--env-file", type=Path, default=ROOT / ".env")
    ap.add_argument(
        "--raw-dir", type=Path, default=None, help="where the model's text goes (outside the repo)"
    )
    ap.add_argument("--packs", type=lambda s: s.split(","), default=list(ALL_PACKS))
    ap.add_argument("--per-pack", type=int, default=6, help="S11 questions per pack")
    ap.add_argument("--paraphrase-per-pack", type=int, default=8)
    ap.add_argument(
        "--twins",
        type=int,
        default=2,
        help="answers: S11 questions per pack asked again for a long answer with a table",
    )
    ap.add_argument("--twin-reps", type=int, default=1, help="answers: runs of every long-answer question")
    ap.add_argument(
        "--append", action="store_true", help="answers: only the extra runs of --twin-reps, appended"
    )
    ap.add_argument("--cases", type=lambda s: s.split(","), default=["cs50_w4", "e6002_l2", "hst151_l1"])
    ap.add_argument("--reps", type=int, default=5, help="drafts and quiz: runs per case and kind")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--rerun-cut", action="store_true")
    ap.add_argument("--lengths", default="500,1000,2048", help="slots: forced output lengths")
    ap.add_argument("--rounds", type=int, default=2, help="slots: waves at 8 and 16 at once")
    ap.add_argument("--rounds-1", type=int, default=3, help="slots: calls one after the other at 1")
    ap.add_argument("--cloud-small-limit", type=int, default=600)
    a = ap.parse_args()
    if a.phase == "summary":
        text = summary()
        (RESULTS / "token_research_tables.md").write_text(text + "\n", encoding="utf-8")
        print(text)
        return
    settings = load_settings(a.env_file)
    asyncio.run(
        {
            "answers": phase_answers,
            "understand": phase_understand,
            "drafts": phase_drafts,
            "quiz": phase_quiz,
            "slots": phase_slots,
            "cloud": phase_cloud,
        }[a.phase](a, settings)
    )


if __name__ == "__main__":
    main()
