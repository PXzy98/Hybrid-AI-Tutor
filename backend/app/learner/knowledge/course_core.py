"""Offline course-level knowledge state: course ability, KC-level BKT, prerequisite propagation.

The three layers of guide 4.10:
- one ability value per student and course, updated online after each graded answer (Elo/IRT-like);
- KC-level BKT; a KC the student has not been observed on starts from a prior shifted by the ability,
  so a strong student starts higher on a new KC and a weak one lower (`ability_weight` 0 = plain BKT);
- weak prerequisites lower the effective mastery of the KCs that depend on them.

S8 computational core only. The course catalog, evidence persistence, role checks,
and v2 API are supplied by the Z-owned platform. Never stores question text.
"""
from dataclasses import dataclass, field
from math import exp, isfinite, log
from typing import Literal

from app.learner.knowledge.bkt_math import learn, posterior, weak_update

EvidenceKind = Literal["strong", "diagnostic", "weak"]
Difficulty = Literal["basic", "intermediate", "advanced"]


class CourseKnowledgeError(ValueError):
    """Invalid course, KC graph, or learner evidence."""


@dataclass(frozen=True)
class CourseEvidence:
    course_id: int
    student_id: str
    kc_id: str
    kind: EvidenceKind
    correct: bool | None
    difficulty: Difficulty = "intermediate"


@dataclass(frozen=True)
class KCProgress:
    probability: float = 0.2
    observations: int = 0


@dataclass(frozen=True)
class CourseKnowledgeState:
    course_id: int
    student_id: str
    ability: float = 0.0
    kcs: dict[str, KCProgress] = field(default_factory=dict)


class CourseKnowledgeCore:
    """Validated prerequisite graph with course ability and KC-level BKT."""

    def __init__(self, prerequisites: dict[str, list[str]], *, prior: float = 0.2,
                 learn_rate: float = 0.1, slip: float = 0.1, guess: float = 0.25,
                 ability_gain: float = 0.3, ability_weight: float = 0.5,
                 weak_likelihood: tuple[float, float] = (0.3, 0.6)) -> None:
        if not prerequisites or any(not isinstance(k, str) or not k for k in prerequisites):
            raise CourseKnowledgeError("The course must define named KCs.")
        if any(not 0 < x < 1 for x in (prior, slip, guess)):
            raise CourseKnowledgeError("Invalid BKT probabilities.")
        if not (0 <= learn_rate <= 1 and 0 < ability_gain <= 1 and 0 <= ability_weight <= 1):
            raise CourseKnowledgeError("Invalid model learning rates.")
        if any(not 0 < x < 1 for x in weak_likelihood):
            raise CourseKnowledgeError("Invalid weak-evidence likelihoods.")
        self.ability_weight, self.weak_likelihood = ability_weight, weak_likelihood
        self.graph = {kc: tuple(deps) for kc, deps in prerequisites.items()}
        self.prior, self.learn_rate = prior, learn_rate
        self.slip, self.guess, self.ability_gain = slip, guess, ability_gain
        checked: set[str] = set()
        active: set[str] = set()

        def visit(node: str) -> None:
            if node in active:
                raise CourseKnowledgeError("Cyclic KC prerequisites are not allowed.")
            if node in checked:
                return
            active.add(node)
            for dep in self.graph[node]:
                if dep not in self.graph or dep == node:
                    raise CourseKnowledgeError("Unknown or self-referential prerequisite.")
                visit(dep)
            active.remove(node)
            checked.add(node)

        for kc in self.graph:
            visit(kc)

    @classmethod
    def from_settings(cls, prerequisites: dict[str, list[str]], settings) -> "CourseKnowledgeCore":
        """Use the deployment's BKT parameters (`learner.bkt_defaults`, `learner.weak_likelihood`)."""
        b, w = settings.learner.bkt_defaults, settings.learner.weak_likelihood
        return cls(prerequisites, prior=b.p_init, learn_rate=b.learn, slip=b.slip, guess=b.guess,
                   weak_likelihood=(w.given_mastered, w.given_not_mastered))

    def prior_for(self, ability: float) -> float:
        """The starting mastery of an unobserved KC: the prior's log-odds shifted by the ability."""
        logit = log(self.prior / (1 - self.prior)) + self.ability_weight * ability
        return round(1 / (1 + exp(-logit)), 6)

    def predict_correct(self, state: CourseKnowledgeState, kc_id: str) -> float:
        """P(correct answer) on an item of this KC, from the effective mastery (with prerequisites)."""
        m = self.effective_mastery(state)[kc_id]
        return round(m * (1 - self.slip) + (1 - m) * self.guess, 6)

    def initial(self, course_id: int, student_id: str) -> CourseKnowledgeState:
        if type(course_id) is not int or course_id <= 0 or not student_id:
            raise CourseKnowledgeError("A valid course and student are required.")
        return CourseKnowledgeState(course_id=course_id, student_id=student_id)

    def progress(self, state: CourseKnowledgeState, kc_id: str) -> KCProgress:
        if kc_id not in self.graph:
            raise CourseKnowledgeError("Unknown knowledge component.")
        return state.kcs.get(kc_id) or KCProgress(self.prior_for(state.ability))

    def effective_mastery(self, state: CourseKnowledgeState) -> dict[str, float]:
        """Lower apparent mastery when prerequisites are weak, preserving raw BKT state."""
        calculated: dict[str, float] = {}

        def score(kc: str) -> float:
            if kc not in calculated:
                raw = self.progress(state, kc).probability
                deps = self.graph[kc]
                if deps:
                    raw = min(raw, 0.25 + 0.75 * min(score(dep) for dep in deps))
                calculated[kc] = round(raw, 6)
            return calculated[kc]

        for kc in self.graph:
            score(kc)
        return calculated

    def update(self, state: CourseKnowledgeState, event: CourseEvidence) -> CourseKnowledgeState:
        """Apply one labelled observation to the correct course without persistence."""
        if state.course_id != event.course_id or state.student_id != event.student_id:
            raise CourseKnowledgeError("Course or student scope mismatch.")
        if event.kc_id not in self.graph:
            raise CourseKnowledgeError("Unknown knowledge component.")
        if event.kind not in ("strong", "diagnostic", "weak"):
            raise CourseKnowledgeError("Unknown evidence type.")
        if event.kind == "weak":
            if event.correct is not None:
                raise CourseKnowledgeError("Weak evidence is not a graded answer.")
        elif type(event.correct) is not bool:
            raise CourseKnowledgeError("Graded evidence requires a Boolean answer.")
        if event.difficulty not in ("basic", "intermediate", "advanced"):
            raise CourseKnowledgeError("Unknown difficulty.")

        old = self.progress(state, event.kc_id)
        if event.kind == "weak":
            p = weak_update(old.probability, *self.weak_likelihood)
            n, ability = old.observations, state.ability
        else:
            p = posterior(old.probability, event.correct, self.slip, self.guess)
            if event.kind == "strong":
                p = learn(p, self.learn_rate)
            n = old.observations + 1
            difficulties = {"basic": -1.0, "intermediate": 0.0, "advanced": 1.0}
            expected = 1.0 / (1.0 + exp(-(state.ability - difficulties[event.difficulty])))
            ability = max(-4.0, min(4.0, state.ability + self.ability_gain *
                                    (float(event.correct) - expected)))
        if not isfinite(ability):
            raise CourseKnowledgeError("Invalid ability state.")
        next_kcs = dict(state.kcs)
        next_kcs[event.kc_id] = KCProgress(round(p, 6), n)
        return CourseKnowledgeState(state.course_id, state.student_id,
                                    round(ability, 6), next_kcs)
