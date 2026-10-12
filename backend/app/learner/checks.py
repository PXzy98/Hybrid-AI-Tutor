"""Check questions: grading by key, item selection, the onboarding diagnostic (design §5.5, §6, §7.2)."""
from dataclasses import dataclass
from datetime import timedelta

from app.core.schemas import Evidence, Level
from app.learner.content import ContentStore, Item
from app.learner.repository import LearnerRepository
from app.storage.models import utcnow

REPEAT_AFTER = timedelta(hours=24)  # an item answered within this window is not asked again
DIAGNOSTIC_MAX = 10


@dataclass(frozen=True)
class Graded:
    correct: bool
    correct_choice: str
    misconception_id: str | None  # the misconception the chosen distractor reveals, if any


def grade(item: Item, choice: str) -> Graded:
    """By the answer key only: no model involved, so this is reliable ("strong") evidence."""
    chosen = item.options.get(choice)
    correct = choice == item.answer
    return Graded(correct=correct, correct_choice=item.answer,
                  misconception_id=None if correct or chosen is None else chosen.misconception)


def evidence_for(item: Item, graded: Graded, kind: str, source: str) -> Evidence:
    return Evidence(kc_id=item.kc, kind=kind, correct=graded.correct, item_id=item.id,
                    misconception_id=graded.misconception_id, source=source)


def topological(content: ContentStore, topic: str) -> list[str]:
    """KC IDs of a topic, prerequisites before the KCs that need them (stable within a level)."""
    kcs = {k.id: k for k in content.kcs(topic)}
    done: list[str] = []
    while len(done) < len(kcs):
        for kid, k in kcs.items():
            if kid not in done and all(p in done or p not in kcs for p in k.prerequisites):
                done.append(kid)
                break
    return done


def diagnostic_items(content: ContentStore, topic: str) -> list[Item]:
    """One item per KC, prerequisite-free KCs first, preferring the KC's basic item; at most 10."""
    out = []
    for kc_id in topological(content, topic):
        items = content.items(kc_id)
        if items:
            out.append(min(items, key=lambda i: (i.level != "basic", i.id)))
    return out[:DIAGNOSTIC_MAX]


def choose_item(content: ContentStore, repo: LearnerRepository, student_id: str | None, kc_id: str,
                kc_level: Level | None) -> Item | None:
    """An item of the KC: never answered first, never one answered in the last 24 h, then the item whose
    level matches the KC's current level. None when every item was answered recently."""
    items = content.items(kc_id)
    if not items:
        return None
    if student_id is None:  # unpersonalized: nothing is recorded, so any item will do
        return min(items, key=lambda i: (i.level != (kc_level or "basic"), i.id))
    answered = repo.answered_items(student_id)  # item_id -> last answered
    recent = utcnow() - REPEAT_AFTER
    fresh = [i for i in items if i.id not in answered or answered[i.id] < recent]
    if not fresh:
        return None
    return min(fresh, key=lambda i: (i.id in answered, i.level != kc_level, i.id))
