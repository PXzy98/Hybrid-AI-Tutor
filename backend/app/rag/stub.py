import json
import re
from pathlib import Path

from app.core.config import REPO_ROOT
from app.core.registry import retrievers
from app.core.schemas import Chunk, Level

FIXTURE = REPO_ROOT / "data" / "synthetic" / "rag_fixture.jsonl"
_WORD = re.compile(r"[a-z0-9]+")


@retrievers.register("stub")
class StubRetriever:
    """Returns no passages. Used until the real retriever exists."""

    def retrieve(self, query: str, topic: str, k: int = 4, kc_ids: list[str] | None = None,
                 level: Level | None = None) -> list[Chunk]:
        return []


@retrievers.register("fixture")
class FixtureRetriever:
    """Keyword retrieval over a few synthetic placeholder chunks, for development and tests.

    It follows the full retriever contract (KC/level filter with topic fallback), so it doubles as a
    reference implementation of the interface.
    """

    def __init__(self, path: Path = FIXTURE) -> None:
        self.chunks = [Chunk(**json.loads(line)) for line in path.read_text(encoding="utf-8").splitlines()
                       if line.strip()]

    def retrieve(self, query: str, topic: str, k: int = 4, kc_ids: list[str] | None = None,
                 level: Level | None = None) -> list[Chunk]:
        q = set(_WORD.findall(query.lower()))

        def ranked(chunks: list[Chunk]) -> list[Chunk]:
            scored = [c.model_copy(update={"score": round(len(q & set(_WORD.findall(c.text.lower())))
                                                          / (len(q) or 1), 4)}) for c in chunks]
            return sorted(scored, key=lambda c: -c.score)  # stable: ties keep file order

        pool = [c for c in self.chunks if c.topic == topic]
        matched = [c for c in pool
                   if (not kc_ids or set(kc_ids) & set(c.kc_ids)) and (level is None or c.level == level)]
        rest = [c for c in pool if c not in matched]
        # filter matches first; top up with topic-only results instead of returning too few
        return (ranked(matched) + ranked(rest))[:k]
