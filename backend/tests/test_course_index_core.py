"""Stand-in v4 per-course retriever tests; no real course files or student data."""
import pytest

from app.rag.course_retriever import IndexedCourseRetriever
from app.rag.documents import DocumentError


def _material(root, cid, module, name, body):
    path = root / "courses" / str(cid) / "materials" / str(module) / name
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(body, encoding="utf-8")
    return path


def _fictional(tmp_path):
    _material(tmp_path, 101, "_course", "syllabus.md",
              "# Course Syllabus\nQuartzzyme defines the invented course-wide assessment policy.")
    _material(tmp_path, 101, 7, "lecture.md",
              "# Module Seven\nZephyrlens describes a fictional measuring technique in module seven.")
    _material(tmp_path, 101, 8, "lecture.md",
              "# Module Eight\nHeliometric is an imaginary project submission technique in module eight.")
    _material(tmp_path, 202, "_course", "syllabus.md",
              "# Different Syllabus\nOthercourseword is exclusive to the different course.")


def test_cannot_index_without_privacy_scanner_and_reader_fails_closed(tmp_path):
    _fictional(tmp_path)
    rag = IndexedCourseRetriever(tmp_path)
    assert rag.retrieve(101, None, "Quartzzyme", 4) == []
    with pytest.raises(DocumentError, match="requires the document privacy scanner"):
        rag.rebuild(101)
    assert not (tmp_path / "courses" / "101" / "index" / "current.json").exists()


def test_module_and_course_isolation_and_source_metadata(tmp_path):
    _fictional(tmp_path)
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    assert rag.rebuild(101) == 1
    assert rag.rebuild(202) == 1
    module_hits = rag.retrieve(101, 7, "Zephyrlens fictional measuring", 4)
    assert module_hits and module_hits[0].source == "course/101/7/lecture.md"
    assert module_hits[0].metadata == {"course_id": 101, "module_id": 7, "origin": "uploaded"}
    assert not any("Heliometric" in x.text for x in rag.retrieve(101, 7, "Heliometric", 4))
    assert rag.retrieve(202, None, "Zephyrlens", 4) == []
    assert rag.retrieve(101, None, "Othercourseword", 4) == []
    course_hits = rag.retrieve(101, 7, "Quartzzyme assessment policy", 4)
    assert any(x.metadata["module_id"] is None for x in course_hits)
    all_modules = rag.retrieve(101, None, "Heliometric", 4)
    assert any(x.metadata["module_id"] == 8 for x in all_modules)


def test_rebuild_publishes_new_version_and_other_reader_reloads(tmp_path):
    _fictional(tmp_path)
    writer = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    reader = IndexedCourseRetriever(tmp_path)
    assert writer.rebuild(101) == 1
    assert any("Zephyrlens" in x.text for x in reader.retrieve(101, 7, "Zephyrlens", 4))
    _material(tmp_path, 101, 7, "lecture.md",
              "# Updated Lecture\nAstrometric replaces the old fictional term.")
    assert writer.rebuild(101) == 2
    assert not (tmp_path / "courses" / "101" / "index" / "v1").exists()  # old text is deleted
    assert (tmp_path / "courses" / "101" / "index" / "v2" / "passages.json").exists()
    assert any("Astrometric" in x.text for x in reader.retrieve(101, 7, "Astrometric", 4))
    assert not any("Zephyrlens" in x.text for x in reader.retrieve(101, 7, "Zephyrlens", 4))


def test_rejected_replacement_cannot_publish_new_index(tmp_path):
    path = _material(tmp_path, 101, "_course", "safe.md",
                     "# Fictional Guide\nQuartzzyme is safe fictional content.")
    def scan(text):
        return "PrivateRoster" not in text
    rag = IndexedCourseRetriever(tmp_path, scan=scan)
    assert rag.rebuild(101) == 1
    path.write_text("# Private Data\nPrivateRoster contains a simulated roster entry.", encoding="utf-8")
    with pytest.raises(DocumentError, match="Privacy scan rejected"):
        rag.rebuild(101)
    assert rag._manifest_version(101) == 1
    assert not (tmp_path / "courses" / "101" / "index" / "v2").exists()
    assert not any("PrivateRoster" in x.text for x in rag.retrieve(101, None, "PrivateRoster", 4))


def test_database_version_signal_prevents_early_read(tmp_path):
    _material(tmp_path, 101, "_course", "syllabus.md",
              "# Fictional Policy\nQuartzzyme is a demo-only syllabus token.")
    authoritative = {101: 0}
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True, index_version=lambda cid: authoritative[cid])
    assert rag.rebuild(101) == 1
    assert rag.retrieve(101, None, "Quartzzyme", 4) == []
    authoritative[101] = 1
    assert rag.retrieve(101, None, "Quartzzyme", 4)


@pytest.mark.asyncio
async def test_worker_rebuild_does_not_require_api_threads(tmp_path):
    _material(tmp_path, 101, "_course", "demo.md",
              "# Fake Course\nQuartzzyme is a fictional learner exercise.")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    assert await rag.rebuild_in_worker(101) == 1
    assert len(rag.retrieve(101, None, "Quartzzyme", 1)) == 1


def test_invalid_course_and_module_ids_do_not_cross_courses(tmp_path):
    rag = IndexedCourseRetriever(tmp_path)
    assert rag.retrieve(-1, None, "private", 4) == []
    assert rag.retrieve(1, -1, "private", 4) == []
    assert rag.retrieve(1, None, "  ", 4) == []


def _indexed_text(root, course_id):
    index = root / "courses" / str(course_id) / "index"
    return "".join(p.read_text(encoding="utf-8") for p in index.rglob("*.json"))


def test_a_removed_file_leaves_no_text_in_any_index_version(tmp_path):
    _material(tmp_path, 101, "_course", "syllabus.md", "# Policy\nQuartzzyme is a demo-only syllabus token.")
    roster = _material(tmp_path, 101, "_course", "roster.md", "# Roster\nZephyrlens Fictionalname attends.")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    assert rag.rebuild(101) == 1
    roster.unlink()
    assert rag.rebuild(101) == 2
    assert "Zephyrlens" not in _indexed_text(tmp_path, 101)
    assert sorted(d.name for d in (tmp_path / "courses" / "101" / "index").iterdir() if d.is_dir()) == ["v2"]
    assert rag.retrieve(101, None, "Quartzzyme")  # k defaults to 4 as in the CourseRetriever protocol


def test_database_mode_keeps_the_active_version_until_prune(tmp_path):
    _material(tmp_path, 101, "_course", "syllabus.md", "# Policy\nQuartzzyme is a demo-only syllabus token.")
    authoritative = {101: 0}
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True, index_version=lambda cid: authoritative[cid])
    authoritative[101] = rag.rebuild(101)
    assert rag.rebuild(101) == 2
    assert rag.retrieve(101, None, "Quartzzyme")  # still served from v1 until the database moves on
    authoritative[101] = 2
    rag.prune(101)
    assert sorted(d.name for d in (tmp_path / "courses" / "101" / "index").iterdir() if d.is_dir()) == ["v2"]
    assert rag.retrieve(101, None, "Quartzzyme")


def test_a_database_version_ahead_of_disk_is_never_overwritten(tmp_path):
    _material(tmp_path, 101, "_course", "syllabus.md", "# Policy\nQuartzzyme is a demo-only syllabus token.")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True, index_version=lambda cid: 5)
    assert rag.rebuild(101) == 6


def test_delete_index_removes_all_indexed_text(tmp_path):
    _material(tmp_path, 101, "_course", "syllabus.md", "# Policy\nQuartzzyme is a demo-only syllabus token.")
    rag = IndexedCourseRetriever(tmp_path, scan=lambda _: True)
    rag.rebuild(101)
    rag.delete_index(101)
    assert not (tmp_path / "courses" / "101" / "index").exists()
    assert rag.retrieve(101, None, "Quartzzyme") == []
