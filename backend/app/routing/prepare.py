"""Explicitly download encoder assets, then train any missing method weights.

`--check` downloads nothing: it loads every configured asset from the local cache and exits non-zero if one
is missing (the Docker build and CI run it, so an image never ships without its routing or evidence models).
"""

import argparse
import sys

from app.core.config import REPO_ROOT, get_settings
from app.routing.models import load_weights, pair_encoder, sentence_encoder, weights_path


def check() -> int:
    cfg = get_settings().routing
    problems = []
    names = [cfg.embedding_model, cfg.relevance_model, cfg.answerability_model]
    for n, name in enumerate(names):
        try:
            (sentence_encoder if n == 0 else pair_encoder)(name, cfg.model_cache_dir, True)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{name}: {type(e).__name__}")
    for method in cfg.enabled_methods:
        try:
            load_weights(cfg, method)
        except Exception as e:  # noqa: BLE001
            problems.append(f"{weights_path(cfg, method)}: {type(e).__name__}")
    for p in problems:
        print(f"missing: {p}", file=sys.stderr)
    if not problems:
        methods = ", ".join(cfg.enabled_methods)
        print(f"Routing and evidence models ready ({', '.join(names)}; methods: {methods}).")
    return 1 if problems else 0


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--routing-only", action="store_true", help="Skip the two RAG evidence models")
    parser.add_argument("--retrain", action="store_true")
    parser.add_argument("--check", action="store_true", help="Only verify the local assets; no downloads")
    args = parser.parse_args()
    if args.check:
        sys.exit(check())
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
