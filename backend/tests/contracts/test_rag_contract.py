"""Contract for every registered retriever (Siyun's implementation is picked up automatically).

Run only these: python -m pytest tests/contracts -k rag
"""
import pytest

from app.core.registry import import_submodules, retrievers
from app.core.schemas import Chunk
from app.rag.interface import Retriever

import_submodules("app.rag")

TOPIC = "high_blood_pressure"
QUERY = "Why does salt raise blood pressure?"


@pytest.fixture(params=retrievers.names())
def retriever(request) -> Retriever:
    return retrievers.get(request.param)()


def test_implements_protocol(retriever):
    assert isinstance(retriever, Retriever)


@pytest.mark.parametrize("k", [1, 2, 4])
def test_returns_chunks_of_topic_and_respects_k(retriever, k):
    out = retriever.retrieve(QUERY, TOPIC, k=k)
    assert isinstance(out, list)
    assert len(out) <= k
    assert all(isinstance(c, Chunk) and c.topic == TOPIC for c in out)


def test_filter_matches_or_falls_back_to_topic(retriever):
    plain = retriever.retrieve(QUERY, TOPIC, k=4)
    out = retriever.retrieve(QUERY, TOPIC, k=4, kc_ids=["HBP.5"], level="basic")
    assert all(c.topic == TOPIC for c in out)
    # the filter must not make results disappear: fall back to topic-only chunks
    assert len(out) >= min(len(plain), 1)


@pytest.mark.parametrize(
    "kwargs",
    [{"kc_ids": ["NOPE.9"]}, {"level": "advanced", "kc_ids": []}, {"query": ""}, {"topic": "unknown_topic"}],
    ids=["unknown-kc", "empty-kc-list", "empty-query", "unknown-topic"],
)
def test_never_raises_on_unusual_input(retriever, kwargs):
    args = {"query": QUERY, "topic": TOPIC, "k": 4} | kwargs
    out = retriever.retrieve(**args)
    assert isinstance(out, list)
    assert all(c.topic == args["topic"] for c in out)
