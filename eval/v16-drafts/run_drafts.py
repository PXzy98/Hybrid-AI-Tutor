"""V16: draft the same inputs with one version of the instructor AI code, in-process, with the real local
model.

`--backend` is the `backend/` folder of the version to measure (main, or a detached worktree at the commit
before #119); its own `app` package is imported, so the draft cores, prompts, validators and the check of the
KC references are that version's. The script calls what the draft job `ai_draft.generate` calls for the
default scope (no focus, no request, no chosen sources):

- `drafts.generate_tier1_draft` (project_ideas, sample_proposal, faq) and
  `structure_drafts.generate_structure_draft` (kcs, check_items, misconceptions, with the case's existing KC
  names as the course's accepted KCs), then `draft_jobs.parse_content` on the stored content (the validator of
  an edited draft before it is accepted);
- for quiz questions, the request and the parse of `quiz_drafts.draft` for one module (5 questions, multiple
  choice and true/false, the module's KC codes), with that version's `SYSTEM` and `parse_questions`.

The gateway is `app.llm.gateway.FakeGateway` (the same trust rule as the app's gateway, without the database
of model connections) around the app's own vLLM client (`factory.build_local_client`: thinking off, answers
constrained to the JSON schema, temperature 0.2). Its timeout is raised to 180 s because the lab server is
shared; at most 4 requests run at a time.

`--cloud` (main only) instead drafts a short fictional module (written for this test, `FICTIONAL` below) with
both the local and the cloud model; the cloud drafts go through the app's cloud gate (the job's
`_check_cloud_text` privacy scan, then `build_draft_cloud_request` and `CloudClient.complete_draft`). Real
course pack text is never sent to the cloud model.

Usage (repository root):
    python eval/v16-drafts/run_drafts.py --backend backend --label after
    python eval/v16-drafts/run_drafts.py --backend <before-worktree>/backend --label before
    python eval/v16-drafts/run_drafts.py --backend backend --label cloud --cloud
Options: --env-file PATH (default: <repository>/.env), --cases a,b, --kinds a,b.
Writes results/drafts_<label>.jsonl (one line per draft, raw model answer included).
"""
import argparse
import asyncio
import json
import subprocess
import sys
import time
from pathlib import Path
from types import SimpleNamespace

HERE = Path(__file__).resolve().parent
ROOT = HERE.parents[1]
KINDS = ("kcs", "check_items", "misconceptions", "project_ideas", "sample_proposal", "faq", "quiz")
CLOUD_KINDS = KINDS[:-1]  # quiz drafts have no cloud option
COURSE_ID = 1
PARALLEL = 4  # the lab vLLM is shared

# Fictional material for the cloud comparison only (no real course, person or institution).
FICTIONAL = {
    "id": "fictional_tidewater", "pack": "fictional", "course_type": "ece",
    "module_title": "Module 3: Feedback control of the Marlin rover",
    "existing_kcs": [
        {"name": "Open-loop control",
         "definition": "Control that sets the input without measuring the output."},
        {"name": "Proportional control", "definition": "A controller whose output is the gain Kp times the "
                                                       "error between the setpoint and the measurement."},
    ],
    "passages": [
        {"source": "module3_notes.md", "text": (
            "Module 3 of ROB 210 at the fictional Tidewater Institute uses the Marlin, a small four-wheeled "
            "teaching rover, to introduce feedback control. In open-loop control the rover is told to drive "
            "its "
            "motors at 60 percent power for two seconds and hopes to travel one metre; any change in battery "
            "voltage, floor friction or load changes the distance. In closed-loop control a wheel encoder "
            "measures the distance travelled and the controller corrects the motor command while the rover "
            "moves. The difference between the setpoint (the distance we want) and the measured value is "
            "called the error, e(t).")},
        {"source": "module3_notes.md", "text": (
            "A proportional controller sets the motor command to u(t) = Kp * e(t). A larger gain Kp makes "
            "the "
            "rover approach the target faster, but on the Marlin a gain above about 8 makes it overshoot the "
            "target and oscillate. With proportional control alone the rover often stops a few centimetres "
            "short of the target, because near the target the command becomes too small to overcome static "
            "friction. This remaining error is called the steady-state error.")},
        {"source": "module3_notes.md", "text": (
            "An integral term adds Ki times the accumulated error, so a small error that lasts a long time "
            "still builds up a command; it removes the steady-state error but can cause overshoot and "
            "'integral windup' when the motor is saturated at full power. A derivative term adds Kd times "
            "the "
            "rate of change of the error; it damps the motion and reduces overshoot, but it amplifies the "
            "noise of the encoder signal. Together these form the PID controller: "
            "u(t) = Kp e(t) + Ki * integral of e + Kd de/dt.")},
        {"source": "module3_lab.md", "text": (
            "Lab 3 (fictional course ROB 210): tune a PID controller so the Marlin drives exactly one metre. "
            "Start with Ki = Kd = 0 and raise Kp until the rover oscillates, then halve it. Add Ki in small "
            "steps until the steady-state error disappears, and add Kd if the overshoot is more than 5 cm. "
            "Record the overshoot, the settling time and the final error for each setting in the lab "
            "notebook. The lab report has three parts: the tuning table, a plot of distance against time for "
            "the final gains, and one paragraph explaining what each gain changed.")},
    ],
}


def git_commit(backend: Path) -> str:
    out = subprocess.run(["git", "-C", str(backend), "rev-parse", "--short", "HEAD"], capture_output=True,
                         text=True, check=False)
    return out.stdout.strip()


class Recorder:
    """Wraps the model client: keeps the raw answer of the draft's one call and limits parallel calls."""

    def __init__(self, client, slots: asyncio.Semaphore) -> None:
        self.client, self.slots, self.calls = client, slots, []

    async def complete(self, messages, *, json_schema=None, max_tokens=None):
        async with self.slots:
            result = await self.client.complete(messages, json_schema=json_schema, max_tokens=max_tokens)
        self.calls.append({"text": result.text, "completion_tokens": result.completion_tokens,
                           "latency_ms": round(result.latency_ms)})
        return result


async def draft_one(app, case: dict, kind: str, model: str, local, cloud, slots) -> dict:
    from app.core.schemas import Chunk

    rec_local = Recorder(local, slots)
    rec_cloud = Recorder(cloud, slots) if cloud is not None else None
    clients = {"local": rec_local, **({"cloud": rec_cloud} if rec_cloud else {})}
    gateway = app.gateway.FakeGateway(clients, trusted=frozenset({"local"}))
    settings = SimpleNamespace(local_only=False)
    kc_names = [k["name"] for k in case["existing_kcs"]]
    passages = case["passages"] if case["pack"] == "fictional" else case["passages"][kind]
    chunks = [Chunk(text=p["text"], source=p["source"], topic=case["id"], score=0.0,
                    metadata={"course_id": COURSE_ID}) for p in passages]
    row = {"case": case["id"], "kind": kind, "model": model, "ok": False, "error": None, "content": None,
           "cited_sources": [], "dropped": None}
    started = time.monotonic()
    try:
        if model == "cloud":
            if case["pack"] != "fictional":  # rule 6: only fictional material goes to a hosted model
                raise SystemExit("refusing to send course pack text to the cloud model")
            kcs = [SimpleNamespace(**k) for k in case["existing_kcs"]]
            app.draft_jobs._check_cloud_text("", "", case["course_type"], chunks,
                                             kcs if kind in app.draft_jobs.TIER2 else [])
        extra = {"model": model} if model != "local" else {}
        if kind == "quiz":
            row.update(await _quiz(app, case, chunks, gateway, settings))
        elif kind in app.draft_jobs.TIER1:
            result = await app.drafts.generate_tier1_draft(course_id=COURSE_ID, kind=kind, passages=chunks,
                                                           gateway=gateway, settings=settings, **extra)
            content = app.draft_jobs.parse_content(kind, {"title": result.title, "body": result.body})
            row.update(ok=True, content=content, cited_sources=result.cited_sources)
        else:
            result = await app.structure_drafts.generate_structure_draft(
                course_id=COURSE_ID, kind=kind, passages=chunks, gateway=gateway, settings=settings,
                known_kc_names=kc_names, **extra)
            content = app.draft_jobs.parse_content(
                kind, {"items": [i.model_dump(exclude={"citations"}) for i in result.items]})
            row.update(ok=True, content=content, cited_sources=list(dict.fromkeys(result.cited_sources)))
    except (ValueError, RuntimeError) as e:  # DraftError is a ValueError; LLM errors are RuntimeErrors
        row["error"] = f"{type(e).__name__}: {e}"
    except Exception as e:  # noqa: BLE001 - recorded, the other drafts go on
        row["error"] = f"{type(e).__name__}: {e}"
    row["seconds"] = round(time.monotonic() - started, 1)
    row["raw"] = [c["text"] for c in rec_local.calls + (rec_cloud.calls if rec_cloud else [])]
    row["completion_tokens"] = sum(c["completion_tokens"] or 0
                                   for c in rec_local.calls + (rec_cloud.calls if rec_cloud else []))
    print(f"{case['id']:>20} {kind:<16} {model:<5} {'ok' if row['ok'] else 'FAILED'} {row['seconds']} s",
          flush=True)
    return row


async def _quiz(app, case: dict, chunks, gateway, settings) -> dict:
    """What `quiz_drafts.draft` does for one module: 5 questions, both kinds, the module's KC codes."""
    codes = {f"{case['id']}-kc{i}": k["name"] for i, k in enumerate(case["existing_kcs"], 1)}
    wanted, kinds = 5, {"mcq", "true_false"}
    evidence = [{"number": n, "source": c.source, "text": c.text[:1200]} for n, c in enumerate(chunks, 1)]
    request = {"module": case["module_title"], "questions_wanted": wanted, "kinds": sorted(kinds),
               "kc_codes": codes, "passages": evidence}
    messages = [{"role": "system", "content": app.quiz_drafts.SYSTEM},
                {"role": "user", "content": json.dumps(request, ensure_ascii=False)}]
    result = await gateway.complete("local", messages, settings=settings, trust_required="trusted_local")
    questions = app.quiz_drafts.parse_questions(result.text, [c.source for c in chunks], set(codes), kinds)
    try:
        offered = len(app.drafts.parse_model_json(result.text).get("questions") or [])
    except (ValueError, AttributeError):
        offered = 0
    ok = bool(questions)
    return {"ok": ok, "content": {"questions": questions[:wanted]},
            "dropped": max(0, offered - len(questions)),
            "error": None if ok else "the local model wrote no usable question",
            "cited_sources": sorted({s for q in questions for s in q["sources"]})}


async def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--backend", type=Path, required=True)
    parser.add_argument("--label", required=True)
    parser.add_argument("--env-file", type=Path, default=ROOT / ".env")
    parser.add_argument("--cases", default="")
    parser.add_argument("--kinds", default="")
    parser.add_argument("--cloud", action="store_true")
    args = parser.parse_args()
    backend = args.backend.resolve()
    sys.path.insert(0, str(backend))
    from app.core.config import Settings
    from app.instructor_ai import draft_jobs, drafts, quiz_drafts, structure_drafts
    from app.llm import factory, gateway

    app = SimpleNamespace(draft_jobs=draft_jobs, drafts=drafts, quiz_drafts=quiz_drafts,
                          structure_drafts=structure_drafts, gateway=gateway)
    settings = Settings(_env_file=args.env_file)
    loc = settings.llm.local
    local = factory.build_local_client(settings, loc.model, temperature=loc.temperature, timeout_s=180,
                                       max_tokens=loc.max_tokens)
    if isinstance(local, factory.NoLocalServer):
        raise SystemExit("VLLM_BASE_URL is not set")
    cloud = None
    if args.cloud:
        from app.llm.openai_compat import OpenAICompatClient

        if not settings.cloud_enabled:
            raise SystemExit("CLOUD_API_KEY / CLOUD_MODEL are not set")
        conf = settings.llm.cloud
        cloud = OpenAICompatClient(settings.cloud_base_url, settings.cloud_api_key.get_secret_value(),
                                   settings.cloud_model, timeout_s=conf.timeout_s, max_tokens=conf.max_tokens)
    kinds = [k for k in (args.kinds.split(",") if args.kinds else (CLOUD_KINDS if args.cloud else KINDS))]
    if args.cloud:
        cases, models = [FICTIONAL], ("local", "cloud")
    else:
        data = json.loads((HERE / "results" / "inputs.json").read_text(encoding="utf-8"))
        wanted = set(args.cases.split(",")) if args.cases else None
        cases, models = [c for c in data["cases"] if not wanted or c["id"] in wanted], ("local",)
    slots = asyncio.Semaphore(PARALLEL)
    jobs = [draft_one(app, case, kind, model, local, cloud, slots)
            for case in cases for kind in kinds for model in models]
    rows = await asyncio.gather(*jobs)
    commit = git_commit(backend)
    out = HERE / "results" / f"drafts_{args.label}.jsonl"
    with out.open("w", encoding="utf-8") as f:
        for row in rows:
            f.write(json.dumps({"label": args.label, "commit": commit, **row}, ensure_ascii=False) + "\n")
    print(f"{sum(r['ok'] for r in rows)}/{len(rows)} drafts valid; wrote {out}")


if __name__ == "__main__":
    asyncio.run(main())
