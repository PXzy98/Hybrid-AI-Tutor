"""Knowledge Model: what the student knows, per KC (design §5.1). Selected by `learner.knowledge`."""
from typing import Protocol, runtime_checkable

from app.core.config import Settings
from app.core.schemas import Evidence, KcState
from app.learner.content import ContentStore
from app.learner.knowledge.bkt_math import level_with_hysteresis
from app.learner.repository import LearnerRepository


@runtime_checkable
class KnowledgeModel(Protocol):
    def state(self, student_id: str, kc_ids: list[str]) -> dict[str, KcState]:
        """Current state of every requested KC (never-observed KCs get the prior)."""
        ...

    def update(self, student_id: str, evidence: Evidence) -> KcState:
        """Apply one piece of evidence, log it, and return the new state of its KC."""
        ...


class BaseKnowledgeModel:
    """Shared by every implementation: prior for unseen KCs, hysteresis, evidence logging, persistence.

    Subclasses implement `_estimate(student_id, previous, evidence) -> (p_mastery, n_obs)`.
    """

    def __init__(self, repo: LearnerRepository, settings: Settings, content: ContentStore) -> None:
        self.repo = repo
        self.cfg = settings.learner
        self.content = content

    def _level(self, p: float, previous: str | None):
        lv = self.cfg.levels
        return level_with_hysteresis(p, previous, lv.basic_below, lv.advanced_above, lv.hysteresis)

    def prior(self, kc_id: str) -> KcState:
        p = self.cfg.bkt_defaults.p_init
        return KcState(kc_id=kc_id, p_mastery=p, level=self._level(p, None), n_obs=0)

    def state(self, student_id: str, kc_ids: list[str]) -> dict[str, KcState]:
        stored = self.repo.states(student_id, kc_ids)
        return {k: stored.get(k) or self.prior(k) for k in kc_ids}

    def update(self, student_id: str, evidence: Evidence) -> KcState:
        if self.content.kc(evidence.kc_id) is None:
            raise ValueError(f"unknown KC '{evidence.kc_id}'")
        if evidence.kind in ("strong", "diagnostic") and evidence.correct is None:
            raise ValueError("graded evidence needs `correct`")
        previous = self.state(student_id, [evidence.kc_id])[evidence.kc_id]
        weight = self._weight(evidence)
        seen_at = self.repo.log_evidence(student_id, evidence, weight)
        p, n_obs = self._estimate(student_id, previous, evidence)
        new = KcState(kc_id=evidence.kc_id, p_mastery=round(p, 6), level=self._level(p, previous.level),
                      n_obs=n_obs, last_seen=seen_at)
        self.repo.save_state(student_id, new)
        return new

    def _weight(self, evidence: Evidence) -> float:
        if evidence.kind != "weak":
            return 1.0
        w = self.cfg.weak_likelihood
        return round(w.given_not_mastered / w.given_mastered, 3)  # likelihood ratio of the signal

    def _estimate(self, student_id: str, previous: KcState, evidence: Evidence) -> tuple[float, int]:
        raise NotImplementedError
