"""Explicitly download encoder assets, then train any missing method weights."""

import argparse

from app.core.config import REPO_ROOT, get_settings
from app.routing.models import pair_encoder, sentence_encoder, weights_path


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing-only", action="store_true", help="Skip the two RAG evidence models")
    parser.add_argument("--retrain", action="store_true")
    args = parser.parse_args()
    cfg = get_settings().routing
    print("Preparing the local sentence encoder...")
    sentence_encoder(cfg.embedding_model, cfg.model_cache_dir, False)
    if not args.routing_only:
        for name in (cfg.relevance_model, cfg.answerability_model):
            print(f"Preparing local evidence model: {name}")
            pair_encoder(name, cfg.model_cache_dir, False)
    missing = [m for m in cfg.enabled_methods if args.retrain or not weights_path(cfg, m).exists()]
    if missing:
        from app.routing.train import train

        train(REPO_ROOT / "data/routing/seed.jsonl", missing, allow_download=True)
    print("Ready. Runtime uses cached local assets; no questions are sent to model-download services.")


if __name__ == "__main__":
    main()
