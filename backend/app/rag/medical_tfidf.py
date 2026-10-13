"""Local TF-IDF retriever adapted from the ELG5902 medical_rag_demo.

Bundled demonstration text is indexed (not medically reviewed course content).
KC/level tags are provisional automatic labels that require human review.
"""
import re
from dataclasses import dataclass
from pathlib import Path

import yaml
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import REPO_ROOT
from app.core.registry import retrievers
from app.core.schemas import Chunk, Level

RAW_DIR = REPO_ROOT / "data" / "medical_rag" / "raw"
TOPIC_FILES = {
    "high_blood_pressure": "hypertension.txt",
    "type2_diabetes": "type2_diabetes.txt",
    "asthma": "asthma.txt",
    "migraine": "migraine.txt",
    "pneumonia": "pneumonia.txt",
}
_SENTENCE_BOUNDARY = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")


@dataclass(frozen=True)
class _Passage:
    text: str
    source: str
    topic: str
    kc_ids: tuple[str, ...]
    level: Level | None


def _sentences(text: str) -> list[str]:
    clean = re.sub(r"\s+", " ", text).strip()
    return [s.strip() for s in _SENTENCE_BOUNDARY.split(clean) if len(s.strip()) >= 25]


def _document(path: Path) -> tuple[str, str]:
    lines = path.read_text(encoding="utf-8").splitlines()
    if len(lines) < 5 or not lines[2].startswith("URL:"):
        raise ValueError(f"unexpected medical source format: {path.name}")
    url = lines[2].split(":", 1)[1].strip()
    if not url.startswith("https://"):
        raise ValueError(f"medical source needs HTTPS URL: {path.name}")
    return url, "\n".join(lines[4:])


def _windows(body: str, size: int = 5, overlap: int = 2) -> list[str]:
    sentences = _sentences(body)
    step = max(1, size - overlap)
    return [" ".join(part) for i in range(0, len(sentences), step)
            if (part := sentences[i:i + size]) and len(" ".join(part)) >= 120]


def _kc_definitions(topic: str) -> list[dict]:
    path = REPO_ROOT / "content" / "topics" / topic / "kcs.yaml"
    if not path.is_file():
        return []
    kcs = yaml.safe_load(path.read_text(encoding="utf-8")).get("kcs", [])
    return [kc for kc in kcs if kc.get("id") and kc.get("difficulty") in
            {"basic", "intermediate", "advanced"}]


def _assign_tags(texts: list[str], topic: str) -> list[tuple[tuple[str, ...], Level | None]]:
    """Weak, reproducible auto-tagging; do not treat as medically reviewed."""
    kcs = _kc_definitions(topic)
    if not kcs:
        return [((), None) for _ in texts]
    descriptions = [f"{kc.get('name', '')}. {kc.get('definition', '')}" for kc in kcs]
    tfidf = TfidfVectorizer(stop_words="english", ngram_range=(1, 2), sublinear_tf=True)
    vectors = tfidf.fit_transform(texts + descriptions)
    similarities = cosine_similarity(vectors[:len(texts)], vectors[len(texts):])
    result = []
    for row in similarities:
        best = int(row.argmax())
        kc = kcs[best]
        result.append(((str(kc["id"]),), kc["difficulty"]))
    return result


@retrievers.register("medical_tfidf")
class MedicalTfidfRetriever:
    """Topic-isolated TF-IDF retrieval with KC/level preference and topic fallback."""

    def __init__(self) -> None:
        self.passages: dict[str, list[_Passage]] = {}
        self.indices: dict[str, tuple[TfidfVectorizer, object]] = {}
        for topic, filename in TOPIC_FILES.items():
            path = RAW_DIR / filename
            if not path.is_file():
                raise FileNotFoundError(f"medical RAG corpus missing: {path}")
            url, body = _document(path)
            texts = _windows(body)
            if not texts:
                raise ValueError(f"medical RAG corpus is empty: {path}")
            tags = _assign_tags(texts, topic)
            self.passages[topic] = [
                _Passage(text=text, source=url, topic=topic, kc_ids=ids, level=level)
                for text, (ids, level) in zip(texts, tags, strict=True)
            ]
            vectorizer = TfidfVectorizer(
                stop_words="english", ngram_range=(1, 2),
                sublinear_tf=True, max_df=0.98,
            )
            matrix = vectorizer.fit_transform(texts)
            self.indices[topic] = (vectorizer, matrix)

    def retrieve(
        self,
        query: str,
        topic: str,
        k: int = 4,
        kc_ids: list[str] | None = None,
        level: Level | None = None,
    ) -> list[Chunk]:
        if topic not in self.passages or k <= 0 or not query.strip():
            return []
        passages = self.passages[topic]
        vectorizer, matrix = self.indices[topic]
        scores = cosine_similarity(vectorizer.transform([query]), matrix).ravel()
        requested_kcs = set(kc_ids or [])

        def matches(passage: _Passage) -> bool:
            return ((not requested_kcs or bool(requested_kcs.intersection(passage.kc_ids)))
                    and (level is None or passage.level == level))

        ranked = sorted(range(len(passages)), key=lambda i: (-float(scores[i]), i))
        preferred = [i for i in ranked if matches(passages[i])]
        fallback = [i for i in ranked if not matches(passages[i])]
        return [
            Chunk(
                text=passages[i].text,
                source=passages[i].source,
                topic=topic,
                score=round(float(scores[i]), 6),
                kc_ids=list(passages[i].kc_ids),
                level=passages[i].level,
            )
            for i in (preferred + fallback)[:k]
        ]
