"""Fail-closed Z11 privacy scanner bridge tests, all data fictional."""
import pytest

from app.privacy.profiles import ScanFinding, ScanResult, privacy_profile
from app.rag.course_retriever import IndexedCourseRetriever
from app.rag.documents import DocumentError
from app.rag.privacy_adapter import privacy_scan_callback


def _material(root):
    path = root / "courses" / "101" / "materials" / "_course" / "demo.md"
    path.parent.mkdir(parents=True)
    path.write_text("Quartzzyme is an imaginary course policy.", encoding="utf-8")


def test_z1_scanner_stub_cannot_publish(tmp_path):
    _material(tmp_path)
    cb = privacy_scan_callback(privacy_profile("ece"))
    assert not cb("fictional document")
    with pytest.raises(DocumentError, match="Privacy scan rejected"):
        IndexedCourseRetriever(tmp_path, scan=cb).rebuild(101)
    assert not (tmp_path / "courses" / "101" / "index" / "current.json").exists()


@pytest.mark.parametrize("scan_result", [
    ScanResult(scanned=False),
    ScanResult(scanned=True, findings=(ScanFinding("STUDENT_ID", 1),)),
    ScanResult(scanned=False, findings=(ScanFinding("PERSON", 1),)),
    True,
])
def test_unscanned_sensitive_or_malformed_result_rejected(scan_result):
    callback = privacy_scan_callback(
        privacy_profile("general"), scanner=lambda text, profile: scan_result,
    )
    assert callback("imaginary source") is False


def test_scanner_exception_cannot_publish_or_leak_source():
    def erroring(text, profile):
        raise RuntimeError("private source should never be logged")
    cb = privacy_scan_callback(privacy_profile("ece"), scanner=erroring)
    assert cb("private source text") is False


def test_explicit_completed_clean_scan_allows_fictional_index(tmp_path):
    _material(tmp_path)
    cb = privacy_scan_callback(
        privacy_profile("general"),
        scanner=lambda text, profile: ScanResult(scanned=True),
    )
    rag = IndexedCourseRetriever(tmp_path, scan=cb)
    assert rag.rebuild(101) == 1
    assert rag.retrieve(101, None, "Quartzzyme", 4)
