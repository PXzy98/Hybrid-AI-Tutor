"""Local text extraction for instructor uploads; never fetch embedded URLs or run OCR."""

import zipfile
from html.parser import HTMLParser
from pathlib import Path

SUFFIXES = {".md", ".txt", ".pdf", ".html", ".htm", ".docx", ".pptx"}
MAX_FILE_BYTES = 20 * 1024 * 1024
MAX_TEXT_CHARS = 500_000
MAX_PDF_PAGES = 250


class DocumentError(ValueError):
    """Safe, teacher-visible reason a stored document is not searchable."""


class _HTMLText(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.parts = []
        self.hidden = 0

    def handle_starttag(self, tag, attrs):
        if tag in {"script", "style"}:
            self.hidden += 1
        elif tag in {"p", "div", "br", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in {"script", "style"} and self.hidden:
            self.hidden -= 1
        elif tag in {"p", "div", "li", "h1", "h2", "h3", "tr"}:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.hidden:
            self.parts.append(data)


def _decode(data: bytes) -> str:
    try:
        return data.decode("utf-16" if data.startswith((b"\xff\xfe", b"\xfe\xff")) else "utf-8-sig")
    except UnicodeError as error:
        raise DocumentError("Save text or HTML files as UTF-8 or UTF-16 and upload again.") from error


MAX_PPTX_SLIDES = 250
MAX_UNPACKED_BYTES = 64 * 1024 * 1024


def _shapes(shapes):
    """Every shape of a slide, including the shapes inside groups."""
    from pptx.enum.shapes import MSO_SHAPE_TYPE

    for shape in shapes:
        if shape.shape_type == MSO_SHAPE_TYPE.GROUP:
            yield from _shapes(shape.shapes)
        else:
            yield shape


def _chart_text(shape) -> list[str]:
    """A chart's title, series names and categories (the numbers themselves are not course text)."""
    if not getattr(shape, "has_chart", False):
        return []
    chart, parts = shape.chart, []
    if chart.has_title and chart.chart_title.has_text_frame and chart.chart_title.text_frame.text.strip():
        parts.append(chart.chart_title.text_frame.text.strip())
    try:
        plot = chart.plots[0]
        parts += [f"Series: {s.name}" for s in plot.series if s.name]
        categories = [str(c) for c in plot.categories if str(c).strip()]
        if categories:
            parts.append("Categories: " + ", ".join(categories))
    except (IndexError, KeyError, ValueError, AttributeError):
        pass
    return ["Chart: " + "; ".join(parts)] if parts else []


_DGM = "http://schemas.openxmlformats.org/drawingml/2006/diagram"
_R = "http://schemas.openxmlformats.org/officeDocument/2006/relationships"
_A = "http://schemas.openxmlformats.org/drawingml/2006/main"


def _smartart_text(shape, slide_part) -> list[str]:
    """Text of a SmartArt diagram, read from its data part (python-pptx has no SmartArt API)."""
    # python-pptx reports a SmartArt graphic frame with shape_type None, so only the XML decides.
    if not hasattr(shape, "_element"):
        return []
    rel_ids = shape._element.findall(f".//{{{_DGM}}}relIds")
    if not rel_ids:
        return []
    from lxml import etree

    texts = []
    try:
        data = slide_part.related_part(rel_ids[0].get(f"{{{_R}}}dm")).blob
        root = etree.fromstring(data, parser=etree.XMLParser(resolve_entities=False, no_network=True))
        for paragraph in root.iter(f"{{{_A}}}p"):
            text = "".join(t.text or "" for t in paragraph.iter(f"{{{_A}}}t")).strip()
            if text:
                texts.append(text)
    except (KeyError, ValueError, etree.XMLSyntaxError):
        return []
    return texts


def _slides_text(path: Path, *, numbered: bool) -> str:
    from pptx import Presentation

    # Reject archive bombs before the PowerPoint library parses its ZIP contents.
    with zipfile.ZipFile(path) as archive:
        members = archive.infolist()
        if len(members) > 10_000 or sum(member.file_size for member in members) > MAX_UNPACKED_BYTES:
            raise DocumentError("The unpacked PowerPoint presentation is too large.")
    deck = Presentation(path)
    if len(deck.slides) > MAX_PPTX_SLIDES:
        raise DocumentError("Split PowerPoint decks into at most 250 slides.")
    slides = []
    for slide in deck.slides:
        title = slide.shapes.title
        heading = title.text.strip() if title is not None else ""
        lines = []
        for shape in _shapes(slide.shapes):
            if title is not None and shape.shape_id == title.shape_id:
                continue
            if shape.has_text_frame:
                lines.extend(p.text.strip() for p in shape.text_frame.paragraphs if p.text.strip())
            lines.extend(_chart_text(shape))
            lines.extend(_smartart_text(shape, slide.part))
            if getattr(shape, "has_table", False):
                for row in shape.table.rows:
                    cells = [" ".join(cell.text.split()) for cell in row.cells]
                    if any(cells):
                        lines.append(" | ".join(cells))
        if slide.has_notes_slide and slide.notes_slide.notes_text_frame is not None:
            notes = slide.notes_slide.notes_text_frame.text.strip()
            if notes:
                lines.append("Speaker notes: " + notes)
        # Preserve blank slides so their physical number does not shift citations; a title-only slide
        # (a section divider) keeps its title.
        slides.append("\n".join(["# " + (heading or "Untitled slide")] + lines) if lines or heading else "")
    if not any(slide.strip() for slide in slides):
        raise DocumentError("No readable text was found. Image-only slides need text or speaker notes.")
    return ("\f" if numbered else "\n").join(slides)


def extract_text(path: Path, *, preserve_pdf_pages: bool = False,
                 preserve_slide_numbers: bool = False) -> str:
    """Extract readable text. An optional form-feed separates PDF pages for citation metadata.

    The default is unchanged for administrative validation and other callers.
    Page separators are never indexed as text by the medical retriever.
    """
    if path.suffix.lower() not in SUFFIXES:
        raise DocumentError("This file type is not supported for retrieval.")
    if path.stat().st_size > MAX_FILE_BYTES:
        raise DocumentError("The file exceeds the 20 MB limit.")
    try:
        suffix = path.suffix.lower()
        if suffix == ".pdf":
            from pypdf import PdfReader

            reader = PdfReader(path)
            if reader.is_encrypted:
                raise DocumentError("Remove PDF password protection before uploading.")
            if len(reader.pages) > MAX_PDF_PAGES:
                raise DocumentError("Split PDFs into documents of at most 250 pages.")
            parts, count = [], 0
            for page in reader.pages:
                text = page.extract_text() or ""
                count += len(text)
                if count > MAX_TEXT_CHARS:
                    raise DocumentError("Split documents with more than 500,000 extracted characters.")
                parts.append(text.replace("\f", " "))
            text = ("\f" if preserve_pdf_pages else "\n").join(parts)
        elif suffix == ".pptx":
            text = _slides_text(path, numbered=preserve_slide_numbers)
        elif suffix == ".docx":
            from docx import Document

            with zipfile.ZipFile(path) as archive:
                if sum(i.file_size for i in archive.infolist()) > 64 * 1024 * 1024:
                    raise DocumentError("The unpacked Word document is too large.")
            document = Document(path)
            # Preserve Word heading styles so the course chunker can split sections.
            parts = [("# " if p.style and p.style.name.lower().startswith("heading") else "") + p.text
                     for p in document.paragraphs]
            parts.extend("\t".join(cell.text for cell in row.cells)
                         for table in document.tables for row in table.rows)
            text = "\n".join(parts)
        else:
            text = _decode(path.read_bytes())
            if suffix in {".html", ".htm"}:
                parser = _HTMLText()
                parser.feed(text)
                parser.close()
                text = "".join(parser.parts)
    except DocumentError:
        raise
    except ImportError as error:
        raise DocumentError("Install backend dependencies and restart to read this format.") from error
    except Exception as error:
        raise DocumentError("This document could not be read. Check the file and upload it again.") from error
    if "\0" in text:
        raise DocumentError("The document contains binary data instead of readable text.")
    # Keep leading form-feeds: blank first pages/slides must not shift source numbers.
    numbered = (preserve_pdf_pages and path.suffix.lower() == ".pdf") or (
        preserve_slide_numbers and path.suffix.lower() == ".pptx"
    )
    text = text.strip(" \r\n\t") if numbered else text.strip()
    if not text.replace("\f", "").strip():
        raise DocumentError("No readable text was found. Scanned PDFs require OCR before uploading.")
    if len(text.replace("\f", "")) > MAX_TEXT_CHARS:
        raise DocumentError("Split documents with more than 500,000 extracted characters.")
    return text
