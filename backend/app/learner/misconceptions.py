"""Misconception tracking and corrections (design §5.1, §6, §8.1).

Status per (student, catalog ID):

| Signal | none / resolved | suspected | confirmed |
|---|---|---|---|
| weak (the understand step tagged it) | suspected | confirmed (second signal) | confirmed |
| a distractor tagged with it was chosen | confirmed | confirmed | confirmed |
| a correct answer on an item that targets it | – | resolved | resolved |

Only catalog IDs and counts are stored. Statements and corrections come from the catalog and are shown to
students (and given to the local model) only when content.servable() allows it. The cloud never sees them:
on the cloud route the correction is appended locally after the answer comes back.
"""
import re

from app.core.schemas import MisconceptionRef, RequestContext
from app.learner.content import ContentStore, Item
from app.learner.repository import LearnerRepository
from app.storage.models import LearnerMisconception

OPEN = ("suspected", "confirmed")
MAX_IN_PROMPT = 2  # open misconceptions addressed in one answer

NOTE_HEADER = "A common misunderstanding to watch for:"
STOPWORDS = set("""about after again also always another because before being between blood could doctor
doesn every first from have having however into itself least might more most much often only other pressure
should since some something still such than that their them then there these they this those though through
under usually very what when where whether which while with without would your""".split())
WORD_RE = re.compile(r"[a-z]{5,}")
ADDRESSED_SHARE = 0.5  # share of the correction's key words an answer must contain to count as addressing it


class MisconceptionTracker:
    def __init__(self, repo: LearnerRepository, content: ContentStore) -> None:
        self.repo = repo
        self.content = content

    def _row(self, student_id: str, mc_id: str) -> LearnerMisconception | None:
        mc = self.content.misconception(mc_id)
        if mc is None:
            return None
        return self.repo.misconception(student_id, mc_id) or LearnerMisconception(
            student_id=student_id, misconception_id=mc_id, kc_id=mc.kc, status="resolved", evidence_count=0)

    def weak_signal(self, student_id: str, mc_id: str) -> str | None:
        """The student stated this misconception (understand step). Returns the new status."""
        row = self._row(student_id, mc_id)
        if row is None:
            return None
        if row.status in OPEN:
            row.status, row.evidence_count = "confirmed", row.evidence_count + 1
        else:  # new, or reopened after it was resolved
            row.status, row.evidence_count = "suspected", 1
        self.repo.save_misconception(row)
        return row.status

    def distractor_chosen(self, student_id: str, mc_id: str) -> str | None:
        """A check answer picked a distractor tagged with this misconception: strong evidence."""
        row = self._row(student_id, mc_id)
        if row is None:
            return None
        row.evidence_count = row.evidence_count + 1 if row.status in OPEN else 1
        row.status = "confirmed"
        self.repo.save_misconception(row)
        return row.status

    def answered_correctly(self, student_id: str, item: Item) -> list[str]:
        """A correct answer on an item whose distractors target open misconceptions resolves them."""
        resolved = []
        for mc_id in sorted(self.content.targeted_misconceptions(item)):
            row = self.repo.misconception(student_id, mc_id)
            if row is not None and row.status in OPEN:
                row.status = "resolved"
                self.repo.save_misconception(row)
                resolved.append(mc_id)
        return resolved

    def open_ids(self, student_id: str) -> set[str]:
        return {r.misconception_id for r in self.repo.misconceptions(student_id, OPEN)}

    def refs(self, student_id: str, kc_ids: list[str], limit: int | None = None) -> list[MisconceptionRef]:
        """Open misconceptions of the given KCs that may be shown: confirmed first, then the most recent."""
        rows = [r for r in self.repo.misconceptions(student_id, OPEN) if r.kc_id in kc_ids]
        rows.sort(key=lambda r: r.status != "confirmed")  # stable: keeps most-recent order within a status
        out = []
        for r in rows:
            mc = self.content.misconception(r.misconception_id)
            if mc and self.content.servable(mc):
                out.append(MisconceptionRef(id=mc.id, kc_id=mc.kc, statement=mc.statement,
                                            correction=mc.correction, status=r.status))
        return out[:limit] if limit else out


# ---------------------------------------------------------------------- prompt and answer
def prompt_block(refs: list[MisconceptionRef]) -> str:
    """For the LOCAL prompt only: one "address this misunderstanding" line per open misconception."""
    lines = [f'- Address this misunderstanding the student may have: "{m.statement}" '
             f"Correct it gently with this reviewed correction: {m.correction}" for m in refs]
    return "Known misunderstandings:\n" + "\n".join(lines) if lines else ""


def key_words(text: str) -> set[str]:
    return {w for w in WORD_RE.findall(text.lower()) if w not in STOPWORDS}


def addresses(answer: str, correction: str) -> bool:
    """Keyword check: does the answer already say what the correction says?"""
    words = key_words(correction)
    return bool(words) and len(words & key_words(answer)) / len(words) >= ADDRESSED_SHARE


def append_corrections(ctx: RequestContext) -> None:
    """Cloud route: append the reviewed correction of each relevant open misconception the answer does not
    already address. Runs locally after the answer is back, so the cloud request never contains it."""
    learner = ctx.learner if ctx.learner and ctx.learner.personalized else None
    if ctx.target != "cloud" or not learner or not learner.misconceptions or not ctx.answer:
        return
    notes = [m.correction for m in learner.misconceptions if not addresses(ctx.answer, m.correction)]
    if notes:
        ctx.answer = ctx.answer.rstrip() + "\n\n" + NOTE_HEADER + " " + " ".join(notes)
