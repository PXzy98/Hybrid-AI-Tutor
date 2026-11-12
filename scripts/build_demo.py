"""Build the demo through API v2 only (docs/DEMO.md; task T9); the database is never written directly.

    python scripts/build_demo.py --base-url http://localhost:8000 [--packs harvard_cs50x ...]
                                 [--students N] [--sample-activity]

What it does, in order (every step can be run again; what exists is kept):
  1. unpacks the course packs (scripts/fetch_open_courses.py unpack) when they are not unpacked yet;
  2. logs in as the instructor or admin named by DEMO_INSTRUCTOR_USERNAME / DEMO_INSTRUCTOR_PASSWORD (the
     account must have chosen its own password already);
  3. per pack: creates the course (type from the manifest), one module per manifest module, uploads the
     module files and the course-level documents, waits for the index rebuild. Files the privacy scan
     refuses (422) are reported and skipped. `instructor_only/` is never uploaded;
  4. creates fictional demo students (credentials go to var/demo_accounts.json, never to the screen),
     lists them in each course, and lets them join with the course's invitation code;
  5. sets visibility mode B in every demo course;
  6. with --sample-activity: each student acknowledges mode B, answers the check questions the modules
     have, and asks two questions (fictional, written from the pack material).
"""
import argparse
import csv
import io
import json
import mimetypes
import os
import re
import secrets
import subprocess
import sys
import time
from collections.abc import Callable
from dataclasses import dataclass, field
from pathlib import Path

import httpx

ROOT = Path(__file__).resolve().parents[1]
PACKS_DIR = ROOT / "data" / "demo_courses"
ACCOUNTS_FILE = ROOT / "var" / "demo_accounts.json"
DEFAULT_PACKS = ["mit_hst151_pharmacology", "mit_7_016_intro_biology", "mit_6_002_circuits", "harvard_cs50x"]
V2 = "/api/v2"
# must be in limits.accounts.allowed_email_domains of the server (default uottawa.ca); fictional addresses
EMAIL_DOMAIN = os.environ.get("DEMO_EMAIL_DOMAIN", "uottawa.ca")
JOB_TIMEOUT_SECONDS = 900

# Fictional questions written from the pack material; the tutor answers them from the uploaded files.
QUESTIONS = {
    "mit_hst151_pharmacology": [
        "What does a dose-response curve tell us about a drug?",
        "How do half-life and clearance relate to each other?",
        "What is the difference between an agonist and an antagonist?",
        "Why are some drugs given as a loading dose first?",
    ],
    "mit_7_016_intro_biology": [
        "How does the cell turn a gene into a protein?",
        "What is the difference between mitosis and meiosis?",
        "How do enzymes speed up a chemical reaction?",
        "Why does DNA replication need a primer?",
    ],
    "mit_6_002_circuits": [
        "How does Kirchhoff's current law help to analyze a circuit?",
        "What is a Thevenin equivalent circuit?",
        "Why do we use the digital abstraction?",
        "When is a time constant useful for an RC circuit?",
    ],
    "harvard_cs50x": [
        "What is the difference between an array and a linked list?",
        "How does binary search work and when can I use it?",
        "What does a pointer store in C?",
        "How do I write a simple SQL query that joins two tables?",
    ],
}
GENERIC_QUESTIONS = ["What are the main ideas of this course?", "How is the course graded?",
                     "Where should I start if I am new to the topic?"]


@dataclass
class CourseReport:
    pack: str
    code: str
    course_id: int | None = None
    created: bool = False
    modules: int = 0
    uploaded: int = 0
    refused: list[str] = field(default_factory=list)
    existing: int = 0
    failed: list[str] = field(default_factory=list)
    index_version: int | None = None


class DemoError(Exception):
    """A problem the person running the script can fix; main() prints it without a traceback."""


class Api:
    """One logged-in (or anonymous) session on a client: sends the CSRF header like the frontend."""

    def __init__(self, client: httpx.Client) -> None:
        self.client = client
        self.token = ""

    def request(self, method: str, path: str, **kwargs) -> httpx.Response:
        if method.upper() not in ("GET", "HEAD", "OPTIONS"):
            if not self.token:
                self.token = self.client.get(f"{V2}/auth/csrf").json()["csrf_token"]
            kwargs["headers"] = {**(kwargs.get("headers") or {}), "X-CSRF-Token": self.token}
        return self.client.request(method, f"{V2}{path}", **kwargs)

    def get(self, path: str, **kw) -> httpx.Response:
        return self.request("GET", path, **kw)

    def post(self, path: str, **kw) -> httpx.Response:
        return self.request("POST", path, **kw)

    def put(self, path: str, **kw) -> httpx.Response:
        return self.request("PUT", path, **kw)

    def login(self, username: str, password: str) -> dict:
        self.token = ""  # an anonymous token is not the session's
        r = self.request("POST", "/auth/login", json={"username": username, "password": password})
        if r.status_code != 200:
            raise DemoError(f"login failed ({r.status_code})")
        self.token = r.headers.get("X-CSRF-Token", "")
        return r.json()

    def close(self) -> None:
        self.client.close()


def ok(r: httpx.Response, what: str, expected: tuple[int, ...] = (200, 201)) -> dict | list | None:
    if r.status_code not in expected:
        try:
            detail = r.json().get("detail", "")
        except ValueError:
            detail = ""
        raise DemoError(f"{what} failed ({r.status_code}) {str(detail)[:200]}".strip())
    return r.json() if r.content else None


# ------------------------------------------------------------------------------------------------ packs
def ensure_unpacked(packs: list[str], packs_dir: Path = PACKS_DIR, unpack: bool = True) -> None:
    missing = [p for p in packs if not (packs_dir / p / "manifest.json").is_file()]
    if not missing:
        return
    if not unpack:
        raise DemoError(f"pack not unpacked: {', '.join(missing)}")
    unknown = [p for p in missing if not (packs_dir / "archives" / f"{p}.zip").is_file()]
    if unknown:
        raise DemoError(f"unknown pack: {', '.join(unknown)}")
    script = ROOT / "scripts" / "fetch_open_courses.py"
    if subprocess.run([sys.executable, str(script), "unpack", *missing]).returncode != 0:
        raise DemoError("unpacking the course packs failed")


def load_manifest(pack: str, packs_dir: Path = PACKS_DIR) -> dict:
    path = packs_dir / pack / "manifest.json"
    if not path.is_file():
        raise DemoError(f"unknown pack {pack!r}: {path} does not exist")
    return json.loads(path.read_text(encoding="utf-8"))


def module_code(raw: str, position: int) -> str:
    code = re.sub(r"[^A-Za-z0-9._-]+", "_", raw).strip("_")[:64]
    return code or f"module_{position}"


def document_name(relative: str) -> str:
    """Documents of different folders can share a file name (assignments/ps1, exams/ps1): the folder is
    kept in the uploaded name."""
    return relative.replace("\\", "/").replace("/", "_")


def safe_path(pack_dir: Path, relative: str) -> Path | None:
    """The file inside the pack, never one under instructor_only/ and never outside the pack."""
    path = (pack_dir / relative).resolve()
    if not path.is_relative_to(pack_dir.resolve()) or "instructor_only" in Path(relative).parts:
        return None
    return path if path.is_file() else None


# ----------------------------------------------------------------------------------------------- courses
def find_course(api: Api, code: str) -> dict | None:
    return next((c for c in ok(api.get("/courses"), "listing courses") if c["code"] == code), None)


def upload(api: Api, course_id: int, path: Path, name: str, module_id: int | None,
           report: CourseReport) -> int | None:
    """Upload one file; the job id when stored. 422 (privacy scan, unreadable) is reported, not fatal."""
    mime = mimetypes.guess_type(name)[0] or "application/octet-stream"
    form = {"module_id": str(module_id)} if module_id is not None else {}
    files = {"file": (name, path.read_bytes(), mime)}
    r = api.post(f"/courses/{course_id}/materials", files=files, data=form)
    if r.status_code == 201:
        report.uploaded += 1
        return r.json()["job_id"]
    if r.status_code == 409:
        report.existing += 1
    elif r.status_code == 422:
        try:
            reason = r.json().get("detail", "")
        except ValueError:
            reason = ""
        report.refused.append(f"{name}: {str(reason)[:120]}")
    else:
        report.failed.append(f"{name}: HTTP {r.status_code}")
    return None


def wait_for_job(api: Api, course_id: int, job_id: int, sleep: Callable[[float], None] = time.sleep,
                 timeout: float = JOB_TIMEOUT_SECONDS) -> str:
    deadline = time.monotonic() + timeout
    while True:
        job = ok(api.get(f"/courses/{course_id}/jobs/{job_id}"), "reading the rebuild job")
        if job["status"] in ("done", "failed"):
            return job["status"]
        if time.monotonic() > deadline:
            return "timeout"
        sleep(1.0)


def build_course(api: Api, pack: str, packs_dir: Path = PACKS_DIR,
                 sleep: Callable[[float], None] = time.sleep) -> CourseReport:
    manifest = load_manifest(pack, packs_dir)
    pack_dir = packs_dir / pack
    report = CourseReport(pack=pack, code=manifest["course_code"])
    course = find_course(api, report.code)
    if course is None:
        course = ok(api.post("/courses", json={"code": report.code, "title": manifest["course_title"],
                                               "course_type": manifest["course_type"]}),
                    f"creating course {report.code}")
        report.created = True
    report.course_id = course["id"]
    url = f"/courses/{course['id']}"

    have = {m["code"]: m["id"] for m in ok(api.get(f"{url}/modules"), "listing modules")}
    last_job = None
    for spec in sorted(manifest["modules"], key=lambda m: m["module_order"]):
        code = module_code(spec["module_code"], spec["module_order"])
        if code not in have:
            have[code] = ok(api.post(f"{url}/modules", json={"code": code, "title": spec["title"][:200]}),
                            f"creating module {code}")["id"]
        report.modules += 1
        path = safe_path(pack_dir, spec["demo_note"])
        if path is None:
            report.failed.append(f"{spec['demo_note']}: file missing")
            continue
        last_job = upload(api, course["id"], path, path.name, have[code], report) or last_job
    for relative in manifest["documents"]:
        path = safe_path(pack_dir, relative)
        if path is None:
            report.failed.append(f"{relative}: file missing")
            continue
        last_job = upload(api, course["id"], path, document_name(relative), None, report) or last_job

    job = ok(api.get(f"{url}/materials"), "listing materials")
    last_job = job["rebuild_job_id"] or last_job
    if last_job is not None:
        state = wait_for_job(api, course["id"], last_job, sleep)
        if state != "done":
            report.failed.append(f"index rebuild: {state}")
    report.index_version = ok(api.get(f"{url}/materials"), "listing materials")["index_version"]
    return report


def set_visibility_mode_b(api: Api, course_id: int) -> None:
    current = ok(api.get(f"/courses/{course_id}/settings"), "reading course settings")
    if current["values"].get("visibility_mode") == "B":
        return
    ok(api.put(f"/courses/{course_id}/settings",
               json={"values": {**current["values"], "visibility_mode": "B"},  # PUT replaces every value
                     "version": current["version"]}),
       "setting visibility mode B")


# ------------------------------------------------------------------------------------------------ students
def load_accounts(path: Path) -> list[dict]:
    if path.is_file():
        return json.loads(path.read_text(encoding="utf-8")).get("students", [])
    return []


def save_accounts(path: Path, students: list[dict]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"note": "fictional demo accounts; never commit", "students": students},
                               indent=2) + "\n", encoding="utf-8")
    try:
        path.chmod(0o600)
    except OSError:
        pass  # best effort (Windows)


def ensure_students(path: Path, count: int) -> list[dict]:
    """Student number 1..count with a generated password; existing entries are kept."""
    students = load_accounts(path)
    for n in range(len(students) + 1, count + 1):
        students.append({"display_name": f"Demo Student {n}", "email": f"demo.student{n}@{EMAIL_DOMAIN}",
                         "password": secrets.token_urlsafe(12)})
    save_accounts(path, students)
    return students[:count]


def invite_code(api: Api, course_id: int) -> str:
    current = ok(api.get(f"/courses/{course_id}/invite"), "reading the invitation code")
    if current and current.get("code") and not current["expired"]:
        return current["code"]
    return ok(api.post(f"/courses/{course_id}/invite/rotate"), "creating an invitation code")["code"]


def import_roster(api: Api, course_id: int, students: list[dict]) -> None:
    out = io.StringIO()
    writer = csv.writer(out)
    writer.writerow(["email", "display_name"])
    writer.writerows([s["email"], s["display_name"]] for s in students)
    report = ok(api.post(f"/courses/{course_id}/members/import",
                         files={"file": ("demo_students.csv", out.getvalue().encode(), "text/csv")}),
                "importing the student list")
    if report["rejected"]:
        raise DemoError(f"student list rejected: {report['rejected'][0]['reason']}")


def enrol_student(api: Api, student: dict, codes: dict[int, str]) -> list[int]:
    """Make the student a member of each course (code per course id); the course ids joined."""
    try:
        me = api.login(student["email"], student["password"])
    except DemoError:
        me = None
    joined: list[int] = []
    for course_id, code in codes.items():
        if me and course_id in {m["course_id"] for m in me["memberships"]}:
            joined.append(course_id)
            continue
        body = {"code": code}
        creating = me is None
        if creating:  # the first join creates the account (the e-mail is on the course list)
            body.update(email=student["email"], display_name=student["display_name"],
                        password=student["password"])
            api.token = ""
        r = api.post("/auth/join", json=body)
        if r.status_code != 200:
            raise DemoError(f"{student['display_name']} cannot join course {course_id} ({r.status_code})")
        if creating:
            api.token = r.headers.get("X-CSRF-Token", "")
        me = r.json()["me"]
        joined.append(course_id)
    return joined


# ---------------------------------------------------------------------------------------- sample activity
def questions_for(pack: str, modules: list[dict], student_index: int) -> list[str]:
    pool = QUESTIONS.get(pack) or GENERIC_QUESTIONS
    return [pool[(student_index * 2 + k) % len(pool)] for k in range(2)]


def sample_activity(api: Api, course_id: int, pack: str, student_index: int) -> dict:
    """Acknowledge mode B, answer the check questions the modules have, ask two questions."""
    done = {"checks": 0, "asked": 0, "problems": []}
    url = f"/courses/{course_id}"
    r = api.post(f"{url}/me/visibility", json={"action": "acknowledge"})
    if r.status_code != 200:
        done["problems"].append(f"acknowledge: HTTP {r.status_code}")
    modules = ok(api.get(f"{url}/modules"), "listing modules")
    for module in modules:
        r = api.get(f"{url}/onboarding", params={"module_id": module["id"]})
        if r.status_code != 200:
            continue
        diagnostic = r.json()["diagnostic"]
        if not diagnostic:
            continue
        # consent is needed for anything to be stored; answers are picked by the student's number
        answers = [{"item_id": i["id"], "choice": "ABCD"[(student_index + n) % 4]}
                   for n, i in enumerate(diagnostic)]
        r = api.post(f"{url}/onboarding", json={"module_id": module["id"], "consent": True,
                                                "answers": answers})
        done["checks"] += len(answers) if r.status_code == 200 else 0
    module_id = modules[student_index % len(modules)]["id"] if modules else None
    for k, question in enumerate(questions_for(pack, modules, student_index)):
        r = api.post(f"{url}/ask", json={"question": question, "module_id": module_id if k == 0 else None})
        if r.status_code == 200:
            done["asked"] += 1
        else:
            done["problems"].append(f"ask: HTTP {r.status_code}")
    return done


# ------------------------------------------------------------------------------------------------- driver
def build_demo(client_factory: Callable[[], httpx.Client], packs: list[str], instructor: tuple[str, str],
               students: int = 3, sample: bool = False, packs_dir: Path = PACKS_DIR,
               accounts_path: Path = ACCOUNTS_FILE, sleep: Callable[[float], None] = time.sleep,
               log: Callable[[str], None] = print) -> list[CourseReport]:
    admin = Api(client_factory())
    try:
        me = admin.login(*instructor)
        if me["must_change_password"]:
            raise DemoError("log in once as the instructor in the browser and choose a new password first")
        if me["system_role"] not in ("admin", "instructor"):
            raise DemoError("the demo account must be an instructor or an admin")
        reports = []
        for pack in packs:
            log(f"building {pack} ...")
            reports.append(build_course(admin, pack, packs_dir, sleep))
        usable = [r for r in reports if r.course_id is not None]
        for r in usable:
            set_visibility_mode_b(admin, r.course_id)
        if students:
            people = ensure_students(accounts_path, students)
            codes = {}
            for r in usable:
                import_roster(admin, r.course_id, people)
                codes[r.course_id] = invite_code(admin, r.course_id)
            for index, person in enumerate(people):
                api = Api(client_factory())
                try:
                    enrol_student(api, person, codes)
                    if sample:
                        for r in usable:
                            result = sample_activity(api, r.course_id, r.pack, index)
                            if result["problems"]:
                                r.failed.append(f"{person['display_name']}: {'; '.join(result['problems'])}")
                finally:
                    api.close()
        return reports
    finally:
        admin.close()


def summary(reports: list[CourseReport]) -> str:
    rows = [("course", "modules", "uploaded", "refused", "index")]
    rows += [(r.code, str(r.modules), str(r.uploaded), str(len(r.refused)),
              "-" if r.index_version is None else str(r.index_version)) for r in reports]
    widths = [max(len(row[i]) for row in rows) for i in range(5)]
    lines = ["  ".join(cell.ljust(w) for cell, w in zip(row, widths, strict=True)) for row in rows]
    for r in reports:
        lines += [f"{r.code} refused: {item}" for item in r.refused]
        lines += [f"{r.code} problem: {item}" for item in r.failed]
        if r.existing:
            lines.append(f"{r.code}: {r.existing} files were already there")
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--base-url", default="http://localhost:8000")
    ap.add_argument("--packs", nargs="+", default=DEFAULT_PACKS, metavar="PACK")
    ap.add_argument("--students", type=int, default=3, help="number of demo students (0: none)")
    ap.add_argument("--sample-activity", action="store_true",
                    help="students acknowledge mode B, answer check questions and ask two questions")
    args = ap.parse_args(argv)
    username = os.environ.get("DEMO_INSTRUCTOR_USERNAME", "")
    password = os.environ.get("DEMO_INSTRUCTOR_PASSWORD", "")
    if not (username and password):
        print("build_demo: set DEMO_INSTRUCTOR_USERNAME and DEMO_INSTRUCTOR_PASSWORD", file=sys.stderr)
        return 2
    try:
        ensure_unpacked(args.packs)
        reports = build_demo(lambda: httpx.Client(base_url=args.base_url, timeout=120), args.packs,
                             (username, password), args.students, args.sample_activity)
    except httpx.ConnectError:
        print(f"build_demo: cannot reach {args.base_url} (is the app running?)", file=sys.stderr)
        return 1
    except DemoError as e:
        print(f"build_demo: {e}", file=sys.stderr)
        return 1
    print()
    print(summary(reports))
    if args.students:
        print(f"\nDemo student logins: {ACCOUNTS_FILE.relative_to(ROOT)} (not printed, not committed)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
