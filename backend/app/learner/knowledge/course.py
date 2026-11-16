"""The course-level layered knowledge model (guide 4.10; task S8): `learner.knowledge: course`.

Three layers on top of KC-level BKT, from `course_core`:
- **course ability**: one value per student and course, replayed from the student's graded answers in this
  course (Elo-like: up when an answer beats the expectation for the item's level, down otherwise). Nothing new
  is stored: the evidence log already holds every graded answer, and the repository is per course;
- **starting estimate**: a KC the student has not been observed on starts from the BKT prior shifted by the
  ability, so a strong student starts higher on a new KC and a weak one lower;
- **prerequisites**: the shown mastery of a KC is capped by its weakest prerequisite. The stored estimate
  stays the raw BKT value, and updates start from it, so a weak prerequisite never corrupts what was learned.

With no graded answers and no prerequisites it gives exactly what BKT gives.
"""
from app.core.registry import knowledge_models
from app.core.schemas import Evidence, KcState
from app.learner.knowledge.bkt import BKTKnowledgeModel
from app.learner.knowledge.course_core import ability_step, propagate, shifted_prior


@knowledge_models.register("course")
class CourseKnowledgeModel(BKTKnowledgeModel):
    def ability(self, student_id: str) -> float:
        """The student's ability in this course, from their graded answers in order."""
        gain = self.cfg.course_model.ability_gain
        ability = 0.0
        for row in self.repo.evidence(student_id):
            if row.kind == "weak" or row.correct is None:
                continue
            item = self.content.item(row.item_id) if row.item_id else None
            ability = ability_step(ability, bool(row.correct), item.level if item else "intermediate", gain)
        return ability

    def _prior_for(self, kc_id: str, ability: float) -> KcState:
        p = shifted_prior(self.cfg.bkt_defaults.p_init, ability, self.cfg.course_model.ability_weight)
        return KcState(kc_id=kc_id, p_mastery=p, level=self._level(p, None), n_obs=0)

    def _raw(self, student_id: str, kc_ids: list[str], ability: float) -> dict[str, KcState]:
        stored = self.repo.states(student_id, kc_ids)
        return {k: stored.get(k) or self._prior_for(k, ability) for k in kc_ids}

    def _closure(self, kc_ids: list[str]) -> dict[str, tuple[str, ...]]:
        """The requested KCs and all their prerequisites, with each one's known prerequisites."""
        graph: dict[str, tuple[str, ...]] = {}
        todo = list(kc_ids)
        while todo:
            kc = todo.pop()
            if kc in graph:
                continue
            deps = tuple(d for d in self.content.prerequisites(kc) if self.content.kc(d) is not None)
            graph[kc] = deps
            todo.extend(deps)
        return graph

    def state(self, student_id: str, kc_ids: list[str]) -> dict[str, KcState]:
        if not kc_ids:
            return {}
        graph = self._closure(kc_ids)
        raw = self._raw(student_id, list(graph), self.ability(student_id))
        shown = propagate({k: s.p_mastery for k, s in raw.items()}, graph)
        out = {}
        for k in kc_ids:
            r = raw[k]
            p = shown[k]
            if p == r.p_mastery:
                out[k] = r
                continue
            stored_level = r.level if r.n_obs else None
            out[k] = r.model_copy(update={"p_mastery": p, "level": self._level(p, stored_level)})
        return out

    def _previous(self, student_id: str, kc_id: str) -> KcState:
        # the raw estimate: the prerequisite cap is applied when the state is shown, never stored
        return self._raw(student_id, [kc_id], self.ability(student_id))[kc_id]

    def update(self, student_id: str, evidence: Evidence) -> KcState:
        super().update(student_id, evidence)
        return self.state(student_id, [evidence.kc_id])[evidence.kc_id]
