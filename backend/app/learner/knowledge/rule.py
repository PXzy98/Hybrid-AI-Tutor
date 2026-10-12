from app.core.registry import knowledge_models
from app.core.schemas import Evidence, KcState
from app.learner.knowledge.interface import BaseKnowledgeModel


@knowledge_models.register("rule")
class RuleKnowledgeModel(BaseKnowledgeModel):
    """Fallback (design §5.1): smoothed accuracy of the last N graded answers, minus a penalty per weak signal
    since the last graded answer. Recomputed from the evidence log every time, so it needs no parameters
    beyond learner.rule.

        p = (correct + 1) / (n + 2) - weak_penalty * weak_signals_since_last_graded,  clipped to [0, 1]
    Without any graded answer yet, the prior (learner.bkt_defaults.p_init) replaces the accuracy term.
    """

    def _estimate(self, student_id: str, previous: KcState, evidence: Evidence) -> tuple[float, int]:
        rows = self.repo.evidence(student_id, evidence.kc_id)
        graded = [r for r in rows if r.kind in ("strong", "diagnostic")]
        last = graded[-self.cfg.rule.last_n:]
        if last:
            base = (sum(bool(r.correct) for r in last) + 1) / (len(last) + 2)
        else:
            base = self.cfg.bkt_defaults.p_init
        last_graded_id = graded[-1].id if graded else -1
        weak = sum(1 for r in rows if r.kind == "weak" and r.id > last_graded_id)
        p = min(1.0, max(0.0, base - self.cfg.rule.weak_penalty * weak))
        return p, len(graded)
