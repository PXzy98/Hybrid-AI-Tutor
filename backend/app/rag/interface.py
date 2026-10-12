"""RAG retrieval: black box owned by Siyun. Only this interface is fixed here (design §4.2, §9)."""
from typing import Protocol, runtime_checkable

from app.core.schemas import Chunk, Level


@runtime_checkable
class Retriever(Protocol):
    """Implementations are classes with a no-argument constructor, registered with
    `@retrievers.register("<name>")` and selected by `rag.impl` in config.yaml.

    `retrieve` must be synchronous and:
    - return at most `k` chunks, all with `topic == topic`;
    - when `kc_ids` and/or `level` are given, prefer chunks that match them, and fall back to
      topic-only results when the filter finds too few (never return nothing just because of the filter);
    - never raise on an unknown KC or topic (return what it can, possibly []).

    Implementations may also provide `ingest(topic: str, path: str) -> None` (used by Step 13).
    """

    def retrieve(
        self,
        query: str,
        topic: str,
        k: int = 4,
        kc_ids: list[str] | None = None,
        level: Level | None = None,
    ) -> list[Chunk]: ...
