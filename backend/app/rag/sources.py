"""Where each numbered prompt passage comes from (tasks S1 and S3).

`source_positions` returns one entry per passage, in prompt order ([1], [2], ...), with the position as
numbers. API v1 is frozen (rule 15), so v1 only turns them into its English `title`; the v2 ask response
returns the numbers so the frontend translates "page" and "slide" itself.
"""
from dataclasses import dataclass
from pathlib import PurePosixPath

from app.core.schemas import Chunk


@dataclass(frozen=True)
class SourcePosition:
    source: str
    name: str  # the file name part, without the position
    page: int | None = None
    slide: int | None = None
    excerpt: int | None = None  # 2, 3, ... for further passages from the same file position
    kc_ids: tuple[str, ...] = ()

    def english_title(self) -> str:
        """The v1 title: "lecture (page 2) (excerpt 2)"."""
        title = self.name
        if self.page is not None:
            title += f" (page {self.page})"
        elif self.slide is not None:
            title += f" (slide {self.slide})"
        if self.excerpt is not None:
            title += f" (excerpt {self.excerpt})"
        return title


def _positive(value) -> int | None:
    return value if type(value) is int and value > 0 else None


def source_positions(passages: list[Chunk]) -> list[SourcePosition]:
    """One position per passage, never collapsing passages from the same file or page."""
    seen: dict[tuple[str, int | None, int | None], int] = {}
    out: list[SourcePosition] = []
    for chunk in passages:
        page = _positive(chunk.metadata.get("page"))
        slide = None if page is not None else _positive(chunk.metadata.get("slide"))
        key = (chunk.source, page, slide)
        seen[key] = seen.get(key, 0) + 1
        out.append(SourcePosition(
            source=chunk.source, name=PurePosixPath(chunk.source).stem.replace("_", " "),
            page=page, slide=slide, excerpt=seen[key] if seen[key] > 1 else None, kc_ids=tuple(chunk.kc_ids),
        ))
    return out
