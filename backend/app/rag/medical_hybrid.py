"""Section-aware, fully local hybrid retrieval of bundled medical source snapshots.

This is an experimental research baseline, not reviewed clinical course content.
"""
import csv
import hashlib
import math
import re
from collections import Counter
from dataclasses import dataclass

import numpy as np
from sklearn.feature_extraction.text import ENGLISH_STOP_WORDS, TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

from app.core.config import REPO_ROOT
from app.core.registry import retrievers
from app.core.schemas import Chunk, Level
from app.rag.medical_tfidf import RAW_DIR, TOPIC_FILES, _assign_tags, _document, _kc_definitions

_HEADING = re.compile(r"^(?:what|who|why|how|when|where|which|can|does|do|are|is|should)\b.{0,115}\?$", re.I)
_SENTENCE = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9])")
_WORD = re.compile(r"[a-z0-9]+")
_MAX_CHARS = 750
_STOP = ENGLISH_STOP_WORDS
REVIEWED_TAGS_PATH = REPO_ROOT / "data" / "medical_rag" / "reviewed_tags.csv"


def _segments(body: str) -> list[tuple[str, list[str]]]:
    """Split source document into headed sections; preserve short bullet/list lines."""
    sections: list[tuple[str, list[str]]] = []
    heading = "Overview"
    items: list[str] = []
    for raw in body.splitlines():
        line = " ".join(raw.split())
        if not line:
            continue
        if _HEADING.fullmatch(line):
            if items:
                sections.append((heading, items))
            heading, items = line, []
            continue
        if len(line) <= 400:
            items.append(line)
        else:
            items.extend(part.strip() for part in _SENTENCE.split(line) if part.strip())
    if items:
        sections.append((heading, items))
    return sections


def _chunk_section(heading: str, items: list[str]) -> list[str]:
    """Pack lines by characters, retaining section headings and one-line overlap."""
    output = []
    i = 0
    while i < len(items):
        start = i
        total = len(heading) + 2
        while i < len(items) and (total + len(items[i]) + 2 <= _MAX_CHARS or i == start):
            total += len(items[i]) + 2
            i += 1
        passage = heading + "\n" + "\n".join(items[start:i])
        if len(passage) >= 45:
            output.append(passage)
        if i < len(items):
            i = max(start + 1, i - 1)
    return output


def _terms(s: str) -> list[str]:
    return [w for w in _WORD.findall(s.lower()) if w not in _STOP]


def _chunk_id(topic: str, source: str, text: str) -> str:
    return hashlib.sha256(f"{topic}|{source}|{text}".encode()).hexdigest()[:16]


def _approved_overrides() -> dict[tuple[str, str], tuple[list[str], Level]]:
    """Only explicitly approved, version-matched KC labels replace candidate tags."""
    if not REVIEWED_TAGS_PATH.is_file():
        return {}
    output = {}
    with REVIEWED_TAGS_PATH.open(encoding="utf-8-sig", newline="") as stream:
        for row in csv.DictReader(stream):
            if (row.get("review_status") or "").strip().lower() != "approved":
                continue
            topic = (row.get("topic") or "").strip()
            fingerprint = (row.get("chunk_id") or "").strip()
            reviewer = (row.get("reviewer") or "").strip()
            ids = [x.strip() for x in (row.get("reviewed_kc_ids") or "").split(";") if x.strip()]
            level = (row.get("reviewed_level") or "").strip()
            allowed = {kc["id"] for kc in _kc_definitions(topic)}
            if not reviewer or not fingerprint or not ids or not set(ids) <= allowed or level not in {
                "basic", "intermediate", "advanced"
            }:
                raise ValueError(f"invalid approved RAG tag override for topic {topic!r}")
            key = (topic, fingerprint)
            if key in output:
                raise ValueError(f"duplicate reviewed RAG tag override for {key}")
            output[key] = (ids, level)
    return output


@dataclass(frozen=True)
class _IndexedTopic:
    passages: list[Chunk]
    word: TfidfVectorizer
    word_matrix: object
    char: TfidfVectorizer
    char_matrix: object
    term_counts: list[Counter]
    dfs: Counter
    lengths: list[int]
    mean_length: float


def _bm25(query: str, index: _IndexedTopic) -> np.ndarray:
    """BM25(k1=1.5, b=.75), no network/vector service required."""
    n = len(index.passages)
    scores = np.zeros(n)
    for term in set(_terms(query)):
        df = index.dfs.get(term, 0)
        if df == 0:
            continue
        idf = math.log1p((n - df + 0.5) / (df + 0.5))
        for i, doc in enumerate(index.term_counts):
            tf = doc.get(term, 0)
            if tf:
                norm = 1.5 * (0.25 + 0.75 * index.lengths[i] / index.mean_length)
                scores[i] += idf * tf * 2.5 / (tf + norm)
    return scores


def _scaled(x: np.ndarray) -> np.ndarray:
    high = float(np.max(x))
    return x / high if high > 0 else np.zeros_like(x)


@retrievers.register("medical_hybrid")
class MedicalHybridRetriever:
    """BM25 + word/character TF-IDF, KC-aware preference, and MMR diversity."""

    def __init__(self) -> None:
        self.indices: dict[str, _IndexedTopic] = {}
        overrides = _approved_overrides()
        for topic, filename in TOPIC_FILES.items():
            source_file = RAW_DIR / filename
            url, body = _document(source_file)
            texts = [
                chunk
                for title, lines in _segments(body)
                for chunk in _chunk_section(title, lines)
            ]
            if not texts:
                raise ValueError(f"medical corpus has no usable text: {source_file}")
            tags = _assign_tags(texts, topic)
            passages = []
            for text, (ids, level) in zip(texts, tags, strict=True):
                reviewed = overrides.get((topic, _chunk_id(topic, url, text)))
                if reviewed is not None:
                    ids, level = reviewed
                passages.append(Chunk(
                    text=text, source=url, topic=topic, score=0,
                    kc_ids=list(ids), level=level,
                ))
            word = TfidfVectorizer(
                stop_words="english", ngram_range=(1, 2), sublinear_tf=True,
            )
            char = TfidfVectorizer(
                analyzer="char_wb", ngram_range=(3, 5), sublinear_tf=True,
            )
            word_matrix = word.fit_transform(texts)
            char_matrix = char.fit_transform(texts)
            terms = [_terms(text) for text in texts]
            term_counts = [Counter(tokens) for tokens in terms]
            dfs = Counter(term for counts in term_counts for term in counts)
            lengths = [len(tokens) for tokens in terms]
            self.indices[topic] = _IndexedTopic(
                passages=passages, word=word, word_matrix=word_matrix,
                char=char, char_matrix=char_matrix, term_counts=term_counts,
                dfs=dfs, lengths=lengths,
                mean_length=sum(lengths) / len(lengths) or 1.0,
            )

    def retrieve(
        self, query: str, topic: str, k: int = 4,
        kc_ids: list[str] | None = None, level: Level | None = None,
    ) -> list[Chunk]:
        if topic not in self.indices or not query.strip() or k <= 0:
            return []
        ix = self.indices[topic]
        word = cosine_similarity(ix.word.transform([query]), ix.word_matrix).ravel()
        char = cosine_similarity(ix.char.transform([query]), ix.char_matrix).ravel()
        bm25 = _bm25(query, ix)
        # Scale each signal within the topic; preserve no-match abstention.
        scores = 0.45 * _scaled(word) + 0.20 * _scaled(char) + 0.35 * _scaled(bm25)
        relevant = [i for i, s in enumerate(scores) if s >= 0.03]
        if not relevant:
            return []

        requested_kcs = set(kc_ids or [])

        def matching(i: int) -> bool:
            p = ix.passages[i]
            return ((not requested_kcs or bool(requested_kcs.intersection(p.kc_ids)))
                    and (level is None or p.level == level))

        preferred = [i for i in relevant if matching(i)]
        fallback = [i for i in relevant if not matching(i)]
        chosen: list[int] = []

        for group in (preferred, fallback):
            remaining = set(group)
            while remaining and len(chosen) < k:
                def utility(i: int) -> tuple[float, float, int]:
                    # MMR: discourage near-duplicates but keep relevance primary.
                    sim = max(
                        (float(ix.word_matrix[i].multiply(ix.word_matrix[j]).sum())
                         for j in chosen), default=0.0,
                    )
                    return (float(scores[i]) - 0.20 * sim, float(scores[i]), -i)

                best = max(remaining, key=utility)
                chosen.append(best)
                remaining.remove(best)

        return [
            ix.passages[i].model_copy(update={"score": round(float(scores[i]), 6)})
            for i in chosen
        ]
