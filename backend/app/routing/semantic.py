"""Semantic routing: independent capability, evidence-need and evidence-support gates."""

from app.core.config import get_settings
from app.core.registry import routers
from app.core.schemas import EvidenceAssessment, RouteInput, RouteScore, SemanticAnalysis
from app.routing.evidence import assess_evidence
from app.routing.models import encode, load_weights, predict_heads


@routers.register("semantic")
class SemanticRouter:
    def __init__(self):
        self.cfg = get_settings().routing

    def embed(self, question: str):
        return encode([question], self.cfg)[0]

    def classify(self, vector, method: str) -> SemanticAnalysis:
        if method not in self.cfg.enabled_methods:
            raise ValueError("routing method disabled")
        metadata, arrays = load_weights(self.cfg, method)
        values = predict_heads(vector, metadata, arrays)
        fresh = values["requires_fresh_evidence"] >= self.cfg.freshness_required_threshold
        reliable = values["nearest_similarity"] >= self.cfg.ood_similarity_threshold
        return SemanticAnalysis(
            method=method,
            cloud_probability=values["cloud_required"],
            evidence_probability=values["requires_evidence"],
            freshness_probability=values["requires_fresh_evidence"],
            nearest_similarity=values["nearest_similarity"],
            requires_evidence=fresh or values["requires_evidence"] >= self.cfg.evidence_required_threshold,
            requires_fresh_evidence=fresh,
            reliable=reliable,
            label_origin=metadata.get("label_origin", "unspecified"),
            reason="Calibrated semantic classification."
            if reliable
            else "Outside the semantic training support.",
        )

    def analyze(self, x: RouteInput) -> SemanticAnalysis:
        method = x.method or self.cfg.default_method
        if not x.sanitized_question.strip():
            return SemanticAnalysis(method=method, reason="Empty semantic input.")
        try:
            return self.classify(self.embed(x.contextual_question), method)
        except Exception:
            return SemanticAnalysis(
                method=method, reason="Semantic assets unavailable, invalid, or input too long."
            )

    def capable(self, analysis: SemanticAnalysis, threshold: float) -> bool:
        return analysis.reliable and analysis.cloud_probability < max(
            0, threshold - self.cfg.uncertainty_margin
        )

    def decide(
        self,
        x: RouteInput,
        analysis: SemanticAnalysis,
        threshold: float,
        evidence: EvidenceAssessment | None = None,
    ) -> RouteScore:
        capable = self.capable(analysis, threshold)
        if evidence is None:
            evidence = (
                assess_evidence(x, analysis, self.cfg)
                if capable
                else EvidenceAssessment(status="unavailable", reason="Skipped: capability gate did not pass.")
            )
        allowed = capable and (not analysis.requires_evidence or evidence.status == "sufficient")
        # Final score is a POLICY SCORE. cloud_probability remains a separate classifier output.
        score = analysis.cloud_probability if allowed else max(threshold, analysis.cloud_probability)
        reasons = [
            analysis.reason,
            evidence.reason,
            "Local capability and evidence conditions passed."
            if allowed
            else "Cloud selected: capability, uncertainty, or evidence condition did not pass.",
        ]
        return RouteScore(
            score=score,
            target="local" if allowed else "cloud",
            method=analysis.method,
            reasons=reasons,
            analysis=analysis,
            evidence=evidence,
            accepted_indices=evidence.accepted_indices,
        )

    def route_score(self, x: RouteInput) -> RouteScore:
        return self.decide(x, self.analyze(x), self.cfg.threshold)
