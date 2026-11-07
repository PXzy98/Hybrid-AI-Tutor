"""PowerPoint teacher uploads: slide text, tables, notes, provenance and safety limits."""
from io import BytesIO
from pathlib import Path

import pytest
from PIL import Image
from pptx import Presentation

from app.rag.documents import DocumentError, extract_text
from app.rag.medical_hybrid import MedicalHybridRetriever


def _deck(path: Path) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    p = Presentation()
    slide = p.slides.add_slide(p.slide_layouts[1])
    slide.shapes.title.text = "Workshop Overview"
    slide.placeholders[1].text = "Quartzzyme is an invented method for introductory workshop discussion."

    slide = p.slides.add_slide(p.slide_layouts[5])
    slide.shapes.title.text = "Airflow Monitoring"
    table = slide.shapes.add_table(2, 2, 914400, 914400, 5200000, 1200000).table
    table.cell(0, 0).text = "Technique"
    table.cell(0, 1).text = "Description"
    table.cell(1, 0).text = "Zephyrlens"
    table.cell(1, 1).text = "Fictional airflow measurement using a labelled training meter."
    slide.notes_slide.notes_text_frame.text = (
        "Teacher notes: Astralmetric is a fictional terminology example for this lesson."
    )

    slide = p.slides.add_slide(p.slide_layouts[1])
    slide.shapes.title.text = "Review Exercises"
    slide.placeholders[1].text = "Heliometric is a fictional observation exercise for students."
    p.save(path)
    return path


def test_three_slide_text_table_and_speaker_notes_index_separately(tmp_path):
    deck = _deck(tmp_path / "asthma" / "seminar.pptx")
    text = extract_text(deck, preserve_slide_numbers=True)
    pages = text.split("\f")
    assert len(pages) == 3
    assert pages[0].startswith("# Workshop Overview")
    assert "Quartzzyme" in pages[0]
    assert pages[1].startswith("# Airflow Monitoring")
    assert "Zephyrlens" in pages[1] and "Fictional airflow measurement" in pages[1]
    assert "Astralmetric" in pages[1] and "Speaker notes:" in pages[1]
    assert "Heliometric" in pages[2]
    assert "Zephyrlens" not in pages[0] + pages[2]

    rag = MedicalHybridRetriever(tmp_path)
    status = [r for r in rag.material_status("asthma") if r["name"] == "seminar.pptx"]
    assert len(status) == 1 and status[0]["indexed"] and status[0]["passage_count"] >= 3
    for word, slide in (("Quartzzyme", 1), ("Zephyrlens", 2), ("Astralmetric", 2), ("Heliometric", 3)):
        found = [p for p in rag.retrieve(word, "asthma") if word in p.text]
        assert found and found[0].source == "course/asthma/seminar.pptx"
        assert found[0].metadata == {"origin": "uploaded", "slide": slide}
    assert not any("Zephyrlens" in p.text for p in rag.retrieve("Zephyrlens", "migraine"))


def test_blank_first_slide_does_not_shift_numbering(tmp_path):
    path = tmp_path / "asthma" / "blanks.pptx"
    path.parent.mkdir(parents=True)
    p = Presentation()
    p.slides.add_slide(p.slide_layouts[6])
    second = p.slides.add_slide(p.slide_layouts[1])
    second.shapes.title.text = "Second Slide"
    second.placeholders[1].text = "Quartzzyme appears on the second slide only."
    p.save(path)
    texts = extract_text(path, preserve_slide_numbers=True).split("\f")
    assert len(texts) == 2 and not texts[0].strip()
    retrieved = [x for x in MedicalHybridRetriever(tmp_path).retrieve("Quartzzyme", "asthma")
                 if "Quartzzyme" in x.text]
    assert retrieved and retrieved[0].metadata["slide"] == 2


def test_images_only_deck_reports_clear_error(tmp_path):
    p = Presentation()
    slide = p.slides.add_slide(p.slide_layouts[6])
    picture = BytesIO()
    Image.new("RGB", (25, 25), "white").save(picture, format="PNG")
    picture.seek(0)
    slide.shapes.add_picture(picture, 0, 0)
    path = tmp_path / "asthma" / "scanned.pptx"
    path.parent.mkdir(parents=True)
    p.save(path)
    with pytest.raises(DocumentError, match="Image-only slides"):
        extract_text(path)
    rag = MedicalHybridRetriever(tmp_path)
    row = next(x for x in rag.material_status("asthma") if x["name"] == path.name)
    assert row["indexed"] is False
    assert "Image-only" in row["message"]


def test_compressed_archive_with_excessive_unpacked_size_is_rejected(tmp_path):
    import zipfile

    path = _deck(tmp_path / "asthma" / "oversized.pptx")
    # The added entry compresses to a small archive but expands beyond the safe cap.
    with zipfile.ZipFile(path, "a", compression=zipfile.ZIP_DEFLATED) as archive:
        archive.writestr("extra-large-unpacked-test.bin", b"x" * (64 * 1024 * 1024 + 1))
    with pytest.raises(DocumentError, match="unpacked PowerPoint"):
        extract_text(path)




def test_teacher_upload_endpoint_indexes_pptx_slide_sources(make_client, tmp_path):
    from tests.conftest import Api

    deck = _deck(tmp_path / "instructor_deck.pptx")
    with make_client({"rag": {"impl": "medical_hybrid",
                             "materials_dir": str(tmp_path / "uploads")}}) as client:
        api = Api(client)
        api.make_instructor()
        api.login("prof")
        response = client.post("/api/v1/admin/topics/asthma/materials", files={
            "file": ("instructor_deck.pptx", deck.read_bytes(),
                     "application/vnd.openxmlformats-officedocument.presentationml.presentation"),
        })
        assert response.status_code == 201, response.text
        assert response.json()["ingested"] is True
        row = next(r for r in api.services.retriever.material_status("asthma")
                   if r["name"] == "instructor_deck.pptx")
        assert row["indexed"]
        hits = api.services.retriever.retrieve("Astralmetric", "asthma")
        assert any(p.metadata.get("slide") == 2 and "Astralmetric" in p.text for p in hits)


def test_upload_accepts_pptx_and_survives_retriever_restart(tmp_path):
    from app.admin.materials import clean_name

    path = _deck(tmp_path / "asthma" / "class.pptx")
    assert clean_name("class.pptx") == "class.pptx"
    rag = MedicalHybridRetriever(tmp_path)
    rag.ingest("asthma", str(path))
    restarted = MedicalHybridRetriever(tmp_path)
    found = [x for x in restarted.retrieve("Zephyrlens", "asthma") if "Zephyrlens" in x.text]
    assert found and found[0].metadata["slide"] == 2


def test_title_only_and_grouped_text_slides_are_read(tmp_path):
    from pptx.util import Inches

    p = Presentation()
    divider = p.slides.add_slide(p.slide_layouts[5])
    divider.shapes.title.text = "Week 3: Quartzzyme sampling"
    grouped = p.slides.add_slide(p.slide_layouts[6])
    box = grouped.shapes.add_group_shape().shapes.add_textbox(Inches(1), Inches(1), Inches(4), Inches(1))
    box.text_frame.text = "Zephyrlens rate is twice the fictional bandwidth."
    path = tmp_path / "grouped.pptx"
    p.save(path)
    slides = extract_text(path, preserve_slide_numbers=True).split("\f")
    assert slides == ["# Week 3: Quartzzyme sampling",
                      "# Untitled slide\nZephyrlens rate is twice the fictional bandwidth."]


def test_chart_title_series_and_categories_are_read(tmp_path):
    from pptx.chart.data import CategoryChartData
    from pptx.enum.chart import XL_CHART_TYPE
    from pptx.util import Inches

    p = Presentation()
    slide = p.slides.add_slide(p.slide_layouts[5])
    slide.shapes.title.text = "Quartzzyme results"
    data = CategoryChartData()
    data.categories = ["Week one", "Week two"]
    data.add_series("Zephyrlens score", (1.0, 2.0))
    chart = slide.shapes.add_chart(XL_CHART_TYPE.COLUMN_CLUSTERED, Inches(1), Inches(1), Inches(4), Inches(3),
                                   data).chart
    chart.has_title = True
    chart.chart_title.text_frame.text = "Fictional Heliometric trend"
    path = tmp_path / "chart.pptx"
    p.save(path)
    text = extract_text(path, preserve_slide_numbers=True)
    assert ("Chart: Fictional Heliometric trend; Series: Zephyrlens score; "
            "Categories: Week one, Week two") in text


def test_smartart_text_is_read_from_the_diagram_data_part():
    from lxml import etree

    from app.rag.documents import _smartart_text

    frame = etree.fromstring(
        '<p:graphicFrame xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<a:graphic><a:graphicData><dgm:relIds r:dm="rId9" r:lo="rId10" r:qs="rId11" r:cs="rId12"/>'
        '</a:graphicData></a:graphic></p:graphicFrame>')
    data = (b'<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
            b'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><dgm:ptLst>'
            b'<dgm:pt><dgm:t><a:p><a:r><a:t>Quartzzyme step</a:t></a:r></a:p></dgm:t></dgm:pt>'
            b'<dgm:pt><dgm:t><a:p><a:r><a:t>Zephyrlens </a:t></a:r><a:r><a:t>step</a:t></a:r></a:p>'
            b'</dgm:t></dgm:pt>'
            b'</dgm:ptLst></dgm:dataModel>')
    shape = type("Shape", (), {"shape_type": 6, "_element": frame})()
    part = type("Part", (), {"related_part": lambda self, rid: type("P", (), {"blob": data})()})()
    assert _smartart_text(shape, part) == ["Quartzzyme step", "Zephyrlens step"]


def _deck_with_smartart(path: Path) -> Path:
    """A saved deck whose slide holds a real SmartArt graphic frame linked to a diagram data part."""
    from lxml import etree
    from pptx.opc.package import Part
    from pptx.opc.packuri import PackURI

    p = Presentation()
    slide = p.slides.add_slide(p.slide_layouts[5])
    slide.shapes.title.text = "Fictional process"
    data = (b'<dgm:dataModel xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
            b'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main"><dgm:ptLst>'
            b'<dgm:pt modelId="1"><dgm:t><a:bodyPr/><a:p><a:r><a:t>Quartzzyme intake</a:t></a:r></a:p>'
            b'</dgm:t>'
            b'</dgm:pt><dgm:pt modelId="2"><dgm:t><a:bodyPr/><a:p><a:r><a:t>Zephyrlens review</a:t></a:r>'
            b'</a:p></dgm:t></dgm:pt></dgm:ptLst></dgm:dataModel>')
    part = Part(PackURI("/ppt/diagrams/data1.xml"),
                "application/vnd.openxmlformats-officedocument.drawingml.diagramData+xml",
                p.part.package, data)
    rid = slide.part.relate_to(
        part, "http://schemas.openxmlformats.org/officeDocument/2006/relationships/diagramData")
    frame = etree.fromstring(
        '<p:graphicFrame xmlns:p="http://schemas.openxmlformats.org/presentationml/2006/main" '
        'xmlns:a="http://schemas.openxmlformats.org/drawingml/2006/main" '
        'xmlns:r="http://schemas.openxmlformats.org/officeDocument/2006/relationships">'
        '<p:nvGraphicFramePr><p:cNvPr id="10" name="Diagram 1"/><p:cNvGraphicFramePr/><p:nvPr/>'
        '</p:nvGraphicFramePr><p:xfrm><a:off x="0" y="0"/><a:ext cx="100" cy="100"/></p:xfrm>'
        '<a:graphic><a:graphicData uri="http://schemas.openxmlformats.org/drawingml/2006/diagram">'
        '<dgm:relIds xmlns:dgm="http://schemas.openxmlformats.org/drawingml/2006/diagram" '
        f'r:dm="{rid}" r:lo="{rid}" r:qs="{rid}" r:cs="{rid}"/></a:graphicData></a:graphic></p:graphicFrame>')
    slide.shapes._spTree.append(frame)
    p.save(path)
    return path


def test_real_smartart_frame_is_read_although_python_pptx_gives_no_shape_type(tmp_path):
    path = _deck_with_smartart(tmp_path / "smartart.pptx")
    deck = Presentation(path)
    assert [s.shape_type for s in deck.slides[0].shapes if s.name == "Diagram 1"] == [None]
    text = extract_text(path, preserve_slide_numbers=True)
    assert "Quartzzyme intake" in text and "Zephyrlens review" in text


def test_title_only_slides_are_indexed_as_passages(tmp_path):
    p = Presentation()
    for title in ("Week 3: Quartzzyme sampling", "Week 4: Zephyrlens filters"):
        p.slides.add_slide(p.slide_layouts[5]).shapes.title.text = title
    path = tmp_path / "asthma" / "dividers.pptx"
    path.parent.mkdir(parents=True)
    p.save(path)
    rag = MedicalHybridRetriever(tmp_path)
    rag.ingest("asthma", str(path))
    found = [x for x in rag.retrieve("Zephyrlens filters", "asthma") if "Zephyrlens" in x.text]
    assert found and found[0].metadata["slide"] == 2
