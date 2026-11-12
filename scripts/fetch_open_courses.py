"""The open course packs of `data/demo_courses/` (MIT OpenCourseWare and Harvard CS50x).

The repository stores one zip per pack in `data/demo_courses/archives/`; the unpacked folders are
git-ignored. Every pack is published under CC BY-NC-SA 4.0. Downloading keeps the PDFs unchanged, converts
web pages (syllabus, calendar, assignment pages, CS50x notes) to Markdown with an attribution header, puts
solutions in `instructor_only/`, and writes `manifest.json` (the format read by
`app.rag.demo_courses.stage_demo_course`) and a `README.md` with source, author and license.

Usage (from the repository root):
    python scripts/fetch_open_courses.py unpack [pack ...]    # unpack the zips: what everyone runs first
    python scripts/fetch_open_courses.py download [pack ...]  # download again (existing PDFs are kept)
    python scripts/fetch_open_courses.py archive [pack ...]   # write the zips from the unpacked folders
Nothing downloaded is executed.
"""
import json
import re
import sys
import time
import urllib.request
import zipfile
from datetime import date
from html import unescape
from pathlib import Path

OUT = Path(__file__).resolve().parents[1] / "data" / "demo_courses"
ARCHIVES = OUT / "archives"
EXTRA_PAGES = ("calendar", "assignments", "exams")  # course-level pages, where the course has them
UA = {"User-Agent": "Mozilla/5.0 (course-pack-builder)"}
OCW = "https://ocw.mit.edu"
CS50 = "https://cs50.harvard.edu/x"
LICENSE = "CC BY-NC-SA 4.0"
LICENSE_URL = "https://creativecommons.org/licenses/by-nc-sa/4.0/"

# pack name, OCW course slug, the page that lists the material, course type, code, title, author.
# `skip`: regular expression for files left out (unreadable or duplicate); `titles`: module titles for
# courses whose file names carry no topic (only the listed files are used).
OCW_COURSES = [
    dict(pack="mit_hst151_pharmacology", slug="hst-151-principles-of-pharmacology-spring-2005",
         page="lecture-notes", course_type="medical_science", code="MIT HST.151",
         title="Principles of Pharmacology (Spring 2005)",
         author="Carl Rosow, Gary Strichartz, and Carol Walsh, MIT OpenCourseWare",
         titles={"0201_1_rosow": "Introduction: receptors and dose-response",
                 "ln34hms3275": "Pharmacokinetics I and II",
                 "0203_case_exampl": "Case: anticholinesterase",
                 "ln1112hms5008": "Autonomic pharmacology; antidysrhythmics",
                 "0215_2_weinblatt": "Antiinflammatory drugs",
                 "0216_1_baker": "Vasoactive drugs I",
                 "0216_2_baker": "Vasoactive drugs II: heart failure",
                 "0217_1_lees": "Lipid lowering drugs",
                 "0222_2_spitzer": "Immunosuppression for solid organ transplantation",
                 "parkinson": "Neuropharmacology I: drugs for movement disorders",
                 "ln15ahms2066": "Nitric oxide",
                 "antidepresedtive": "Neuropharmacology II: anxiolytics and antidepressants",
                 "anticonvulsants": "Neuropharmacology III: anticonvulsants",
                 "ln2425_antimic": "Antimicrobials I and II",
                 "ln2627hms5885": "Chemotherapy I and II",
                 "ln2829ahms7471": "Opioids I and II"}),
    dict(pack="mit_hst035_pathology", slug="hst-035-principle-and-practice-of-human-pathology-spring-2003",
         page="lecture-notes", course_type="medical_science", code="MIT HST.035",
         title="Principle and Practice of Human Pathology (Spring 2003)",
         author="Kamran Badizadegan, MIT OpenCourseWare", extra=("calendar", "assignments"),
         titles={"introduction_2003": "Introduction to human pathology and diagnostic medicine",
                 "epithelium_2003": "Epithelial structure and function",
                 "immunesystem2003": "The immune system",
                 "cellinjury_2003": "Cell injury, adaptation and death",
                 "inflammation2003": "Acute and chronic inflammation",
                 "tissuerepair2003": "Tissue repair, fibrosis and healing",
                 "infections": "Infectious diseases",
                 "transplant_2003": "Transplantation",
                 "optimal_diets_sl": "Diet and disease development",
                 "isch_infarct2003": "Ischemia and infarction",
                 "genetics_2003": "Genetic disorders",
                 "liver": "The liver"}),
    dict(pack="mit_7_03_genetics", slug="7-03-genetics-fall-2004", page="lecture-notes",
         course_type="life_science", code="MIT 7.03", title="Genetics (Fall 2004)",
         author="Chris Kaiser, Gerald Fink, and Leona Samson, MIT OpenCourseWare",
         skip=r"lecture33_"),  # three large scanned image files
    dict(pack="mit_7_016_intro_biology", slug="7-016-introductory-biology-fall-2018", page="recitations",
         course_type="life_science", code="MIT 7.016", title="Introductory Biology (Fall 2018)",
         author="Barbara Imperiali, Adam Martin, and Debra Mauzy-Melitz, MIT OpenCourseWare"),
    dict(pack="mit_6_002_circuits", slug="6-002-circuits-and-electronics-spring-2007", page="lecture-notes",
         course_type="ece", code="MIT 6.002", title="Circuits and Electronics (Spring 2007)",
         author="Anant Agarwal, MIT OpenCourseWare"),
    dict(pack="mit_res_6_007_signals", slug="res-6-007-signals-and-systems-spring-2011", page="lecture-notes",
         course_type="ece", code="MIT RES.6-007", title="Signals and Systems (Spring 2011)",
         author="Alan V. Oppenheim, MIT OpenCourseWare", extra=("assignments",)),
    dict(pack="mit_6_006_algorithms", slug="6-006-introduction-to-algorithms-spring-2020",
         page="lecture-notes",
         course_type="ece", code="MIT 6.006", title="Introduction to Algorithms (Spring 2020)",
         author="Erik Demaine, Jason Ku, and Justin Solomon, MIT OpenCourseWare",
         extra=("calendar", "assignments", "quizzes"),
         skip=r"Recitation|Lecture 16:"),  # lecture 16 has no extractable text
]


def fetch(url: str) -> bytes:
    for attempt in range(4):
        try:
            with urllib.request.urlopen(urllib.request.Request(url, headers=UA), timeout=60) as r:
                return r.read()
        except Exception:
            if attempt == 3:
                raise
            time.sleep(3)
    raise RuntimeError(url)


def page(url: str) -> str:
    return fetch(url).decode("utf-8", "replace")


def slugify(text: str) -> str:
    return re.sub(r"[^a-z0-9]+", "_", text.lower()).strip("_")[:48].rstrip("_")


def strip_tags(fragment: str) -> str:
    return re.sub(r"\s+", " ", unescape(re.sub(r"<[^>]+>", "", fragment))).strip()


def html_to_md(fragment: str) -> str:
    """Enough Markdown for these pages: headings, lists, code blocks, emphasis."""
    t = re.sub(r"(?is)<(script|style|nav|footer|button|svg|form)[^>]*>.*?</\1>", "", fragment)
    t = re.sub(r"(?is)<pre[^>]*>(.*?)</pre>",
               lambda m: "\n```\n" + unescape(re.sub(r"<[^>]+>", "", m.group(1))).strip("\n") + "\n```\n", t)
    for n in range(1, 5):
        t = re.sub(rf"(?is)<h{n}[^>]*>(.*?)</h{n}>",
                   lambda m, n=n: f"\n\n{'#' * n} {strip_tags(m.group(1))}\n\n", t)
    t = re.sub(r"(?is)<tr[^>]*>(.*?)</tr>", lambda m: "\n| " + " | ".join(
        strip_tags(x) for x in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", m.group(1))) + " |\n", t)
    t = re.sub(r"(?is)<li[^>]*>", "\n- ", t)
    t = re.sub(r"(?is)<code[^>]*>(.*?)</code>", lambda m: "`" + re.sub(r"<[^>]+>", "", m.group(1)) + "`", t)
    t = re.sub(r"(?is)<(strong|b)>(.*?)</\1>", r"**\2**", t)
    t = re.sub(r"(?is)<(em|i)>(.*?)</\1>", r"*\2*", t)
    t = re.sub(r"(?is)<br\s*/?>", "\n", t)
    t = re.sub(r"(?is)</(p|div|ul|ol|table|tr|blockquote)>", "\n\n", t)
    t = re.sub(r"(?is)</t[dh]>", " | ", t)
    t = unescape(re.sub(r"(?s)<[^>]+>", "", t))
    parts = re.split(r"(\n```\n.*?\n```\n)", t, flags=re.S)  # code blocks stay as they are
    for i, p in enumerate(parts):
        if not p.startswith("\n```"):
            p = re.sub(r" *\n *", "\n", re.sub(r"[ \t]+", " ", p))
            parts[i] = re.sub(r"\n(-\n)+", "\n", re.sub(r"\n{3,}", "\n\n", p))
    return "".join(parts).strip() + "\n"


def main_content(html: str) -> str:
    m = re.search(r"(?is)<main[^>]*>(.*)</main>", html)
    body = m.group(1) if m else html
    m = re.search(r'(?is)id="course-content-section"[^>]*>(.*)', body)
    return m.group(1) if m else body


def attribution(name: str, url: str, author: str, changes: str) -> str:
    return (f"> Source: {name}, {author}. {url}\n"
            f"> License: {LICENSE} ({LICENSE_URL}). Retrieved {date.today().isoformat()}.\n"
            f"> Changes: {changes}\n\n")


def ocw_materials(c: dict) -> list[tuple]:
    """(sort key, resource, title, pdf url) of each file listed on the course's material page."""
    listing = page(f"{OCW}/courses/{c['slug']}/pages/{c['page']}/")
    rows = re.findall(r"(?is)<tr>(.*?)</tr>", listing)
    order, topics = {}, {}
    for i, row in enumerate(rows):
        cells = [strip_tags(x) for x in re.findall(r"(?is)<t[dh][^>]*>(.*?)</t[dh]>", row)]
        for res in dict.fromkeys(re.findall(r'/resources/([^/"]+)/', row)):
            order.setdefault(res, i)
            if len(cells) > 1 and cells[0].isdigit():
                topics.setdefault(res, []).append((cells[0], cells[1]))
    link = rf'href="/courses/{re.escape(c["slug"])}/resources/([^/"]+)/"'
    resources = sorted(set(re.findall(link, listing)))
    out = []
    for res in resources:
        html = page(f"{OCW}/courses/{c['slug']}/resources/{res}/")
        pdf = re.search(r'href="([^"]+\.pdf)"', html)
        if not pdf:
            continue
        title = re.search(r"<title>(.*?)</title>", html, re.S)
        title = unescape(title.group(1)).split(" | ")[0].strip() if title else res
        if c.get("skip") and re.search(c["skip"], f"{title} {res}"):
            continue
        if c.get("titles"):
            if res not in c["titles"]:
                continue
            key, title = (order.get(res, 999), res), c["titles"][res]
        else:
            m = re.search(r"(?:Lecture|Recitation|lecture)\s*(\d+)(b?)", title)
            key = ((int(m.group(1)) + (0.5 if m.group(2) else 0)) if m else 999, res)
            title = re.sub(r"^(Lecture|Recitation) ([\db]+)[:,]?\s*", r"\1 \2: ", title).rstrip(": ")
            if res in topics and not re.search(r"[:,]", title):
                nums, names = [n for n, _ in topics[res]], [t for _, t in topics[res]]
                label = f"Lecture {nums[0]}" if len(nums) == 1 else f"Lectures {nums[0]}-{nums[-1]}"
                name = names[0] if len(names) == 1 else f"{names[0]} and {names[-1].split()[-1]}"
                title = f"{label}: {name}"
        url = pdf.group(1) if pdf.group(1).startswith("http") else OCW + pdf.group(1)
        out.append((key, res, title, url))
    return sorted(out)


def build_ocw(c: dict) -> dict:
    pack = OUT / c["pack"]
    (pack / "modules").mkdir(parents=True, exist_ok=True)
    modules = []
    for n, (_, res, title, url) in enumerate(ocw_materials(c), 1):
        name = f"{n:02d}_{slugify(title) or res}.pdf"
        dest = pack / "modules" / name
        if not dest.exists():
            dest.write_bytes(fetch(url))
        modules.append({"module_order": n, "module_code": slugify(title) or res, "title": title,
                        "demo_note": f"modules/{name}", "source_url": url})
    url = f"{OCW}/courses/{c['slug']}/pages/syllabus/"
    try:
        text = html_to_md(main_content(page(url)))
    except Exception:  # some courses have an introduction page instead of a syllabus
        url = f"{OCW}/courses/{c['slug']}/pages/introduction/"
        text = html_to_md(main_content(page(url)))
    (pack / "syllabus.md").write_text(
        f"# {c['code']} {c['title']}: syllabus\n\n"
        + attribution(c["title"], url, c["author"],
                      "converted from the web page to Markdown; navigation removed.")
        + text, encoding="utf-8")
    documents, instructor_only = ["syllabus.md"], []
    for name in c.get("extra", EXTRA_PAGES):
        docs, solutions = ocw_extra_page(c, pack, name)
        documents += docs
        instructor_only += solutions
    return dict(c, modules=modules, home=f"{OCW}/courses/{c['slug']}/", documents=documents,
                instructor_only=instructor_only)


SOLUTION = re.compile(r"(?i)\b(sol|soln|solutions?|ans|answers?|key)\b|_(sol|soln|ans|answers?)\b")


def ocw_extra_page(c: dict, pack: Path, name: str) -> tuple[list[str], list[str]]:
    """The page as Markdown, its question PDFs (course-level) and its solution PDFs (instructor only)."""
    url = f"{OCW}/courses/{c['slug']}/pages/{name}/"
    try:
        html = page(url)
    except Exception:
        return [], []
    label = name.replace("-", " ")
    (pack / f"{name}.md").write_text(
        f"# {c['code']} {c['title']}: {label}\n\n"
        + attribution(c["title"], url, c["author"],
                      "converted from the web page to Markdown; navigation removed.")
        + html_to_md(main_content(html)), encoding="utf-8")
    documents, solutions = [f"{name}.md"], []
    link = rf'href="/courses/{re.escape(c["slug"])}/resources/([^/"]+)/"'
    for res in sorted(set(re.findall(link, html))):
        res_html = page(f"{OCW}/courses/{c['slug']}/resources/{res}/")
        pdf = re.search(r'href="([^"]+\.pdf)"', res_html)
        if not pdf:
            continue
        title = re.search(r"<title>(.*?)</title>", res_html, re.S)
        title = unescape(title.group(1)).split(" | ")[0].strip() if title else res
        title = re.sub(r"\.pdf$", "", title)
        is_solution = bool(SOLUTION.search(title.replace("_", " ")) or SOLUTION.search(res))
        folder = f"instructor_only/{name}" if is_solution else name
        rel = f"{folder}/{slugify(title) or res}.pdf"
        dest = pack / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        if not dest.exists():
            source = pdf.group(1) if pdf.group(1).startswith("http") else OCW + pdf.group(1)
            dest.write_bytes(fetch(source))
        (solutions if is_solution else documents).append(rel)
    return documents, solutions


def build_cs50() -> dict:
    c = dict(pack="harvard_cs50x", course_type="ece", code="Harvard CS50x",
             title="CS50's Introduction to Computer Science (2026)",
             author="David J. Malan, Harvard University",
             home=f"{CS50}/")
    pack = OUT / c["pack"]
    (pack / "modules").mkdir(parents=True, exist_ok=True)
    modules = []
    for week in range(11):
        url = f"{CS50}/notes/{week}/"
        body = html_to_md(main_content(page(url)))
        wt = re.search(r"<title>Week \d+ (.*?) - CS50x", page(f"{CS50}/weeks/{week}/"))
        topic = unescape(wt.group(1)).strip() if wt else "The End"
        title = f"Week {week}: {topic}"
        name = f"{week + 1:02d}_week_{week}_{slugify(topic)}.md"
        (pack / "modules" / name).write_text(
            f"# CS50x {title}\n\n"
            + attribution("CS50x lecture notes", url, c["author"],
                          "converted from the web page to Markdown; navigation, images and videos removed.")
            + body, encoding="utf-8")
        modules.append({"module_order": week + 1, "module_code": f"week_{week}", "title": title,
                        "demo_note": f"modules/{name}", "source_url": url})
        time.sleep(1)
    url = f"{CS50}/syllabus/"
    (pack / "syllabus.md").write_text(
        "# Harvard CS50x: syllabus\n\n"
        + attribution("CS50x syllabus", url, c["author"],
                      "converted from the web page to Markdown; navigation removed.")
        + html_to_md(main_content(page(url))), encoding="utf-8")
    # CS50x is self-paced: no calendar and no exams; the problem sets and the final project are the work
    documents = ["syllabus.md"]
    (pack / "assignments").mkdir(exist_ok=True)
    pages = [(f"{CS50}/psets/{n}/", f"pset_{n}") for n in range(10)] + [(f"{CS50}/project/", "final_project")]
    for url, base in pages:
        html = page(url)
        parts = [html_to_md(main_content(html))]
        if base.startswith("pset_"):  # each problem of the set has its own page
            for sub in sorted(set(re.findall(r'href="([a-z][a-z0-9-]*/(?:[a-z0-9-]+/)?)"', html))):
                parts.append(html_to_md(main_content(page(url + sub))))
                time.sleep(0.5)
        rel = f"assignments/{base}.md"
        (pack / rel).write_text(
            f"# CS50x {base.replace('_', ' ')}\n\n"
            + attribution("CS50x problem sets", url, c["author"],
                          "converted from the web pages to Markdown; navigation, images and videos removed.")
            + "\n\n".join(parts), encoding="utf-8")
        documents.append(rel)
    return dict(c, modules=modules, documents=documents, instructor_only=[])


def write_pack(c: dict) -> None:
    pack = OUT / c["pack"]
    manifest = {
        "course_code": c["code"], "course_title": c["title"], "course_type": c["course_type"],
        "type": "open_course_material", "review_status": "unreviewed", "is_official_course": True,
        "source_permissions_verified": True, "source": c["home"], "author": c["author"],
        "license": LICENSE, "license_url": LICENSE_URL, "retrieved": date.today().isoformat(),
        "documents": c["documents"], "modules": c["modules"], "instructor_only": c["instructor_only"],
    }
    (pack / "manifest.json").write_text(json.dumps(manifest, indent=2, ensure_ascii=False) + "\n",
                                        encoding="utf-8")
    lines = [f"# {c['code']}: {c['title']}", "",
             f"Open course material used as a demo and test course of the Hybrid AI Tutor (course type "
             f"`{c['course_type']}`). See [../README.md](../README.md).", "",
             f"- **Source**: [{c['home']}]({c['home']})",
             f"- **Author**: {c['author']}",
             f"- **License**: [{LICENSE}]({LICENSE_URL}). Non-commercial use only; adaptations are shared "
             "under the same license.",
             f"- **Retrieved**: {date.today().isoformat()}",
             "- **Changes**: files renamed and numbered as modules; web pages converted to Markdown with an "
             "attribution header. PDFs are unchanged.",
             "- The authors and their institution do not endorse this project.", "",
             "## Course-level documents", "",
             "Uploaded to the course (not to a module): the syllabus and, where the course has them, the "
             "calendar, assignments and exams (questions only).", ""]
    lines += [f"- `{d}`" for d in c["documents"]]
    lines += ["", "## Instructor only", "",
              "Solutions and answer keys. **Never upload them as course material**: students would get the "
              "answers. They are kept to check generated quizzes."
              if c["instructor_only"] else "None.", ""]
    lines += [f"- `{d}`" for d in c["instructor_only"]]
    lines += ["", "## Modules", "", "| Module | Title | File |", "|---|---|---|"]
    lines += [f"| {m['module_order']} | {m['title']} | `{m['demo_note']}` |" for m in c["modules"]]
    (pack / "README.md").write_text("\n".join(lines) + "\n", encoding="utf-8")


def pack_names() -> list[str]:
    return [c["pack"] for c in OCW_COURSES] + ["harvard_cs50x"]


def archive(only: list[str]) -> None:
    """Write `archives/<pack>.zip` from the unpacked folder (what the repository stores)."""
    ARCHIVES.mkdir(exist_ok=True)
    for name in only or pack_names():
        folder = OUT / name
        target = ARCHIVES / f"{name}.zip"
        with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED, compresslevel=9) as z:
            for f in sorted(p for p in folder.rglob("*") if p.is_file()):
                info = zipfile.ZipInfo(f.relative_to(OUT).as_posix(), date_time=(2026, 1, 1, 0, 0, 0))
                info.compress_type = zipfile.ZIP_DEFLATED
                z.writestr(info, f.read_bytes(), compresslevel=9)
        print("archived", name, f"{target.stat().st_size / 1e6:.1f} MB", flush=True)


def unpack(only: list[str]) -> None:
    """Unpack `archives/<pack>.zip` into `data/demo_courses/<pack>/` (git-ignored)."""
    for name in only or pack_names():
        with zipfile.ZipFile(ARCHIVES / f"{name}.zip") as z:
            for member in z.namelist():  # every member must stay inside its pack folder
                target = (OUT / member).resolve()
                if not target.is_relative_to((OUT / name).resolve()):
                    raise SystemExit(f"unsafe path in {name}.zip: {member}")
            z.extractall(OUT)
        print("unpacked", name, flush=True)


def download(only: list[str]) -> None:
    for c in OCW_COURSES:
        if not only or c["pack"] in only:
            write_pack(build_ocw(c))
            print("built", c["pack"], flush=True)
    if not only or "harvard_cs50x" in only:
        write_pack(build_cs50())
        print("built harvard_cs50x", flush=True)


if __name__ == "__main__":
    commands = {"unpack": unpack, "download": download, "archive": archive}
    if len(sys.argv) < 2 or sys.argv[1] not in commands:
        raise SystemExit(__doc__)
    commands[sys.argv[1]](sys.argv[2:])
