"""Class summary for the instructor (design §8.3): aggregates only, small groups suppressed.

Population: students who gave consent (only they have a learning profile).

Suppression with min_group = learner.class_summary_min_group (5):
- fewer than min_group students in the population → only "suppressed" is returned, no counts at all;
- a band count from 1 to min_group - 1 is replaced by None (0 is shown: it reveals nobody);
- if a row then has exactly one suppressed cell, it could be computed from the total, so the smallest
  other non-zero cell is suppressed too (secondary suppression);
- a misconception is listed only when at least min_group students have it open.
"""
from typing import Literal

from pydantic import BaseModel
from sqlmodel import Session, select

from app.learner.content import ContentStore
from app.learner.facade import LearnerModel
from app.learner.misconceptions import OPEN
from app.storage.models import Consent, LearnerMisconception

Band = Literal["not_assessed", "basic", "intermediate", "advanced", "mastered"]
BANDS: tuple[Band, ...] = ("not_assessed", "basic", "intermediate", "advanced", "mastered")


class KcSummary(BaseModel):
    kc_id: str
    name: str
    counts: dict[str, int | None]  # band -> number of students; None = suppressed


class MisconceptionSummary(BaseModel):
    misconception_id: str
    kc_id: str
    statement: str
    students: int  # with this misconception open (suspected or confirmed)


class ClassSummary(BaseModel):
    topic: str
    min_group: int
    suppressed: bool  # True: the population is smaller than min_group, nothing else is shown
    students: int | None = None
    kcs: list[KcSummary] = []
    misconceptions: list[MisconceptionSummary] = []
    misconceptions_hidden: int = 0  # open misconceptions held by fewer than min_group students


def suppress(counts: dict[str, int], min_group: int) -> dict[str, int | None]:
    out: dict[str, int | None] = {b: (None if 0 < n < min_group else n) for b, n in counts.items()}
    if sum(v is None for v in out.values()) == 1:
        rest = [b for b, v in out.items() if v]  # shown and non-zero
        if rest:
            out[min(rest, key=lambda b: (counts[b], BANDS.index(b)))] = None
    return out


def consenting_students(engine) -> list[str]:
    with Session(engine) as db:
        return sorted(db.exec(select(Consent.student_id).where(Consent.given == True)).all())  # noqa: E712


def class_summary(engine, learner: LearnerModel, content: ContentStore, topic: str, min_group: int
                  ) -> ClassSummary:
    students = consenting_students(engine)
    if len(students) < min_group:
        return ClassSummary(topic=topic, min_group=min_group, suppressed=True)
    kcs = content.kcs(topic)
    kc_ids = [k.id for k in kcs]
    raw = {k: dict.fromkeys(BANDS, 0) for k in kc_ids}
    for sid in students:
        for kc_id, state in learner.knowledge.state(sid, kc_ids).items():
            band = "not_assessed" if state.n_obs == 0 else learner.band(state)
            raw[kc_id][band] += 1
    with Session(engine) as db:
        rows = db.exec(select(LearnerMisconception).where(LearnerMisconception.status.in_(OPEN))).all()
    holders: dict[str, set[str]] = {}
    consenting = set(students)
    for r in rows:
        if r.kc_id in raw and r.student_id in consenting:
            holders.setdefault(r.misconception_id, set()).add(r.student_id)
    shown = sorted(((m, len(s)) for m, s in holders.items() if len(s) >= min_group),
                   key=lambda x: (-x[1], x[0]))
    return ClassSummary(
        topic=topic, min_group=min_group, suppressed=False, students=len(students),
        kcs=[KcSummary(kc_id=k.id, name=k.name, counts=suppress(raw[k.id], min_group)) for k in kcs],
        misconceptions=[MisconceptionSummary(misconception_id=m, kc_id=content.misconception(m).kc,
                                             statement=content.misconception(m).statement, students=n)
                        for m, n in shown],
        misconceptions_hidden=sum(1 for s in holders.values() if len(s) < min_group),
    )
