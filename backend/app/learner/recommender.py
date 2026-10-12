"""Next KC to study (design §5.3)."""
from app.core.config import Settings
from app.core.schemas import KcRecommendation, KcState
from app.learner.content import ContentStore
from app.learner.knowledge import KnowledgeModel


class Recommender:
    """Candidates: KCs whose prerequisites are all ready (>= recommender.ready) and that are not yet mastered
    (< recommender.mastered). Lowest mastery first, then fewer observations.

    The current topic is searched first; other topics only when the current one has no candidate. None when
    everything is mastered. (The design's "weakest prerequisite" fallback cannot trigger: in a DAG, following
    unready prerequisites always ends at a KC whose own prerequisites are ready, which is a candidate.)
    """

    def __init__(self, knowledge: KnowledgeModel, content: ContentStore, settings: Settings) -> None:
        self.knowledge = knowledge
        self.content = content
        self.cfg = settings.learner.recommender

    def next_kc(self, student_id: str, topic: str) -> KcRecommendation | None:
        topics = [topic] + [t for t in self.content.topics() if t != topic]
        for i, t in enumerate(topics):
            kcs = self.content.kcs(t)
            states = self.knowledge.state(student_id, [k.id for k in kcs])
            ready = [k for k in kcs if states[k.id].p_mastery < self.cfg.mastered
                     and all(self._p(states, student_id, p) >= self.cfg.ready for p in k.prerequisites)]
            if ready:
                best = min(ready, key=lambda k: (states[k.id].p_mastery, states[k.id].n_obs))
                where = "in this topic" if i == 0 else f"in {self.content.topic(t).name}"
                return KcRecommendation(kc_id=best.id, name=best.name,
                                        reason=f"prerequisites ready, lowest mastery {where}")
        return None

    def _p(self, states: dict[str, KcState], student_id: str, kc_id: str) -> float:
        if kc_id not in states:
            states.update(self.knowledge.state(student_id, [kc_id]))
        return states[kc_id].p_mastery
