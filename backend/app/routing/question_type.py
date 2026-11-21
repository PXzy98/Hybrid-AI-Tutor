"""Question type head (T5): course logistics (deadlines, grading, schedule, policies) vs concept.

A small logistic-regression head on the same local sentence embedding the router already computes. It lives in
its own weight file next to the routing models and never changes a route decision: it only sets
`SemanticAnalysis.question_kind`, which later steps use (logistics skips personalization and prefers the
course-level files). Without the file, or with weights of another encoder, every question is a concept
question. Train it with `python -m app.routing.question_type_train`.
"""
import json
from functools import lru_cache
from pathlib import Path
from typing import Literal

import numpy as np

from app.core.config import RoutingConfig
from app.routing.models import model_dir, type_dir

QuestionKind = Literal["concept", "logistics"]
WEIGHTS_NAME = "question_type.npz"
SCHEMA_VERSION = 1


def weights_path(cfg: RoutingConfig, course_type: str | None = None) -> Path:
    """The course type's own head when it has one (V19, `<model_dir>/<type>/`), otherwise the shared one."""
    folder = type_dir(cfg, course_type)
    if folder is not None and (folder / WEIGHTS_NAME).is_file():
        return folder / WEIGHTS_NAME
    return model_dir(cfg) / WEIGHTS_NAME


@lru_cache(maxsize=4)
def _load(path: str, modified_ns: int, size: int):
    del modified_ns, size  # part of the cache key so retraining takes effect
    with np.load(path, allow_pickle=False) as file:
        arrays = {k: file[k].copy() for k in file.files if k != "metadata"}
        metadata = json.loads(str(file["metadata"]))
    return metadata, arrays


def load_weights(cfg: RoutingConfig, course_type: str | None = None):
    path = weights_path(cfg, course_type)
    stat = path.stat()
    metadata, arrays = _load(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if (metadata.get("schema_version") != SCHEMA_VERSION
            or metadata.get("embedding_model") != cfg.embedding_model):
        raise ValueError("question type weights and configured encoder do not match")
    return metadata, arrays


def logistics_probability(vector: np.ndarray, metadata: dict, arrays: dict) -> float:
    if vector.shape != (metadata["dimension"],) or not np.isfinite(vector).all():
        raise ValueError("invalid semantic embedding")
    z = float(arrays["coef"] @ vector + arrays["intercept"][0])
    return float(1 / (1 + np.exp(-np.clip(z, -50, 50))))


def classify(vector: np.ndarray, cfg: RoutingConfig, course_type: str | None = None) -> QuestionKind:
    """The kind of the question with this embedding; "concept" whenever the head is missing or unusable."""
    try:
        metadata, arrays = load_weights(cfg, course_type)
        p = logistics_probability(vector, metadata, arrays)
    except (OSError, ValueError, KeyError, TypeError):
        return "concept"
    return "logistics" if p >= metadata.get("threshold", 0.5) else "concept"
