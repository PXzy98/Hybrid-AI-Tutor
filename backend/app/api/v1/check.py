"""Answer a check question (design §7.2): graded by the key, applied as strong evidence. No LLM, no cloud."""
from typing import Literal

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

from app.api.deps import ServicesDep
from app.auth.deps import Student
from app.core.schemas import KcRecommendation, Level
from app.learner.checks import evidence_for, grade

router = APIRouter(tags=["learner"])


class CheckBody(BaseModel):
    session_id: str = Field("", max_length=64)
    item_id: str
    choice: Literal["A", "B", "C", "D"]


class CheckResponse(BaseModel):
    correct: bool
    correct_choice: str
    explanation: str
    kc_id: str
    kc_level: Level | None = None  # None without consent (nothing is recorded)
    kc_band: str | None = None  # basic | intermediate | advanced | mastered
    next_kc: KcRecommendation | None = None


@router.post("/check", response_model=CheckResponse)
def check(body: CheckBody, user: Student, services: ServicesDep):
    content, learner = services.content, services.learner
    item = content.item(body.item_id)
    if item is None or item not in content.items(item.kc):  # unknown, or not servable (unreviewed)
        raise HTTPException(404, "check question not found")
    owner = services.sessions.owner(body.session_id) if body.session_id else None
    if owner is not None and owner != user.student_id:
        raise HTTPException(404, "session not found")
    graded = grade(item, body.choice)
    state = learner.observe(user.student_id, evidence_for(item, graded, "strong", "check"))
    learner.check_answered(user.student_id, item, graded)  # confirm / resolve misconceptions (Step 12)
    topic = content.topic_of(item.kc)
    next_kc = learner.recommender.next_kc(user.student_id, topic) if state else None
    return CheckResponse(correct=graded.correct, correct_choice=graded.correct_choice,
                         explanation=item.explanation, kc_id=item.kc,
                         kc_level=state.level if state else None,
                         kc_band=learner.band(state) if state else None, next_kc=next_kc)
