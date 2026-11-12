"""The end-of-term survey (api-v2.md 3.10; course-structure.md 4.7): replaces the rating after each answer.

The instructor opens a window; each student of the course answers once inside it. Answers are anonymous
ratings only: the response row has no student ID and no time, and a separate row only records that the
student has answered (so nobody answers twice). The instructor sees averages once at least
`MIN_AGGREGATE_SIZE` students answered. The end of term exports the averages and deletes the rows.
"""
from datetime import datetime
from typing import Annotated

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, select

from app.api.v1.survey import MIN_AGGREGATE_SIZE
from app.api.v2.errors import ApiError, ErrorCode
from app.platform.access import CourseAccess, require_course_role
from app.storage.models import CourseSurveyResponse, CourseSurveySubmission, SurveyWindow, utcnow

router = APIRouter(tags=["survey"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
CourseStudent = Annotated[CourseAccess, Depends(require_course_role("student"))]
CourseMember = Annotated[CourseAccess, Depends(require_course_role("instructor", "student"))]
ITEMS = ("helpfulness", "material_relevance", "clarity", "source_confidence", "learning_effect")


class WindowIn(BaseModel):
    opens_at: datetime
    closes_at: datetime


class SurveyAnswers(BaseModel):
    """1 (not at all) to 5 (very much); no free text."""

    model_config = ConfigDict(extra="forbid")

    helpfulness: int = Field(ge=1, le=5)  # the tutor helped me learn in this course
    material_relevance: int = Field(ge=1, le=5)  # answers used the course material
    clarity: int = Field(ge=1, le=5)  # answers were clear
    source_confidence: int = Field(ge=1, le=5)  # I could check the answers against the sources
    learning_effect: int = Field(ge=1, le=5)  # I understand the course better than without it


class SurveyResults(BaseModel):
    responses: int
    min_group_size: int
    sufficient_sample: bool
    means: dict[str, float] | None = None  # only with a sufficient sample


class SurveyOut(BaseModel):
    opens_at: datetime | None
    closes_at: datetime | None
    open: bool
    answered: bool | None = None  # students: whether the caller has answered
    results: SurveyResults | None = None  # instructors only


def _engine(request: Request):
    return request.app.state.services.engine


def _window(engine, course_id: int) -> SurveyWindow | None:
    with Session(engine) as db:
        return db.get(SurveyWindow, course_id)


def _is_open(window: SurveyWindow | None) -> bool:
    return window is not None and window.opens_at <= utcnow() < window.closes_at


def survey_results(engine, course_id: int) -> SurveyResults:
    with Session(engine) as db:
        rows = db.exec(select(CourseSurveyResponse).where(CourseSurveyResponse.course_id == course_id)).all()
    enough = len(rows) >= MIN_AGGREGATE_SIZE
    means = {k: round(sum(getattr(r, k) for r in rows) / len(rows), 2) for k in ITEMS} if enough else None
    return SurveyResults(responses=len(rows), min_group_size=MIN_AGGREGATE_SIZE, sufficient_sample=enough,
                         means=means)


@router.get("/courses/{course_id}/survey", response_model=SurveyOut, operation_id="survey_get")
def get_survey(access: CourseMember, request: Request):
    engine = _engine(request)
    window = _window(engine, access.course.id)
    out = SurveyOut(opens_at=window.opens_at if window else None,
                    closes_at=window.closes_at if window else None, open=_is_open(window))
    if access.role == "instructor":
        out.results = survey_results(engine, access.course.id)
    else:
        with Session(engine) as db:
            out.answered = db.exec(select(CourseSurveySubmission).where(
                CourseSurveySubmission.course_id == access.course.id,
                CourseSurveySubmission.student_id == access.student_id)).first() is not None
    return out


@router.put("/courses/{course_id}/survey", response_model=SurveyOut, operation_id="survey_window_set")
def set_window(body: WindowIn, access: CourseInstructor, request: Request):
    """Open the survey for a time window (usually the last week of term); set again to change or close it."""
    if body.closes_at <= body.opens_at:
        raise ApiError(422, ErrorCode.invalid, "closes_at must be after opens_at")
    engine = _engine(request)
    with Session(engine) as db:
        window = db.get(SurveyWindow, access.course.id) or SurveyWindow(course_id=access.course.id,
                                                                         opens_at=body.opens_at,
                                                                         closes_at=body.closes_at)
        window.opens_at, window.closes_at = body.opens_at, body.closes_at
        window.updated_by, window.updated_at = access.account_id, utcnow()
        db.add(window)
        db.commit()
    return get_survey(access, request)


@router.post("/courses/{course_id}/survey/responses", status_code=201, response_model=SurveyOut,
             operation_id="survey_answer")
def answer(body: SurveyAnswers, access: CourseStudent, request: Request):
    engine = _engine(request)
    if not _is_open(_window(engine, access.course.id)):
        raise ApiError(409, ErrorCode.conflict, "the survey is not open")
    with Session(engine) as db:
        db.add(CourseSurveySubmission(course_id=access.course.id, student_id=access.student_id))
        db.add(CourseSurveyResponse(course_id=access.course.id, **body.model_dump()))
        try:
            db.commit()
        except IntegrityError:
            raise ApiError(409, ErrorCode.conflict, "already answered") from None
    return get_survey(access, request)
