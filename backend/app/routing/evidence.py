"""Evaluate retrieved course evidence independently of the answering LLM.

Relevance and QNLI answerability are separate signals. Their thresholds need
domain validation; neither proves medical correctness or source authority.
"""

import logging
import re
from datetime import UTC, datetime, timedelta

import numpy as np

from app.core.config import RoutingConfig
from app.core.schemas import Chunk, EvidenceAssessment, RouteInput, SemanticAnalysis
from app.routing.models import pair_scores

log = logging.getLogger("app.routing")
_warned_unavailable = False


def question_units(question: str) -> list[str]:
    parts = re.split(
        r"(?<=[?？;；])\s*|\n+|\band\s+(?=(?:why|how|what|which|explain)\b)", question.strip(), flags=re.I
    )
    return [p.strip() for p in parts if p.strip()] or [question]


def windows(text: str) -> list[str]:
    words = text.split()
    # Overlap avoids dropping a support sentence at the window boundary.
    return [" ".join(words[i : i + 100]) for i in range(0, len(words), 75)]


def _date(value):
    if not isinstance(value, str):
        return None
    try:
        parsed = datetime.fromisoformat(value.replace("Z", "+00:00"))
        return parsed.astimezone(UTC) if parsed.tzinfo else parsed.replace(tzinfo=UTC)
    except ValueError:
        return None


def source_usable(chunk, fresh: bool, cfg: RoutingConfig) -> bool:
    if (
        not chunk.source.strip()
        or not chunk.text.strip()
        or ("approved" in chunk.metadata and chunk.metadata["approved"] is not True)
    ):
        return False
    now = datetime.now(UTC)
    until = _date(chunk.metadata.get("valid_until"))
    if "valid_until" in chunk.metadata and (until is None or until < now):
        return False
    if fresh:
        verified = _date(chunk.metadata.get("verified_at"))
        if chunk.metadata.get("verified_current") is not True or verified is None:
            return False
        if not now - timedelta(days=cfg.current_source_max_age_days) <= verified <= now:
            return False
    # Without explicit metadata, the Retriever contract supplies instructor course
    # material. This is provenance from that integration, not inferred credibility.
    return True


def assess_evidence(x: RouteInput, analysis: SemanticAnalysis, cfg: RoutingConfig) -> EvidenceAssessment:
    count = len(x.passages)
    required = analysis.requires_evidence
    if not count:
        status = (
            "not_required"
            if not required
            else ("unavailable" if x.retrieval_status in ("disabled", "error", "unknown") else "empty")
        )
        return EvidenceAssessment(status=status, reason="No retrieved evidence; no coverage is assumed.")

    candidates = [
        (i, w)
        for i, c in enumerate(x.passages)
        if c.topic == x.topic and source_usable(c, analysis.requires_fresh_evidence, cfg)
        for w in windows(c.text)
    ]
    if not candidates:
        return EvidenceAssessment(
            status="insufficient" if required else "not_required",
            retrieved_count=count,
            reason="No source passed provenance/time checks.",
        )
    if len(candidates) > cfg.max_evidence_windows:
        # Do not silently truncate a large evidence set and report full verification.
        return EvidenceAssessment(
            status="uncertain" if required else "not_required",
            retrieved_count=count,
            reason="Evidence exceeds the verification budget.",
        )
    units = question_units(x.sanitized_question)
    if x.conversation_context:
        units = [f"Context: {x.conversation_context}\nQuestion: {q}" for q in units]
    pairs = [(q, text) for q in units for _, text in candidates]
    try:
        relevant = pair_scores(cfg.relevance_model, pairs, cfg).reshape(len(units), -1)
        # Only run QA support on candidates that passed relevance.
        selected = [
            (u, j)
            for u in range(len(units))
            for j in range(len(candidates))
            if relevant[u, j] >= cfg.relevance_threshold
        ]
        supported = np.zeros_like(relevant)
        scores = pair_scores(
            cfg.answerability_model, [(units[u], candidates[j][1]) for u, j in selected], cfg
        )
        for (u, j), score in zip(selected, scores, strict=True):
            supported[u, j] = score
        best = supported.max(axis=1)
        passed = best >= cfg.answerability_threshold
        accepted = sorted({candidates[int(supported[u].argmax())][0] for u in range(len(units)) if passed[u]})
        relevant_idx = sorted({candidates[j][0] for _, j in selected})
        coverage = float(passed.mean())
        if bool(passed.all()):
            status = "sufficient"
        else:
            status = "insufficient" if required else "not_required"
        return EvidenceAssessment(
            status=status,
            retrieved_count=count,
            accepted_indices=accepted,
            relevant_indices=relevant_idx,
            checked=True,
            coverage=coverage,
            support_scores=[round(float(s), 4) for s in best],
            reason=f"{int(passed.sum())}/{len(units)} question units have QA support.",
        )
    except Exception as e:
        # Missing/offline model assets and scoring errors are never sufficient evidence.
        global _warned_unavailable
        if not _warned_unavailable:  # once per process: an environment problem, not a per-question one
            log.warning("evidence models unavailable (%s): passages are used unverified; run "
                        "`python -m app.routing.prepare` to download them", type(e).__name__)
            _warned_unavailable = True
        return EvidenceAssessment(
            status="uncertain" if required else "not_required",
            retrieved_count=count,
            reason="Evidence models unavailable or scoring failed.",
        )


def select_passages(x: RouteInput, evidence: EvidenceAssessment | None, cfg: RoutingConfig) -> list[Chunk]:
    """The passages the answer may use. Separate from the routing decision (`accepted_indices`).

    - Evidence models ran: every passage judged relevant to the question. Answerability is a routing signal;
      a relevant passage that does not fully answer the question still teaches (the answer cites it).
    - Evidence skipped, missing or failed: the retriever's own results (it has its own relevance gate) that
      pass the provenance checks, tagged `evidence_check: unverified`, instead of no material at all.
    """
    if evidence is not None and evidence.checked:
        return [x.passages[i] for i in evidence.relevant_indices]
    return [c.model_copy(update={"metadata": {**c.metadata, "evidence_check": "unverified"}})
            for c in x.passages if c.topic == x.topic and source_usable(c, False, cfg)]
