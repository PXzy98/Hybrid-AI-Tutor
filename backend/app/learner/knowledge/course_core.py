"""Offline course-level knowledge state with BKT and course ability.

S8 computational core only. The course catalog, evidence persistence, role checks,
and v2 API are supplied by the Z-owned platform. Never stores question text.
"""
from dataclasses import dataclass, field
from math import exp, isfinite
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
                 ability_gain: float = 0.3) -> None:
        if not prerequisites or any(not isinstance(k, str) or not k for k in prerequisites):
            raise CourseKnowledgeError("The course must define named KCs.")
        if any(not 0 < x < 1 for x in (prior, slip, guess)):
            raise CourseKnowledgeError("Invalid BKT probabilities.")
        if not (0 <= learn_rate <= 1 and 0 < ability_gain <= 1):
            raise CourseKnowledgeError("Invalid model learning rates.")
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

    def initial(self, course_id: int, student_id: str) -> CourseKnowledgeState:
        if type(course_id) is not int or course_id <= 0 or not student_id:
            raise CourseKnowledgeError("A valid course and student are required.")
        return CourseKnowledgeState(course_id=course_id, student_id=student_id)

    def progress(self, state: CourseKnowledgeState, kc_id: str) -> KCProgress:
        if kc_id not in self.graph:
            raise CourseKnowledgeError("Unknown knowledge component.")
        return state.kcs.get(kc_id, KCProgress(self.prior))

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
            p = weak_update(old.probability, 0.3, 0.6)
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
