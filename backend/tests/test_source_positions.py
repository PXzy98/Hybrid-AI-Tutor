"""S1: source positions are numbers, so the frontend can translate "page" and "slide"."""
from app.core.schemas import Chunk
from app.rag.sources import source_positions


def _chunk(source, **metadata):
    return Chunk(text="Quartzzyme fictional passage", source=source, topic="t", score=1, metadata=metadata)


def test_positions_are_numbers_and_repeated_positions_count_as_excerpts():
    positions = source_positions([
        _chunk("course/1/_course/lecture.pdf", page=2),
        _chunk("course/1/_course/lecture.pdf", page=2),
        _chunk("course/1/3/deck.pptx", slide=4),
        _chunk("course/1/3/notes.pptx", slide=-1),
    ])
    assert [(p.name, p.page, p.slide, p.excerpt) for p in positions] == [
        ("lecture", 2, None, None), ("lecture", 2, None, 2), ("deck", None, 4, None),
        ("notes", None, None, None),
    ]
    assert [p.english_title() for p in positions] == [
        "lecture (page 2)", "lecture (page 2) (excerpt 2)", "deck (slide 4)", "notes",
    ]
