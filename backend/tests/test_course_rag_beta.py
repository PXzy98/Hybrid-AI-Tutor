"""Beta course materials: titled lectures, PDF page citations, and labelled retrieval."""
import csv
import importlib.util
from pathlib import Path

import pytest

from app.api.v1.ask import _sources
from app.core.schemas import RequestContext
from app.rag.documents import extract_text
from app.rag.medical_hybrid import MedicalHybridRetriever, _segments

ROOT = Path(__file__).resolve().parents[2]


def _pdf(path: Path, pages: list[tuple[str, str]]) -> None:
    """Tiny standards-based PDF: no extra fixture-generation dependency."""
    path.parent.mkdir(parents=True, exist_ok=True)
    kids = " ".join(f"{4 + 2 * n} 0 R" for n in range(len(pages)))
    objects = [
        b"<< /Type /Catalog /Pages 2 0 R >>",
        f"<< /Type /Pages /Kids [{kids}] /Count {len(pages)} >>".encode(),
        b"<< /Type /Font /Subtype /Type1 /BaseFont /Helvetica >>",
    ]
    for n, (title, body) in enumerate(pages):
        stream = (f"BT /F1 12 Tf 40 700 Td ({title}) Tj "
                  f"0 -18 Td ({body}) Tj ET").encode("ascii")
        objects.extend([
            (f"<< /Type /Page /Parent 2 0 R /MediaBox [0 0 900 800] "
             f"/Resources << /Font << /F1 3 0 R >> >> /Contents {5 + 2 * n} 0 R >>").encode(),
            f"<< /Length {len(stream)} >>\nstream\n".encode() + stream + b"\nendstream",
        ])
    data, offsets = bytearray(b"%PDF-1.4\n"), [0]
    for n, obj in enumerate(objects, 1):
        offsets.append(len(data))
        data.extend(f"{n} 0 obj\n".encode() + obj + b"\nendobj\n")
    xref = len(data)
    data.extend(f"xref\n0 {len(objects) + 1}\n0000000000 65535 f \n".encode())
    for offset in offsets[1:]:
        data.extend(f"{offset:010} 00000 n \n".encode())
    data.extend(f"trailer\n<< /Size {len(objects) + 1} /Root 1 0 R >>\n"
                f"startxref\n{xref}\n%%EOF\n".encode())
    path.write_bytes(data)


def test_markdown_and_numbered_course_headings_are_separate_sections():
    text = (
        "# Introduction\nAirway lecture describes the first fictional procedure in detail.\n"
        "2. Follow Up Plan\nZephyrlens lecture describes another fictional procedure in detail.\n"
    )
    parts = _segments(text, course_headings=True)
    assert [name for name, _ in parts] == ["Introduction", "2. Follow Up Plan"]
    assert "Zephyrlens" not in " ".join(parts[0][1])
    assert "Zephyrlens" in " ".join(parts[1][1])
    # The five bundled MedlinePlus documents retain their original heading parser.
    assert _segments(text) != parts


def test_multpage_pdf_is_searchable_and_source_title_has_page(tmp_path):
    path = tmp_path / "asthma" / "module.pdf"
    _pdf(path, [
        ("1. Basics", "First page covers fictional Quartzzyme airway practice for students."),
        ("2. Care", "Second page defines Zephyrlens airway monitoring for nurses."),
    ])
    pages = extract_text(path, preserve_pdf_pages=True).split("\f")
    assert len(pages) == 2
    rag = MedicalHybridRetriever(tmp_path)
    rows = [row for row in rag.material_status("asthma") if row["origin"] == "uploaded"]
    assert len(rows) == 1 and rows[0]["indexed"]
    hits = rag.retrieve("Zephyrlens airway monitoring", "asthma")
    matching = [p for p in hits if "Zephyrlens" in p.text]
    assert matching and matching[0].metadata["page"] == 2
    assert matching[0].source == "course/asthma/module.pdf"
    ctx = RequestContext.model_construct(passages=matching)
    assert _sources(ctx)[0].title == "module (page 2)"
    assert not any("Zephyrlens" in p.text for p in rag.retrieve("Zephyrlens", "migraine"))


def test_pdf_blank_first_page_preserves_page_number(tmp_path):
    path = tmp_path / "asthma" / "blank.pdf"
    _pdf(path, [
        ("", ""),
        ("2. Lecture", "Second page covers Zephyrlens and oxygen lecture evidence."),
    ])
    r = MedicalHybridRetriever(tmp_path)
    matches = [p for p in r.retrieve("Zephyrlens oxygen lecture", "asthma")
               if "Zephyrlens" in p.text]
    assert matches and matches[0].metadata["page"] == 2


def test_docx_heading_styles_are_preserved_and_chunked(tmp_path):
    from docx import Document

    path = tmp_path / "asthma" / "seminar.docx"
    path.parent.mkdir(parents=True)
    doc = Document()
    doc.add_heading("Overview", level=1)
    doc.add_paragraph("Quartzzyme gives a fictional overview of airway care for learners.")
    doc.add_heading("Follow Up", level=2)
    doc.add_paragraph("Zephyrlens is the fictional follow-up method in these notes.")
    doc.save(path)
    r = MedicalHybridRetriever(tmp_path)
    passages = [p.text for p in r.indices["asthma"].passages if p.source.endswith("seminar.docx")]
    assert len(passages) == 2
    assert passages[0].startswith("Overview")
    assert passages[1].startswith("Follow Up")
    assert "Zephyrlens" not in passages[0]


def test_pdf_page_citation_flows_from_teacher_upload_to_student_api(make_client, monkeypatch, tmp_path):
    import numpy as np

    from tests.conftest import Api
    from tests.test_semantic_rag_integration import config, configure_classifier

    configure_classifier(monkeypatch)
    monkeypatch.setattr(
        "app.routing.evidence.pair_scores",
        lambda name, pairs, cfg: np.full(len(pairs), 0.99),
    )
    settings = config()
    settings["rag"]["materials_dir"] = str(tmp_path / "uploads")
    pdf = tmp_path / "input.pdf"
    _pdf(pdf, [
        ("1. Intro", "Quartzzyme teaches a fictional overview of breathing exercises."),
        ("2. Care", "Zephyrlens means a fictional airway monitoring procedure for students."),
    ])
    with make_client(settings) as client:
        api = Api(client)
        api.make_instructor()
        api.make_student()
        api.login("prof")
        upload = client.post("/api/v1/admin/topics/asthma/materials", files={
            "file": ("module.pdf", pdf.read_bytes(), "application/pdf"),
        })
        assert upload.status_code == 201 and upload.json()["ingested"] is True, upload.text
        api.login("alice")
        response = client.post("/api/v1/ask", json={
            "topic": "asthma",
            "question": "What is Zephyrlens airway monitoring in our lecture?",
        })
        assert response.status_code == 200, response.text
        assert any(
            source["title"] == "module (page 2)" and source["source"] == "course/asthma/module.pdf"
            for source in response.json()["sources"]
        ), response.json()["sources"]


def _benchmark():
    spec = importlib.util.spec_from_file_location(
        "course_rag_benchmark", ROOT / "eval" / "course_rag_benchmark.py"
    )
    assert spec and spec.loader
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_course_benchmark_supports_multiple_gold_and_negative_queries(tmp_path):
    folder = tmp_path / "materials" / "asthma"
    folder.mkdir(parents=True)
    (folder / "notes.md").write_text(
        "# First Topic\nQuartzzyme means the fictional airway care protocol for our workshop.\n"
        "# Second Topic\nZephyrlens describes the fictional airway measurement protocol for our workshop.",
        encoding="utf-8",
    )
    labels = tmp_path / "gold.csv"
    with labels.open("w", encoding="utf-8", newline="") as handle:
        writer = csv.writer(handle)
        writer.writerow(["id", "topic", "query", "gold_source", "gold_anchor"])
        writer.writerow(["q1", "asthma", "What does quartzzyme mean in workshop?",
                         "course/asthma/notes.md", "Quartzzyme means"])
        writer.writerow(["q2", "asthma", "zzzzzxxyyzznotreal", "", ""])
    output = _benchmark().evaluate(tmp_path / "materials", labels)
    m = output["metrics"]
    assert m["total_questions"] == 2 and m["labelled_questions"] == 1
    assert m["negative_questions"] == 1 and m["recall_at_1"] == pytest.approx(1.0)
    assert m["negative_abstention"] == pytest.approx(1.0)
    assert m["precision_at_k"] == pytest.approx(0.25)
    assert m["source_traceability"] == pytest.approx(1.0)
    assert any(r["indexed"] for r in output["material_status"]["asthma"])
    assert not (tmp_path / "materials" / "asthma" / "results.json").exists()


def test_course_benchmark_rejects_missing_or_ambiguous_gold(tmp_path):
    folder = tmp_path / "asthma"
    folder.mkdir(parents=True)
    (folder / "lecture.txt").write_text("Quartzzyme useful example in workshop.", encoding="utf-8")
    labels = tmp_path / "gold.csv"
    labels.write_text("id,topic,query,gold_source,gold_anchor\n", encoding="utf-8")
    with pytest.raises(ValueError, match="No labelled questions"):
        _benchmark().evaluate(tmp_path, labels)
    with labels.open("a", encoding="utf-8") as f:
        f.write("q1,asthma,quartzzyme,course/asthma/lecture.txt,NONEXISTENT\n")
    with pytest.raises(ValueError, match="matches 0 indexed chunks"):
        _benchmark().evaluate(tmp_path, labels)
