"""Traceable evidence records and a conservative numeric-claim precheck.

These helpers DO NOT prove clinical truth. A number being present in a source
still requires comparing the population, outcome, timeframe and risk measure.
"""

import json
import re
from dataclasses import asdict, dataclass
from pathlib import Path, PurePosixPath

from app.core.config import REPO_ROOT
from app.core.schemas import Chunk
from app.rag.medical_hybrid import _chunk_id

_MANIFEST = REPO_ROOT / "data" / "medical_rag" / "corpus_manifest.json"
_NUMERIC = re.compile(r"(?<![A-Za-z0-9])\d+(?:\.\d+)?\s*(?:%|percent|mmhg|mg|years?)?", re.I)


@dataclass(frozen=True)
class EvidenceRecord:
    evidence_id: str
    topic: str
    text: str
    source_url: str
    source_title: str
    source_publisher: str
    source_last_modified: str | None
    corpus_fetched_at: str | None
    relevance_score: float
    suggested_kc_ids: tuple[str, ...]
    suggested_level: str | None

    def to_dict(self) -> dict:
        return asdict(self)


@dataclass(frozen=True)
class NumericClaimCheck:
    status: str
    numbers_in_claim: tuple[str, ...]
    candidate_evidence_ids: tuple[str, ...]
    note: str

    def to_dict(self) -> dict:
        return asdict(self)


def _normalize_number(value: str) -> str:
    return re.sub(r"\s+", "", value.lower().replace("percent", "%"))


def _numbers(text: str) -> set[str]:
    return {_normalize_number(m.group(0)) for m in _NUMERIC.finditer(text)}


def evidence_from_chunks(chunks: list[Chunk], manifest: Path = _MANIFEST) -> list[EvidenceRecord]:
    """Enrich existing Chunk objects without changing teammates' shared schema."""
    metadata = {}
    if manifest.is_file():
        for row in json.loads(manifest.read_text(encoding="utf-8")):
            metadata[row["url"]] = row
    evidence = []
    for chunk in chunks:
        source = metadata.get(chunk.source, {})
        if chunk.source.startswith("course/"):
            title = PurePosixPath(chunk.source).stem.replace("_", " ").replace("-", " ")
            publisher = "Instructor upload (review status unverified)"
        else:
            title = source.get("title", "Unknown source")
            publisher = source.get("publisher", "Unknown publisher")
        evidence.append(
            EvidenceRecord(
                evidence_id=_chunk_id(chunk.topic, chunk.source, chunk.text),
                topic=chunk.topic,
                text=chunk.text,
                source_url=chunk.source,
                source_title=title,
                source_publisher=publisher,
                source_last_modified=source.get("source_last_modified"),
                corpus_fetched_at=source.get("fetched_at_utc"),
                relevance_score=chunk.score,
                suggested_kc_ids=tuple(chunk.kc_ids),
                suggested_level=chunk.level,
            )
        )
    return evidence


def check_numeric_claim(claim: str, evidence: list[EvidenceRecord]) -> NumericClaimCheck:
    """Check whether every numeric token occurs in ONE candidate passage.

    Match != validation. Never label a claim 'verified' or infer its risk type.
    """
    values = _numbers(claim)
    if not values:
        return NumericClaimCheck(
            "not_a_numeric_claim",
            (),
            (),
            "No numeric tokens detected; other factual claims still require verification.",
        )
    candidates = [record.evidence_id for record in evidence if values <= _numbers(record.text)]
    if candidates:
        status = "numbers_present_context_unverified"
        note = (
            "Same numeric tokens appear in a retrieved passage; verify study population, "
            "denominator, endpoint, units, absolute/relative risk and publication context."
        )
    else:
        status = "numeric_evidence_missing"
        note = (
            "No retrieved passage contains all claimed numeric tokens. "
            "Do not present this quantitative claim as evidence-grounded."
        )
    return NumericClaimCheck(status, tuple(sorted(values)), tuple(candidates), note)
