from app.core.registry import knowledge_models
from app.core.schemas import Evidence, KcState
from app.learner.knowledge import bkt_math
from app.learner.knowledge.interface import BaseKnowledgeModel


@knowledge_models.register("bkt")
class BKTKnowledgeModel(BaseKnowledgeModel):
    """Bayesian Knowledge Tracing per KC (default).

    strong (check answer):  posterior with slip/guess, then the learning step
    diagnostic (onboarding): posterior only (a placement test is not practice)
    weak (understand step):  noisy observation, no learning step; only lowers mastery (MVP)
    Parameters: learner.bkt_defaults, overridden per item level by learner.bkt_by_level.
    """

    def _params(self, evidence: Evidence) -> tuple[float, float, float]:
        d = self.cfg.bkt_defaults
        learn, slip, guess = d.learn, d.slip, d.guess
        item = self.content.item(evidence.item_id) if evidence.item_id else None
        override = self.cfg.bkt_by_level.get(item.level) if item else None
        if override:
            learn = override.learn if override.learn is not None else learn
            slip = override.slip if override.slip is not None else slip
            guess = override.guess if override.guess is not None else guess
        return learn, slip, guess

    def _estimate(self, student_id: str, previous: KcState, evidence: Evidence) -> tuple[float, int]:
        p = previous.p_mastery
        if evidence.kind == "weak":
            w = self.cfg.weak_likelihood
            return bkt_math.weak_update(p, w.given_mastered, w.given_not_mastered), previous.n_obs
        learn, slip, guess = self._params(evidence)
        p = bkt_math.posterior(p, bool(evidence.correct), slip, guess)
        if evidence.kind == "strong":
            p = bkt_math.learn(p, learn)
        return p, previous.n_obs + 1
