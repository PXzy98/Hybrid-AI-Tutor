"""Instructor AI tier 4 endpoints (api-v2.md 3.7; guide 4.9; task Z12) and background job status (api-v2.md
3.4).

Flow: `POST .../ai/evaluations` starts the question generation (local model only) -> the evaluation waits in
`review` -> the instructor edits the questions (`PUT .../questions`) -> `POST .../run` with
`confirm_cloud: true` (course material and the questions go to the cloud model; refused when the course is
local only) -> `done` with a report -> optional spot checks (`PATCH .../results/{question_id}`).
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlmodel import Session, col, select

from app.api.v2.errors import ApiError, ErrorCode
from app.instructor_ai import eval as tier4
from app.platform import jobs
from app.platform.access import CourseAccess, require_course_role
from app.storage.models import AiEvaluation, Module, utcnow

router = APIRouter(tags=["instructor-ai"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
QuestionType = Literal["concept", "application", "logistics"]


class EvaluationIn(BaseModel):
    module_ids: list[int] | None = None  # None: every module with material
    questions_per_module: int = Field(5, ge=1, le=20)
    question_types: list[QuestionType] | None = None


class QuestionIn(BaseModel):
    module_id: int
    type: QuestionType
    question: str = Field(min_length=1, max_length=500)
    reference: str = Field("", max_length=800)


class QuestionsIn(BaseModel):
    questions: list[QuestionIn] = Field(max_length=200)


class RunIn(BaseModel):
    # the instructor's consent: course material and these questions go to the cloud model and the judge
    confirm_cloud: bool = False


class SpotCheckIn(BaseModel):
    agrees_with_judge: bool
    note: str = Field("", max_length=500)


class EvaluationOut(BaseModel):
    id: int
    status: Literal["generating", "review", "running", "done", "failed"]
    options: dict
    questions: list[dict]
    results: list[dict]
    report: dict
    error: str | None
    created_at: datetime
    updated_at: datetime
    job_id: int | None = None  # the job started by this request


class EvaluationSummary(BaseModel):
    id: int
    status: str
    questions: int
    created_at: datetime
    updated_at: datetime


class JobOut(BaseModel):
    id: int
    kind: str
    status: Literal["queued", "running", "done", "failed"]
    progress: int
    error: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None


def _engine(request: Request):
    return request.app.state.services.engine


def _out(row: AiEvaluation, job_id: int | None = None) -> EvaluationOut:
    return EvaluationOut(id=row.id, status=row.status, options=row.options, questions=row.questions,
                         results=row.results, report=row.report, error=row.error, created_at=row.created_at,
                         updated_at=row.updated_at, job_id=job_id)


def _get(db: Session, course_id: int, evaluation_id: int) -> AiEvaluation:
    row = db.get(AiEvaluation, evaluation_id)
    if row is None or row.course_id != course_id:
        raise ApiError(404, ErrorCode.not_found, "evaluation not found")
    return row


def _course_modules(db: Session, course_id: int, ids: list[int]) -> None:
    found = set(db.exec(select(Module.id).where(Module.course_id == course_id, col(Module.id).in_(ids))))
    if set(ids) - found:
        raise ApiError(422, ErrorCode.invalid, "a module is not part of this course")


@router.post("/courses/{course_id}/ai/evaluations", response_model=EvaluationOut, status_code=202,
             operation_id="ai_evaluations_create")
def create(request: Request, body: EvaluationIn, access: CourseInstructor):
    """Start writing test questions from the course material with the local model."""
    engine = _engine(request)
    with Session(engine, expire_on_commit=False) as db:
        if body.module_ids:
            _course_modules(db, access.course.id, body.module_ids)
        row = AiEvaluation(course_id=access.course.id, created_by=access.account_id, status="generating",
                           options=body.model_dump(exclude_none=True))
        db.add(row)
        db.commit()
    job = jobs.enqueue(engine, tier4.GENERATE, course_id=access.course.id, ref_id=row.id,
                       created_by=access.account_id)
    return _out(row, job.id)


@router.get("/courses/{course_id}/ai/evaluations", response_model=list[EvaluationSummary],
            operation_id="ai_evaluations_list")
def list_evaluations(request: Request, access: CourseInstructor):
    with Session(_engine(request)) as db:
        rows = db.exec(select(AiEvaluation).where(AiEvaluation.course_id == access.course.id)
                       .order_by(col(AiEvaluation.id).desc())).all()
        return [EvaluationSummary(id=r.id, status=r.status, questions=len(r.questions),
                                  created_at=r.created_at, updated_at=r.updated_at) for r in rows]


@router.get("/courses/{course_id}/ai/evaluations/{evaluation_id}", response_model=EvaluationOut,
            operation_id="ai_evaluations_get")
def get_evaluation(request: Request, evaluation_id: int, access: CourseInstructor):
    with Session(_engine(request)) as db:
        return _out(_get(db, access.course.id, evaluation_id))


@router.put("/courses/{course_id}/ai/evaluations/{evaluation_id}/questions", response_model=EvaluationOut,
            operation_id="ai_evaluations_set_questions")
def set_questions(request: Request, evaluation_id: int, body: QuestionsIn, access: CourseInstructor):
    """The instructor's review: the full list of questions to run (edited, removed or added)."""
    with Session(_engine(request), expire_on_commit=False) as db:
        row = _get(db, access.course.id, evaluation_id)
        if row.status != "review":
            raise ApiError(409, ErrorCode.conflict, "questions can be changed only while in review")
        _course_modules(db, access.course.id, [q.module_id for q in body.questions])
        modules = db.exec(select(Module).where(Module.course_id == access.course.id)).all()
        titles = {m.id: m.title for m in modules}
        row.questions = [{"id": i + 1, "module_id": q.module_id, "module": titles[q.module_id],
                          "type": q.type, "question": q.question, "reference": q.reference}
                         for i, q in enumerate(body.questions)]
        row.updated_at = utcnow()
        db.add(row)
        db.commit()
        return _out(row)


@router.post("/courses/{course_id}/ai/evaluations/{evaluation_id}/run", response_model=EvaluationOut,
             status_code=202, operation_id="ai_evaluations_run",
             responses={409: {"description": "not in review, no questions, or the course is local only"}})
def run(request: Request, evaluation_id: int, body: RunIn, access: CourseInstructor):
    """Answer every question with the local and the cloud model and score them (needs `confirm_cloud`)."""
    engine = _engine(request)
    if request.app.state.services.effective(access.course.id).local_only:
        raise ApiError(409, ErrorCode.conflict, "this course uses the local model only: no cloud comparison")
    if not body.confirm_cloud:
        raise ApiError(422, ErrorCode.invalid, "confirm that course material and these questions may go to "
                                               "the cloud model (confirm_cloud)")
    with Session(engine, expire_on_commit=False) as db:
        _get(db, access.course.id, evaluation_id)  # 404 for another course's evaluation
        # locked while checked, so two requests cannot both start it (one run, one job)
        row = db.exec(select(AiEvaluation).where(AiEvaluation.id == evaluation_id).with_for_update()).one()
        if row.status != "review" or not row.questions:
            raise ApiError(409, ErrorCode.conflict, "the evaluation must be in review and have questions")
        row.status, row.updated_at = "running", utcnow()
        row.options = {**row.options, "cloud_confirmed_by": access.account_id}
        db.add(row)
        db.commit()
    job = jobs.enqueue(engine, tier4.RUN, course_id=access.course.id, ref_id=row.id,
                       created_by=access.account_id)
    return _out(row, job.id)


@router.patch("/courses/{course_id}/ai/evaluations/{evaluation_id}/results/{question_id}",
              response_model=EvaluationOut, operation_id="ai_evaluations_spot_check")
def spot_check(request: Request, evaluation_id: int, question_id: int, body: SpotCheckIn,
               access: CourseInstructor):
    """The instructor's spot check of one scored question (counted in the report)."""
    with Session(_engine(request), expire_on_commit=False) as db:
        row = _get(db, access.course.id, evaluation_id)
        results = [dict(r) for r in row.results]
        target = next((r for r in results if r["question_id"] == question_id), None)
        if row.status != "done" or target is None:
            raise ApiError(404, ErrorCode.not_found, "result not found")
        target["spot_check"] = body.model_dump()
        row.results, row.report, row.updated_at = results, tier4.report(results), utcnow()
        db.add(row)
        db.commit()
        return _out(row)


@router.get("/courses/{course_id}/jobs/{job_id}", response_model=JobOut, operation_id="jobs_get")
def get_job(request: Request, job_id: int, access: CourseInstructor):
    job = jobs.get(_engine(request), job_id, access.course.id)
    if job is None:
        raise ApiError(404, ErrorCode.not_found, "job not found")
    return JobOut(id=job.id, kind=job.kind, status=job.status, progress=job.progress, error=job.error,
                  created_at=job.created_at, started_at=job.started_at, finished_at=job.finished_at)
