"""LearnerModel: the one interface the rest of the system uses (design §5.4).

It hides which KnowledgeModel / PreferenceModel is configured, applies the consent rule, and builds the
LearnerContext for the prompt builder. Everything here stays inside the privacy boundary; the cloud only
ever sees LearnerContext.to_cloud_labels().
"""
from sqlalchemy import Engine

from app.core.config import Settings
from app.core.schemas import Evidence, KcState, LearnerContext, Level, Preferences
from app.learner.content import ContentStore
from app.learner.knowledge import KnowledgeModel, load_knowledge_model
from app.learner.knowledge.bkt_math import level_with_hysteresis
from app.learner.preference import PreferenceModel, PreferenceSignal, load_preference_model
from app.learner.recommender import Recommender
from app.learner.repository import LearnerRepository

LEVEL_ORDER: dict[Level, int] = {"basic": 0, "intermediate": 1, "advanced": 2}


class LearnerModel:
    def __init__(self, repo: LearnerRepository, knowledge: KnowledgeModel, preferences: PreferenceModel,
                 recommender: Recommender, content: ContentStore, settings: Settings) -> None:
        self.repo = repo
        self.knowledge = knowledge
        self.preferences = preferences
        self.recommender = recommender
        self.content = content
        self.cfg = settings.learner

    # ------------------------------------------------------------------- consent
    def has_consent(self, student_id: str) -> bool:
        return self.repo.consent(student_id) is True

    def set_consent(self, student_id: str, given: bool) -> None:
        """Withdrawing consent also forgets the learning profile."""
        self.repo.set_consent(student_id, given)
        if not given:
            self.repo.reset(student_id)

    # ------------------------------------------------------------------- context
    def context(self, student_id: str, topic: str, kc_ids: list[str] | None = None) -> LearnerContext:
        """Learner view for the prompt. Without consent: unpersonalized, and nothing is read or stored."""
        if not self.has_consent(student_id):
            return LearnerContext(personalized=False)
        topic_kcs = [k.id for k in self.content.kcs(topic)]
        asked = [k for k in (kc_ids or []) if self.content.kc(k)]
        states = self.knowledge.state(student_id, list(dict.fromkeys(topic_kcs + asked)))
        return LearnerContext(
            kc_states=states,
            focus_level=self._focus_level(student_id, topic, topic_kcs, asked, states),
            preferences=self.preferences.get(student_id),
            next_kc=self.recommender.next_kc(student_id, topic),
            personalized=True,
        )

    def _focus_level(self, student_id: str, topic: str, topic_kcs: list[str], asked: list[str],
                     states: dict[str, KcState]) -> Level:
        if asked:  # the question touches known KCs: the weakest of them decides (design §6)
            return min((states[k].level for k in asked), key=LEVEL_ORDER.__getitem__)
        if not topic_kcs:
            return "intermediate"
        # TEMPORARY until the understand step (Step 11) tags questions with KCs: the topic's mean mastery,
        # with hysteresis against the last topic level
        mean = sum(states[k].p_mastery for k in topic_kcs) / len(topic_kcs)
        previous = self.repo.topic_level(student_id, topic)
        lv = self.cfg.levels
        level = level_with_hysteresis(mean, previous, lv.basic_below, lv.advanced_above, lv.hysteresis)
        if level != previous:
            self.repo.save_topic_level(student_id, topic, level)
        return level

    # ------------------------------------------------------------------ evidence
    def observe(self, student_id: str, evidence: Evidence) -> KcState | None:
        """Apply one piece of evidence. Without consent nothing is stored and None is returned."""
        if not self.has_consent(student_id):
            return None
        return self.knowledge.update(student_id, evidence)

    def observe_request(self, student_id: str, evidence: list[Evidence]) -> list[KcState]:
        """Evidence from one request: at most one weak update per KC (design §5.1)."""
        seen_weak: set[str] = set()
        out = []
        for ev in evidence:
            if ev.kind == "weak":
                if ev.kc_id in seen_weak:
                    continue
                seen_weak.add(ev.kc_id)
            state = self.observe(student_id, ev)
            if state:
                out.append(state)
        return out

    def apply_diagnostic(self, student_id: str, topic: str,
                         answers: list[tuple[str, str]]) -> tuple[dict[str, bool], list[str]]:
        """Grade onboarding answers and apply them as diagnostic evidence, prerequisites first.

        A KC whose prerequisite was answered wrongly (or was itself skipped) is not assessed and keeps its
        prior: a correct answer there is more likely a guess. Returns ({kc_id: correct}, skipped kc_ids).
        """
        from app.learner.checks import evidence_for, grade, topological

        by_kc: dict[str, tuple] = {}
        for item_id, choice in answers:
            item = self.content.item(item_id)
            if item is None or self.content.topic_of(item.kc) != topic:
                raise ValueError(f"unknown item for this topic: {item_id}")
            by_kc.setdefault(item.kc, (item, grade(item, choice)))
        assessed: dict[str, bool] = {}
        blocked: set[str] = set()
        skipped: list[str] = []
        for kc_id in topological(self.content, topic):
            if kc_id not in by_kc:
                continue
            if any(p in blocked for p in self.content.prerequisites(kc_id)):
                blocked.add(kc_id)
                skipped.append(kc_id)
                continue
            item, graded = by_kc[kc_id]
            self.observe(student_id, evidence_for(item, graded, "diagnostic", "onboarding"))
            assessed[kc_id] = graded.correct
            if not graded.correct:
                blocked.add(kc_id)
        return assessed, skipped

    def band(self, state: KcState) -> str:
        """What the student sees: basic / intermediate / advanced, or mastered. Never the probability."""
        return "mastered" if state.p_mastery >= self.cfg.recommender.mastered else state.level

    # --------------------------------------------------------------- preferences
    def update_preferences(self, student_id: str, signal: PreferenceSignal) -> Preferences | None:
        if not self.has_consent(student_id):
            return None
        return self.preferences.update(student_id, signal)

    # --------------------------------------------------------------------- reset
    def reset(self, student_id: str) -> None:
        self.repo.reset(student_id)


def build_learner_model(settings: Settings, engine: Engine, content: ContentStore) -> LearnerModel:
    repo = LearnerRepository(engine)
    knowledge = load_knowledge_model(settings, repo, content)
    preferences = load_preference_model(settings, repo)
    recommender = Recommender(knowledge, content, settings)
    return LearnerModel(repo, knowledge, preferences, recommender, content, settings)
