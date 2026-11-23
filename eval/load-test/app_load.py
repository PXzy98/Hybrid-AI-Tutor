"""V13: load of the whole ask path (privacy filter, routing, retrieval, the gateway queue, the local model)
for N students asking at the same time, through a running API.

Every virtual student is a separate account of a demo build (`scripts/build_demo.py`) and asks the
S11 questions of one of its courses (eval/course-rag-packs/questions), one after the other; a share of them
asks for a long answer (" Explain it in detail with a worked example and a comparison table.").
Each student's course is read from the memberships its login returns and matched to a pack by the course
code of the pack manifest (unpack the packs first: `python scripts/fetch_open_courses.py unpack`).
Run it against a copy of the demo database with the local model only (no cloud key),
so that no course text leaves and the demo's statistics do not change.

    python eval/load-test/app_load.py --base http://127.0.0.1:8001 --accounts var/demo_build/accounts.json \\
        --levels 4,8,16,24,32 --per-student 3 --label 2048-c4

Only counts, durations and status codes are written (results/app_load_<label>.jsonl); never a question,
an answer or a password.
"""

import argparse
import asyncio
import json
import math
import random
import statistics
import time
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[2]
QUESTIONS = ROOT / "eval/course-rag-packs/questions"
PACKS = ROOT / "data/demo_courses"
RESULTS = Path(__file__).resolve().parent / "results"
DETAILED_SUFFIX = " Explain it in detail with a worked example and a comparison table."
CUT_NOTE = "length limit"


def questions(pack: str) -> list[str]:
    rows = [
        json.loads(line)
        for line in (QUESTIONS / f"{pack}.jsonl").read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    return [r["question"] for r in rows if r.get("type") != "logistics"]


async def login(client: httpx.AsyncClient, base: str, acc: dict) -> None:
    client.headers["X-CSRF-Token"] = (await client.get(f"{base}/api/v2/auth/csrf")).json()["csrf_token"]
    r = await client.post(
        f"{base}/api/v2/auth/login", json={"username": acc["email"], "password": acc["password"]}
    )
    r.raise_for_status()
    client.headers["X-CSRF-Token"] = r.headers.get("X-CSRF-Token", client.headers["X-CSRF-Token"])


def pack_codes() -> dict[str, str]:
    """Course code (as the demo build creates it from the pack manifest) -> pack with a question file."""
    codes = {}
    for manifest in PACKS.glob("*/manifest.json"):
        pack = manifest.parent.name
        if (QUESTIONS / f"{pack}.jsonl").exists():
            codes[json.loads(manifest.read_text(encoding="utf-8"))["course_code"]] = pack
    if not codes:
        raise SystemExit("no unpacked course pack: run python scripts/fetch_open_courses.py unpack")
    return codes


async def discover(base: str, accounts: list[dict], codes: dict[str, str], need: int) -> list[tuple]:
    """(account, course id, pack) for the first `need` students with a course of a pack, read from the
    memberships the login returns (any account file with email and password works, e.g. build_demo.py's)."""
    found = []
    for acc in accounts:
        async with httpx.AsyncClient(timeout=60) as client:
            client.headers["X-CSRF-Token"] = (await client.get(f"{base}/api/v2/auth/csrf")).json()[
                "csrf_token"
            ]
            r = await client.post(
                f"{base}/api/v2/auth/login", json={"username": acc["email"], "password": acc["password"]}
            )
        if r.status_code != 200:
            continue
        courses = [
            m for m in r.json().get("memberships", []) if m.get("role") == "student" and m["code"] in codes
        ]
        if courses:
            found.append((acc, courses[0]["course_id"], codes[courses[0]["code"]]))
        if len(found) >= need:
            break
    if len(found) < need:
        raise SystemExit(f"only {len(found)} students with a course of a pack; {need} needed")
    return found


async def student(i, acc, course_id, pack, a, rnd, rows, level, t_start):
    async with httpx.AsyncClient(timeout=a.client_timeout) as client:
        await login(client, a.base, acc)
        pool = questions(pack)
        await asyncio.sleep(rnd.uniform(0, a.spread))  # students do not press Enter in the same millisecond
        for k in range(a.per_student):
            detailed = rnd.random() < a.detailed_share
            q = rnd.choice(pool) + (DETAILED_SUFFIX if detailed else "")
            t0 = time.perf_counter()
            try:
                r = await client.post(
                    f"{a.base}/api/v2/courses/{course_id}/ask", json={"question": q, "language": "en"}
                )
                status, d = (
                    r.status_code,
                    (r.json() if r.headers.get("content-type", "").startswith("application/json") else {}),
                )
            except httpx.HTTPError as e:
                status, d = type(e).__name__, {}
            seconds = time.perf_counter() - t0
            warnings = d.get("warnings") or []
            rows.append(
                {
                    "level": level,
                    "student": i,
                    "pack": pack,
                    "n": k,
                    "detailed": detailed,
                    "status": status,
                    "seconds": round(seconds, 2),
                    "started_s": round(t0 - t_start, 2),
                    "model": d.get("model_used"),
                    "target": d.get("route_target"),
                    "cut_off": any(CUT_NOTE in w for w in warnings),
                    "busy": status == 503,
                    "code": d.get("code") if status != 200 else None,
                    "generate_ms": (d.get("timings_ms") or {}).get("generate"),
                }
            )


def summary(rows: list[dict], level: int, wall: float) -> dict:
    ok = [r for r in rows if r["status"] == 200]
    sec = sorted(r["seconds"] for r in ok)
    return {
        "level": level,
        "requests": len(rows),
        "ok": len(ok),
        "busy_503": sum(r["busy"] for r in rows),
        "other_errors": len(rows) - len(ok) - sum(r["busy"] for r in rows),
        "cut_off": sum(r["cut_off"] for r in ok),
        "detailed": sum(r["detailed"] for r in rows),
        "p50_s": round(statistics.median(sec), 1) if sec else None,
        "p95_s": round(sec[min(len(sec) - 1, math.ceil(len(sec) * 0.95) - 1)], 1) if sec else None,
        "max_s": round(sec[-1], 1) if sec else None,
        "over_60s": sum(s > 60 for s in sec),
        "answers_per_min": round(len(ok) / wall * 60, 1),
        "wall_s": round(wall, 1),
        "local_answers": sum(r["target"] == "local" for r in ok),
    }


async def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base", default="http://127.0.0.1:8001")
    ap.add_argument(
        "--accounts",
        type=Path,
        required=True,
        help="accounts file of the demo build (scripts/build_demo.py; git-ignored)",
    )
    ap.add_argument("--levels", default="4,8,16,24,32")
    ap.add_argument("--per-student", type=int, default=3)
    ap.add_argument("--detailed-share", type=float, default=0.1)
    ap.add_argument("--spread", type=float, default=5.0, help="seconds over which the students start")
    ap.add_argument("--client-timeout", type=float, default=300)
    ap.add_argument("--label", required=True)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    levels = [int(x) for x in a.levels.split(",")]
    accounts = json.loads(a.accounts.read_text(encoding="utf-8"))["students"]
    students = await discover(a.base, accounts, pack_codes(), max(levels))
    RESULTS.mkdir(exist_ok=True)
    out = RESULTS / f"app_load_{a.label}.jsonl"
    out.write_text("", encoding="utf-8")
    table = []
    for level in levels:
        rnd = random.Random(a.seed + level)
        chosen = rnd.sample(students, level)
        rows: list[dict] = []
        t_start = time.perf_counter()
        await asyncio.gather(
            *(
                student(i, acc, course_id, pack, a, rnd, rows, level, t_start)
                for i, (acc, course_id, pack) in enumerate(chosen)
            )
        )
        wall = time.perf_counter() - t_start
        with out.open("a", encoding="utf-8") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
        s = summary(rows, level, wall)
        table.append(s)
        print(json.dumps(s), flush=True)
    (RESULTS / f"app_load_{a.label}_summary.json").write_text(json.dumps(table, indent=1), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main())
