"""E2 simulator: students with a hidden true mastery go through the REAL learner model (design §11 E2).

Simulated student (per KC):
- true mastery m in [0, 1], drawn at the start; a KC never starts more than 0.2 above its weakest
  prerequisite;
- learning rate drawn from [0.05, 0.20] per student: after practising a KC, m += learn * (1 - m);
- forgetting 0.02 per step on every KC: m *= 0.98 (before the practice of that step);
- slip and guess drawn per student from distributions that differ from the BKT defaults (0.10 / 0.25):
  slip in [0.10, 0.25], guess in [0.20, 0.40];
- P(correct) = m * (1 - slip) + (1 - m) * guess.

One run per student: onboarding diagnostic (the real `apply_diagnostic`), then N interactions. Each one uses
the real recommender (`next_kc`) and the real item selection (`choose_item`). When every item of the KC was
answered within 24 h (simulated time does not pass), the least recently answered item is reused.

Weak signals (when weak evidence is on): before answering, the student asks a question about the KC with
probability 0.5. It carries a confusion signal with P = 0.15 + 0.45 * (1 - m), and with probability `noise`
(the E1 tagging error rate) the signal is tagged to a random other KC of the topic.

Metrics, over every step and every KC of the topic:
- MAE between the model's p_mastery and the true mastery;
- next-answer AUC: the model's p_mastery for the practised KC before the answer vs the answer's correctness
  (the "oracle" AUC uses the student's true P(correct) instead: the best any estimate could do);
- level-band accuracy: the model's level (with hysteresis) vs the true band (0.40 / 0.70).
"""
import random
import sys
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "backend"))

from sqlalchemy.pool import StaticPool  # noqa: E402
from sqlmodel import create_engine  # noqa: E402

from app.core.config import Settings  # noqa: E402
from app.core.schemas import Evidence  # noqa: E402
from app.learner.checks import choose_item, diagnostic_items, evidence_for, grade  # noqa: E402
from app.learner.content import ContentStore  # noqa: E402
from app.learner.facade import build_learner_model  # noqa: E402
from app.storage.db import init_db  # noqa: E402

FORGET = 0.02
ASK_RATE = 0.5


@dataclass
class SimStudent:
    sid: str
    mastery: dict[str, float]
    learn: float
    slip: float
    guess: float


@dataclass
class RunConfig:
    name: str
    knowledge: str = "bkt"
    weak_evidence: bool = False
    bkt: dict = field(default_factory=dict)  # overrides of learner.bkt_defaults (sensitivity sweep)


@dataclass
class RunResult:
    config: RunConfig
    abs_errors: list[float] = field(default_factory=list)
    band_hits: list[bool] = field(default_factory=list)
    predictions: list[tuple[float, bool]] = field(default_factory=list)
    oracle: list[tuple[float, bool]] = field(default_factory=list)  # true P(correct) vs outcome: the ceiling
    mae_by_step: list[list[float]] = field(default_factory=list)  # step -> per-KC errors
    mae_by_student: list[float] = field(default_factory=list)
    reused_items: int = 0

    @property
    def mae(self) -> float:
        return sum(self.abs_errors) / len(self.abs_errors) if self.abs_errors else float("nan")

    @property
    def band_accuracy(self) -> float:
        return sum(self.band_hits) / len(self.band_hits) if self.band_hits else float("nan")

    @property
    def auc(self) -> float:
        return auc(self.predictions)

    @property
    def oracle_auc(self) -> float:
        return auc(self.oracle)


def auc(pairs: list[tuple[float, bool]]) -> float:
    """Mann-Whitney AUC with ties counted as one half."""
    pos = sorted(p for p, y in pairs if y)
    neg = sorted(p for p, y in pairs if not y)
    if not pos or not neg:
        return float("nan")
    import bisect
    total = 0.0
    for p in pos:
        lo, hi = bisect.bisect_left(neg, p), bisect.bisect_right(neg, p)
        total += lo + 0.5 * (hi - lo)
    return total / (len(pos) * len(neg))


def true_band(m: float, basic_below: float, advanced_above: float) -> str:
    return "basic" if m < basic_below else ("advanced" if m > advanced_above else "intermediate")


def make_students(content: ContentStore, topic: str, n: int, seed: int) -> list[SimStudent]:
    rng = random.Random(seed)
    order = [k.id for k in content.kcs(topic)]
    out = []
    for i in range(n):
        m: dict[str, float] = {}
        for kc in order:  # kcs.yaml lists prerequisites first (validated topological order is not needed)
            value = rng.betavariate(1.2, 2.0)
            prereqs = [p for p in content.prerequisites(kc) if p in m]
            if prereqs:
                value = min(value, min(m[p] for p in prereqs) + 0.2)
            m[kc] = value
        out.append(SimStudent(sid=f"sim-{seed}-{i}", mastery=m, learn=rng.uniform(0.05, 0.20),
                              slip=rng.uniform(0.10, 0.25), guess=rng.uniform(0.20, 0.40)))
    return out


def p_correct(st: SimStudent, kc: str) -> float:
    m = st.mastery[kc]
    return m * (1 - st.slip) + (1 - m) * st.guess


def answer(rng: random.Random, item, st: SimStudent) -> str:
    if rng.random() < p_correct(st, item.kc):
        return item.answer
    return rng.choice([k for k in item.options if k != item.answer])


def settings_for(base: Settings, cfg: RunConfig) -> Settings:
    learner = base.learner.model_validate({
        **base.learner.model_dump(), "knowledge": cfg.knowledge, "weak_evidence": cfg.weak_evidence,
        "bkt_defaults": {**base.learner.bkt_defaults.model_dump(), **cfg.bkt}})
    return base.model_copy(update={"learner": learner})


def run(base: Settings, content: ContentStore, topic: str, cfg: RunConfig, students: list[SimStudent],
        interactions: int, noise: float, seed: int) -> RunResult:
    settings = settings_for(base, cfg)
    engine = create_engine("sqlite://", poolclass=StaticPool, connect_args={"check_same_thread": False})
    init_db(engine)
    learner = build_learner_model(settings, engine, content)
    lv = settings.learner.levels
    kc_ids = [k.id for k in content.kcs(topic)]
    res = RunResult(config=cfg, mae_by_step=[[] for _ in range(interactions)])
    for idx, original in enumerate(students):
        rng = random.Random(seed * 100_003 + idx)  # same answers stream per student in every config
        st = SimStudent(original.sid, dict(original.mastery), original.learn, original.slip, original.guess)
        learner.set_consent(st.sid, True)
        diag = [(i.id, answer(rng, i, st)) for i in diagnostic_items(content, topic)]
        learner.apply_diagnostic(st.sid, topic, diag)
        student_errors = []
        for step in range(interactions):
            for kc in kc_ids:  # forgetting
                st.mastery[kc] *= 1 - FORGET
            rec = learner.recommender.next_kc(st.sid, topic)
            states = learner.knowledge.state(st.sid, kc_ids)
            kc = rec.kc_id if rec and rec.kc_id in states else min(kc_ids, key=lambda k: states[k].p_mastery)
            if cfg.weak_evidence and rng.random() < ASK_RATE \
                    and rng.random() < 0.15 + 0.45 * (1 - st.mastery[kc]):
                tagged = rng.choice([k for k in kc_ids if k != kc]) if rng.random() < noise else kc
                learner.observe_request(st.sid, [Evidence(kc_id=tagged, kind="weak", signal="confusion",
                                                          source="understand")])
                states = learner.knowledge.state(st.sid, kc_ids)
            item = choose_item(content, learner.repo, st.sid, kc, states[kc].level, learner.tracker.open_ids(st.sid))
            if item is None:  # everything answered "today": reuse the least recently answered item
                answered = learner.repo.answered_items(st.sid)
                item = min(content.items(kc), key=lambda i: answered.get(i.id, min(answered.values())))
                res.reused_items += 1
            choice = answer(rng, item, st)
            graded = grade(item, choice)
            res.predictions.append((states[kc].p_mastery, graded.correct))
            res.oracle.append((p_correct(st, kc), graded.correct))
            learner.observe(st.sid, evidence_for(item, graded, "strong", "check"))
            learner.check_answered(st.sid, item, graded)
            st.mastery[kc] += st.learn * (1 - st.mastery[kc])
            after = learner.knowledge.state(st.sid, kc_ids)
            for k in kc_ids:
                err = abs(after[k].p_mastery - st.mastery[k])
                res.abs_errors.append(err)
                res.mae_by_step[step].append(err)
                student_errors.append(err)
                res.band_hits.append(after[k].level == true_band(st.mastery[k], lv.basic_below, lv.advanced_above))
        res.mae_by_student.append(sum(student_errors) / len(student_errors))
    engine.dispose()
    return res


def load_content(base: Settings) -> ContentStore:
    return ContentStore(base.content_dir(), serve_unreviewed=True)  # simulation only: all items usable


def simulated_topics(content: ContentStore) -> list[str]:
    """Topics with a KC map and at least one item per KC (others cannot be simulated yet)."""
    return [t for t in content.topics() if content.kcs(t) and all(content.items(k.id) for k in content.kcs(t))]
