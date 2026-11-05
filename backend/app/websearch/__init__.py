"""Web search for cloud answers that need recent information (task T13; guide rule 6).

The query always comes from `app.privacy.profiles.search_query()`; this package never sees the original
question. Z1 stand-in: `web_search` returns no passages.
"""
from app.core.schemas import Chunk


async def web_search(query: str, allowlist: list[str]) -> list[Chunk]:
    return []
