"""Local encoder assets and portable classifier weights. No student-time downloads.

Run `python -m app.routing.prepare` once before using the semantic router.
No generative LLM is used to classify questions or grade evidence.
"""

import json
from functools import lru_cache
from pathlib import Path
from threading import RLock

import numpy as np

from app.core.config import REPO_ROOT, RoutingConfig

MODEL_LOCK = RLock()
HEADS = ("cloud_required", "requires_evidence", "requires_fresh_evidence")


def asset_path(name: str, cache_dir: str | None, local_only: bool) -> str:
    if Path(name).is_dir() or not local_only:
        return name
    from huggingface_hub import snapshot_download

    # Passing a resolved local directory also prevents optional Hub metadata
    # lookups by downstream libraries during student requests.
    return snapshot_download(repo_id=name, cache_dir=cache_dir, local_files_only=True)


def weights_path(cfg: RoutingConfig, method: str) -> Path:
    base = Path(cfg.model_dir)
    return (base if base.is_absolute() else REPO_ROOT / base) / f"semantic_{method}.npz"


@lru_cache(maxsize=4)
def sentence_encoder(name: str, cache_dir: str | None, local_only: bool):
    import torch
    from sentence_transformers import SentenceTransformer

    # Small CPU encoders are slower with dozens of BLAS threads.
    torch.set_num_threads(2)
    with MODEL_LOCK:
        return SentenceTransformer(
            asset_path(name, cache_dir, local_only),
            cache_folder=cache_dir,
            device="cpu",
            local_files_only=local_only,
            trust_remote_code=False,
        )


@lru_cache(maxsize=4)
def pair_encoder(name: str, cache_dir: str | None, local_only: bool):
    import torch
    from sentence_transformers import CrossEncoder

    torch.set_num_threads(2)
    with MODEL_LOCK:
        return CrossEncoder(
            asset_path(name, cache_dir, local_only),
            device="cpu",
            max_length=512,
            cache_folder=cache_dir,
            local_files_only=local_only,
            trust_remote_code=False,
        )


def encode(texts: list[str], cfg: RoutingConfig, *, allow_download: bool = False) -> np.ndarray:
    encoder = sentence_encoder(
        cfg.embedding_model, cfg.model_cache_dir, False if allow_download else cfg.local_files_only
    )
    lengths = [len(encoder.tokenizer.encode(t, add_special_tokens=True)) for t in texts]
    if any(n > encoder.max_seq_length for n in lengths):
        # Never silently lose the final constraints of a long clinical scenario.
        raise ValueError("semantic encoder context exceeded")
    with MODEL_LOCK:
        return np.asarray(
            encoder.encode(texts, normalize_embeddings=True, show_progress_bar=False, batch_size=32),
            dtype=np.float32,
        )


def pair_scores(name: str, pairs: list[tuple[str, str]], cfg: RoutingConfig) -> np.ndarray:
    if not pairs:
        return np.zeros(0, dtype=np.float32)
    import torch

    model = pair_encoder(name, cfg.model_cache_dir, cfg.local_files_only)
    if any(len(model.tokenizer.encode(a, b, add_special_tokens=True)) > 512 for a, b in pairs):
        raise ValueError("evidence pair exceeds verification context")
    # Explicit sigmoid: MS MARCO's raw outputs are logits, NOT probabilities.
    with MODEL_LOCK:
        out = model.predict(
            pairs,
            activation_fn=torch.nn.Sigmoid(),
            show_progress_bar=False,
            batch_size=16,
            convert_to_numpy=True,
        )
    result = np.asarray(out, dtype=np.float64).reshape(-1)
    if len(result) != len(pairs) or not np.isfinite(result).all():
        raise ValueError("invalid evidence model output")
    return result


@lru_cache(maxsize=8)
def _load_weights(path: str, modified_ns: int, size: int):
    del modified_ns, size  # included in cache key so retraining takes effect
    with np.load(path, allow_pickle=False) as file:
        arrays = {k: file[k].copy() for k in file.files if k != "metadata"}
        metadata = json.loads(str(file["metadata"]))
    return metadata, arrays


def load_weights(cfg: RoutingConfig, method: str):
    path = weights_path(cfg, method)
    stat = path.stat()
    metadata, arrays = _load_weights(str(path.resolve()), stat.st_mtime_ns, stat.st_size)
    if metadata["embedding_model"] != cfg.embedding_model or metadata["method"] != method:
        raise ValueError("weights and configured encoder/method do not match")
    if metadata.get("schema_version") != 1:
        raise ValueError("unsupported routing weight format")
    return metadata, arrays


def predict_heads(vector: np.ndarray, metadata: dict, arrays: dict) -> dict[str, float]:
    if vector.shape != (metadata["dimension"],) or not np.isfinite(vector).all():
        raise ValueError("invalid semantic embedding")
    result = {}
    for head in HEADS:
        decision = arrays[f"{head}_coef"] @ vector + arrays[f"{head}_intercept"]
        z = arrays[f"{head}_a"] * decision + arrays[f"{head}_b"]
        result[head] = float(np.mean(1 / (1 + np.exp(np.clip(z, -50, 50)))))
    result["nearest_similarity"] = float(np.clip(np.max(arrays["prototypes"] @ vector), -1, 1))
    return result
