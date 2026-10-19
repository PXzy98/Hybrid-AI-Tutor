"""Voluntary, minimal-data student feedback survey and instructor-only aggregates.

No student identifiers, question text, answer content, or free-text fields are stored.
Counts are submissions, not unique student counts; the API deliberately collects
no linking token that could be used to identify or deduplicate respondents.
"""

from fastapi import APIRouter, HTTPException, status
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import func
from sqlmodel import Session, select

from app.api.deps import ServicesDep
from app.auth.deps import Instructor, Student
from app.storage.models import SurveyResponse

router = APIRouter(tags=["survey"])
MIN_AGGREGATE_SIZE = 3


class SurveySubmission(BaseModel):
    model_config = ConfigDict(extra="forbid")

    topic: str = Field(min_length=1, max_length=64)
    helpfulness: int = Field(ge=1, le=5)
    material_relevance: int = Field(ge=1, le=5)
    clarity: int = Field(ge=1, le=5)
    source_confidence: int = Field(ge=1, le=5)


class SurveyReceipt(BaseModel):
    saved: bool


class SurveyTopicSummary(BaseModel):
    topic: str
    count: int
    sufficient_sample: bool
    mean_helpfulness: float | None = None
    mean_material_relevance: float | None = None
    mean_clarity: float | None = None
    mean_source_confidence: float | None = None


class SurveySummary(BaseModel):
    min_group_size: int
    topics: list[SurveyTopicSummary]


def _allowed_topics(services) -> list[str]:
    return list(dict.fromkeys(services.settings.topics() + services.content.topics()))


@router.post("/survey", response_model=SurveyReceipt, status_code=status.HTTP_201_CREATED)
def submit_survey(body: SurveySubmission, _: Student, services: ServicesDep):
    if body.topic not in _allowed_topics(services) or services.content.topic(body.topic) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "unknown topic")
    with Session(services.engine) as db:
        db.add(SurveyResponse(**body.model_dump()))
        db.commit()
    return SurveyReceipt(saved=True)


@router.get("/admin/survey-summary", response_model=SurveySummary)
def survey_summary(_: Instructor, services: ServicesDep):
    with Session(services.engine) as db:
        rows = db.exec(
            select(
                SurveyResponse.topic,
                func.count(SurveyResponse.id),
                func.avg(SurveyResponse.helpfulness),
                func.avg(SurveyResponse.material_relevance),
                func.avg(SurveyResponse.clarity),
                func.avg(SurveyResponse.source_confidence),
            ).group_by(SurveyResponse.topic)
        ).all()
    by_topic = {str(row[0]): row for row in rows}
    result: list[SurveyTopicSummary] = []
    for topic in _allowed_topics(services):
        row = by_topic.get(topic)
        count = int(row[1]) if row is not None else 0
        enough = count >= MIN_AGGREGATE_SIZE
        result.append(
            SurveyTopicSummary(
                topic=topic,
                count=count,
                sufficient_sample=enough,
                mean_helpfulness=round(float(row[2]), 2) if enough else None,
                mean_material_relevance=round(float(row[3]), 2) if enough else None,
                mean_clarity=round(float(row[4]), 2) if enough else None,
                mean_source_confidence=round(float(row[5]), 2) if enough else None,
            )
        )
    return SurveySummary(min_group_size=MIN_AGGREGATE_SIZE, topics=result)
