"""Pinned Hugging Face commits of the routing and evidence models (bandit B615).

Every download (`python -m app.routing.prepare`, the Docker build) and every load from the local cache uses
these commits, so a changed model on the Hub never reaches the app unnoticed. To move to a newer model
version: put its commit here, run `python -m app.routing.prepare`, re-run the routing evaluation.
A model that is not listed (a local folder, or a name set in config.yaml without a pin) loads without one.

No imports on purpose: the Docker build reads this file before the application code is copied.
"""
REVISIONS = {
    "sentence-transformers/all-MiniLM-L6-v2": "1110a243fdf4706b3f48f1d95db1a4f5529b4d41",
    "cross-encoder/ms-marco-MiniLM-L6-v2": "233902d25c440f23af6f7d6e94d2946bac0bee0a",
    "cross-encoder/qnli-electra-base": "c7dea87c98b2269a935686c31336e97e837cbbeb",
}
