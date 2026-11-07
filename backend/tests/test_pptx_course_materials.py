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
