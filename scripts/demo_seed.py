"""Create three demo students with different starting levels, through the public API (docs/DEMO.md).

    .venv\\Scripts\\python scripts\\demo_seed.py --base-url http://localhost:8080 --instructor prof

The instructor must exist and have changed the initial password (log in once in the browser). The
instructor password is read from DEMO_INSTRUCTOR_PASSWORD or asked for. Demo students get the password
DEMO_STUDENT_PASSWORD (default below) and are reset if they already exist.

    demo.novice        misses the first diagnostic question -> every part starts at "basic"
    demo.intermediate  answers the diagnostic correctly      -> "intermediate"
    demo.advanced      diagnostic + one correct check answer per part -> "advanced"

Answer keys are read from content/ only to simulate students; the API never reveals them.
Requires content.serve_unreviewed=true on the server while the content is unreviewed.
"""
import argparse
import getpass
import os
import sys
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / "backend"))
from app.learner.content import ContentStore  # noqa: E402

TOPIC = "high_blood_pressure"
DEFAULT_STUDENT_PASSWORD = "demo-student-2026"  # demo accounts only; never use for real students
STUDENTS = [
    ("demo.novice", "Demo Novice", "novice", {"sequencing": "example_first", "detail": "concise"}),
    ("demo.intermediate", "Demo Intermediate", "intermediate",
     {"sequencing": "example_first", "detail": "detailed"}),
    ("demo.advanced", "Demo Advanced", "advanced", {"sequencing": "concept_first", "detail": "detailed"}),
]


def fail(msg: str) -> None:
    sys.exit(f"demo_seed: {msg}")


def login(client: httpx.Client, username: str, password: str) -> dict:
    r = client.post("/api/v1/auth/login", json={"username": username, "password": password})
    if r.status_code != 200:
        fail(f"login as {username} failed ({r.status_code}): {r.json().get('detail')}")
    return r.json()


def temporary_password(admin: httpx.Client, username: str, name: str) -> str:
    r = admin.post("/api/v1/admin/students", json={"username": username, "display_name": name})
    if r.status_code == 201:
        return r.json()["temporary_password"]
    if r.status_code != 409:
        fail(f"creating {username} failed ({r.status_code}): {r.text}")
    student = next(s for s in admin.get("/api/v1/admin/students").json() if s["username"] == username)
    admin.patch(f"/api/v1/admin/students/{student['id']}", json={"active": True})
    return admin.post(f"/api/v1/admin/students/{student['id']}/reset-password").json()["temporary_password"]


def seed_student(base: str, content: ContentStore, admin: httpx.Client, spec, password: str) -> dict:
    username, name, profile, prefs = spec
    temp = temporary_password(admin, username, name)
    with httpx.Client(base_url=base, timeout=60) as s:
        login(s, username, temp)
        r = s.post("/api/v1/auth/change-password", json={"current_password": temp, "new_password": password})
        if r.status_code != 200:
            fail(f"password change for {username} failed: {r.text}")
        s.delete("/api/v1/learner/me")  # start from a clean profile when re-seeding
        diagnostic = s.get("/api/v1/onboarding", params={"topic": TOPIC}).json()["diagnostic"]
        if not diagnostic:
            fail("the server serves no check questions: set CONTENT__SERVE_UNREVIEWED=true (docs/DEMO.md)")
        answers = []
        for n, item in enumerate(diagnostic):
            key = content.item(item["id"]).answer
            choice = key if profile != "novice" or n > 0 else next(k for k in "ABCD" if k != key)
            answers.append({"item_id": item["id"], "choice": choice})
        result = s.post("/api/v1/onboarding", json={"topic": TOPIC, "consent": True, "preferences": prefs,
                                                      "answers": answers}).json()
        if profile == "advanced":
            used = {a["item_id"] for a in answers}
            for kc in content.kcs(TOPIC):
                item = next(i for i in content.items(kc.id, reviewed_only=False) if i.id not in used)
                s.post("/api/v1/check", json={"item_id": item.id, "choice": item.answer})
        me = s.get("/api/v1/learner/me", params={"topic": TOPIC}).json()
        bands = [k["band"] for k in me["topics"][0]["kcs"]]
        return {"username": username, "bands": bands, "skipped": result.get("skipped", [])}


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8080")
    ap.add_argument("--instructor", default=os.environ.get("DEMO_INSTRUCTOR_USERNAME", "prof"))
    args = ap.parse_args(argv)
    instructor_pw = os.environ.get("DEMO_INSTRUCTOR_PASSWORD") or getpass.getpass("Instructor password: ")
    student_pw = os.environ.get("DEMO_STUDENT_PASSWORD", DEFAULT_STUDENT_PASSWORD)

    content = ContentStore(ROOT / "content" / "topics", serve_unreviewed=True)
    with httpx.Client(base_url=args.base_url, timeout=60) as admin:
        try:
            me = login(admin, args.instructor, instructor_pw)
        except httpx.ConnectError:
            fail(f"cannot reach {args.base_url} (is the app running?)")
        if me["role"] != "instructor":
            fail(f"{args.instructor} is not an instructor")
        if me["must_change_password"]:
            fail("log in once as the instructor in the browser and choose a new password first")
        for spec in STUDENTS:
            r = seed_student(args.base_url, content, admin, spec, student_pw)
            print(f"{r['username']:<18} bands: {' '.join(r['bands'])}"
                  + (f"   (not assessed: {', '.join(r['skipped'])})" if r["skipped"] else ""))
    print("\nDemo students log in with the password from DEMO_STUDENT_PASSWORD "
          f"(default: {DEFAULT_STUDENT_PASSWORD}).")


if __name__ == "__main__":
    main()
