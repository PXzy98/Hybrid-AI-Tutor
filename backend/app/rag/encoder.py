"""The sentence encoder of the router, reused as the semantic step of course retrieval (S14).

Same model, same local files, no download at question time: if the model is not available the embedder raises
and `IndexedCourseRetriever` falls back to lexical retrieval.
"""
import numpy as np

from app.core.config import RoutingConfig
from app.routing.models import MODEL_LOCK, sentence_encoder


def routing_embedder(cfg: RoutingConfig):
    """A function texts -> unit vectors (float32). Texts longer than the encoder's context are truncated:
    a passage is matched by its beginning, which holds its heading."""

    def embed(texts: list[str]) -> np.ndarray:
        encoder = sentence_encoder(cfg.embedding_model, cfg.model_cache_dir, cfg.local_files_only)
        with MODEL_LOCK:
            return np.asarray(encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False,
                                             batch_size=32), dtype=np.float32)

    return embed


def course_embedder(settings):
    """The embedder for course indexes, or None when `rag.semantic_retrieval` is off."""
    return routing_embedder(settings.routing) if settings.rag.semantic_retrieval else None
