"""The student's own learning profile (design §7.4): bands, never probabilities."""
from typing import Literal

from fastapi import APIRouter, HTTPException, Response, status
from pydantic import BaseModel

from app.api.deps import ServicesDep
from app.api.v1.onboarding import KcBand
from app.auth.deps import Student
from app.core.schemas import MisconceptionRef, Preferences
from app.learner.preference import PreferenceSignal

router = APIRouter(prefix="/learner/me", tags=["learner"])

FEEDBACK = {
    "more_detail": ("detail", "detailed"),
    "shorter": ("detail", "concise"),
    "example_first": ("sequencing", "example_first"),
    "concept_first": ("sequencing", "concept_first"),
}


class OpenMisconception(BaseModel):
    """A misunderstanding the tutor is working on, in plain language (no catalog ID)."""

    kc_id: str
    statement: str
    correction: str
    status: Literal["suspected", "confirmed"]

    @classmethod
    def of(cls, ref: MisconceptionRef) -> "OpenMisconception":
        return cls(kc_id=ref.kc_id, statement=ref.statement, correction=ref.correction, status=ref.status)


class TopicProfile(BaseModel):
    topic: str
    name: str
    kcs: list[KcBand]
    misconceptions: list[OpenMisconception] = []


class Profile(BaseModel):
    personalized: bool  # False without consent: nothing is stored, so there is nothing to show
    preferences: Preferences | None = None
    topics: list[TopicProfile] = []


class FeedbackBody(BaseModel):
    action: Literal["more_detail", "shorter", "example_first", "concept_first"]


@router.get("", response_model=Profile)
def get_profile(user: Student, services: ServicesDep, topic: str | None = None):
    learner, content, sid = services.learner, services.content, user.student_id
    if not learner.has_consent(sid):
        return Profile(personalized=False)
    topics = [topic] if topic else services.settings.topics()
    out = []
    for t in topics:
        if content.topic(t) is None:
            raise HTTPException(422, "unknown topic")
        kc_ids = [k.id for k in content.kcs(t)]
        states = learner.knowledge.state(sid, kc_ids)
        out.append(TopicProfile(topic=t, name=content.topic(t).name,
                                kcs=[KcBand(kc_id=k.id, name=k.name, band=learner.band(states[k.id]))
                                     for k in content.kcs(t)],
                                misconceptions=[OpenMisconception.of(m)
                                                for m in learner.open_misconceptions(sid, kc_ids)]))
    return Profile(personalized=True, preferences=learner.preferences.get(sid), topics=out)


@router.delete("", status_code=status.HTTP_204_NO_CONTENT)
def reset_profile(user: Student, services: ServicesDep):
    """Forget the learning profile (state, evidence, preferences). The account and consent stay."""
    services.learner.reset(user.student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/preferences", response_model=Preferences)
def feedback(body: FeedbackBody, user: Student, services: ServicesDep):
    dim, value = FEEDBACK[body.action]
    prefs = services.learner.update_preferences(
        user.student_id, PreferenceSignal(dimension=dim, value=value, explicit=True, source="feedback"))
    if prefs is None:
        raise HTTPException(409, "consent required: complete onboarding first")
    return prefs
