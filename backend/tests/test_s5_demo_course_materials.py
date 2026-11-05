"""S5 fictional demonstration course pack and source-integrity checks.

Only checks authored demo documents. Official ELG 5902 materials need permission first.
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
BASE = ROOT / "data" / "demo_courses" / "general_medical_knowledge"
MARKER = "DEMO MATERIAL"


def _manifest():
    return json.loads((BASE / "manifest.json").read_text(encoding="utf-8"))


def test_demo_course_documents_are_complete_and_marked_fictional():
    manifest = _manifest()
    assert manifest["course_code"] == "MED 0000"
    assert manifest["review_status"] == "unreviewed"
    assert manifest["is_official_course"] is False
    assert manifest["source_permissions_verified"] is False
    docs = manifest["documents"]
    assert {"course_outline.md", "project_requirements.md"} <= set(docs)
    assert any(p.startswith("templates/") for p in docs)
    for relative in docs:
        path = (BASE / relative).resolve()
        assert path.is_relative_to(BASE.resolve())
        assert path.is_file()
        text = path.read_text(encoding="utf-8")
        assert MARKER in text
        assert "NOT AN OFFICIAL SYLLABUS" in text


def test_five_modules_have_readable_draft_notes_and_existing_snapshot_paths():
    manifest = _manifest()
    modules = manifest["modules"]
    assert len(modules) == 5
    assert [m["module_order"] for m in modules] == [1, 2, 3, 4, 5]
    assert len({m["module_code"] for m in modules}) == 5
    assert [m["module_code"] for m in modules] == [
        "high_blood_pressure", "asthma", "type2_diabetes", "migraine", "pneumonia"
    ]
    for module in modules:
        note = (BASE / module["demo_note"]).resolve()
        source = (BASE / module["bundled_reference"]).resolve()
        assert note.is_relative_to(BASE.resolve())
        assert note.is_file() and source.is_file()
        assert source.is_relative_to((ROOT / "data" / "medical_rag" / "raw").resolve())
        text = note.read_text(encoding="utf-8")
        assert MARKER in text
        assert module["title"] in text
        assert "MedlinePlus" in text
        assert "professional clinical judgement" in text
        assert module["medical_review"] == "unreviewed"


def test_elg5902_materials_are_not_included_without_permission():
    folder = ROOT / "data" / "demo_courses" / "elg5902"
    files = list(folder.rglob("*"))
    files = [p for p in files if p.is_file()]
    assert [p.name for p in files] == ["README.md"]
    text = files[0].read_text(encoding="utf-8")
    assert "permission" in text.lower()
    assert "No ELG 5902 course materials" in text


def test_course_scaffolding_is_not_conflated_with_medical_signoff():
    text = (BASE / "course_outline.md").read_text(encoding="utf-8")
    assert "undergraduate" in text.lower()
    assert "84-item draft MCQ bank" in text
    assert "unapproved" in text.lower()
    assert "not" in (BASE / "README.md").read_text(encoding="utf-8").lower()
