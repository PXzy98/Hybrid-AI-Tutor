"""The routing and evidence models are pinned to Hugging Face commits (bandit B615)."""
import re

from app.core.config import RoutingConfig
from app.routing import models
from app.routing.revisions import REVISIONS


def test_every_configured_model_has_a_full_commit_pin():
    cfg = RoutingConfig()
    for name in (cfg.embedding_model, cfg.relevance_model, cfg.answerability_model):
        assert re.fullmatch(r"[0-9a-f]{40}", REVISIONS.get(name, "")), name


def test_the_local_cache_is_read_at_the_pinned_commit(monkeypatch):
    seen = {}

    def fake_snapshot_download(**kwargs):
        seen.update(kwargs)
        return "/cache/snapshot"

    import huggingface_hub

    monkeypatch.setattr(huggingface_hub, "snapshot_download", fake_snapshot_download)
    name = "cross-encoder/ms-marco-MiniLM-L6-v2"
    assert models.asset_path(name, None, True) == "/cache/snapshot"
    assert seen["revision"] == REVISIONS[name] and seen["local_files_only"] is True
