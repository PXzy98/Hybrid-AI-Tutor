"""The prompt [n] references and returned Sources list use the same order."""
from app.api.v1.ask import _sources
from app.core.schemas import Chunk, RequestContext
from app.prompts.render import material_block


def _passage(text, source, *, page=None, slide=None):
    metadata = {}
    if page is not None:
        metadata["page"] = page
    if slide is not None:
        metadata["slide"] = slide
    return Chunk(text=text, source=source, topic="asthma", score=1, metadata=metadata)


def test_duplicate_page_passages_keep_all_citation_numbers_and_unique_titles():
    chunks = [
        _passage("Quartzzyme first passage", "course/asthma/lecture.pdf", page=2),
        _passage("Zephyrlens second passage", "course/asthma/lecture.pdf", page=2),
        _passage("Astralmetric third passage", "course/asthma/deck.pptx", slide=3),
        _passage("Heliometric fourth passage", "https://medlineplus.gov/asthma.html"),
    ]
    ctx = RequestContext.model_construct(passages=chunks)
    sources = _sources(ctx)
    assert len(sources) == len(chunks) == 4
    assert [s.title for s in sources] == [
        "lecture (page 2)", "lecture (page 2) (excerpt 2)", "deck (slide 3)", "asthma",
    ]
    assert len({(s.source, s.title) for s in sources}) == len(sources)
    # S1: the position is also returned as numbers for the frontend to translate
    assert [(s.name, s.page, s.slide, s.excerpt) for s in sources] == [
        ("lecture", 2, None, None), ("lecture", 2, None, 2), ("deck", None, 3, None),
        ("asthma", None, None, None),
    ]
    prompt = material_block([c.text for c in chunks])
    for n, chunk in enumerate(chunks, 1):
        assert f"[{n}] {chunk.text}" in prompt
        assert sources[n - 1].source == chunk.source


def test_no_material_has_no_sources_or_phantom_citations():
    assert _sources(RequestContext.model_construct(passages=[])) == []
    text = material_block([])
    assert "none was found" in text and "[1]" not in text


def test_one_page_keeps_existing_title_and_ignores_invalid_numbers():
    sources = _sources(RequestContext.model_construct(passages=[
        _passage("A", "course/asthma/module.pdf", page=2),
        _passage("B", "course/asthma/notes.pptx", slide=-5),
    ]))
    assert sources[0].title == "module (page 2)"
    assert sources[1].title == "notes"
