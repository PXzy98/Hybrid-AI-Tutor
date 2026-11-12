"""The open course packs (data/demo_courses/archives/*.zip) are complete, attributed and safe to unpack."""
import json
import zipfile
from pathlib import Path

import pytest

from app.privacy.profiles import privacy_profile
from app.rag.demo_courses import stage_demo_course

ARCHIVES = Path(__file__).resolve().parents[2] / "data" / "demo_courses" / "archives"
EXPECTED = {
    "medical_science": {"mit_hst151_pharmacology", "mit_hst035_pathology"},
    "life_science": {"mit_7_03_genetics", "mit_7_016_intro_biology"},
    "ece": {"mit_6_002_circuits", "mit_res_6_007_signals", "mit_6_006_algorithms", "harvard_cs50x"},
}
NAMES = sorted(set().union(*EXPECTED.values()))


@pytest.fixture(scope="module")
def unpacked(tmp_path_factory) -> Path:
    root = tmp_path_factory.mktemp("open_courses")
    for name in NAMES:
        with zipfile.ZipFile(ARCHIVES / f"{name}.zip") as z:
            for member in z.namelist():
                assert member.startswith(f"{name}/") and ".." not in Path(member).parts
            z.extractall(root)
    return root


def _manifest(pack: Path) -> dict:
    return json.loads((pack / "manifest.json").read_text(encoding="utf-8"))


def test_two_courses_per_area_and_nothing_else(unpacked):
    assert sorted(p.stem for p in ARCHIVES.glob("*.zip")) == NAMES
    found: dict[str, set[str]] = {}
    for name in NAMES:
        found.setdefault(_manifest(unpacked / name)["course_type"], set()).add(name)
    assert found == EXPECTED


@pytest.mark.parametrize("name", NAMES)
def test_pack_is_licensed_attributed_and_complete(unpacked, name, tmp_path):
    pack = unpacked / name
    m = _manifest(pack)
    assert m["type"] == "open_course_material" and m["license"] == "CC BY-NC-SA 4.0"
    assert m["source"].startswith("https://") and m["author"]
    privacy_profile(m["course_type"])  # a course type that exists
    modules = m["modules"]
    assert [x["module_order"] for x in modules] == list(range(1, len(modules) + 1))
    assert len({x["module_code"] for x in modules}) == len(modules)
    assert m["documents"][0] == "syllabus.md"
    files = [pack / d for d in m["documents"]] + [pack / x["demo_note"] for x in modules]
    for f in files + [pack / d for d in m["instructor_only"]]:
        assert f.resolve().is_relative_to(pack.resolve()) and f.is_file() and f.stat().st_size > 0
        if f.suffix == ".md":
            head = f.read_text(encoding="utf-8")[:600]
            assert "> Source:" in head and "CC BY-NC-SA 4.0" in head
    readme = (pack / "README.md").read_text(encoding="utf-8")
    assert "CC BY-NC-SA 4.0" in readme and m["source"] in readme
    staged = stage_demo_course(pack, tmp_path, 3)
    assert len(staged) == len(files)


@pytest.mark.parametrize("name", NAMES)
def test_solutions_are_never_course_material(unpacked, name, tmp_path):
    m = _manifest(unpacked / name)
    assert all(d.startswith("instructor_only/") for d in m["instructor_only"])
    assert not any("instructor_only" in d for d in m["documents"])
    staged = stage_demo_course(unpacked / name, tmp_path, 3)
    assert not any("solution" in p.name or p.name.endswith(("_sol.pdf", "_ans.pdf")) for p in staged)
