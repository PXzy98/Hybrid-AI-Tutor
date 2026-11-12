"""Quizzes (api-v2.md 3.9; course-structure.md 4.6): instructors write or AI-draft quizzes and see the
results; students answer published quizzes once. Multiple choice and true/false, graded automatically,
for progress only (not a grade)."""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field
from sqlalchemy.exc import IntegrityError
from sqlmodel import Session, col, select

from app.api.v2.ask import _scope
from app.api.v2.errors import ApiError, ErrorCode
from app.core.schemas import Evidence
from app.instructor_ai.quiz_drafts import DRAFT
from app.learner import quizzes as core
from app.learner.quizzes import PublicQuestion, QuizError, QuizQuestion, QuizResults
from app.platform import jobs
from app.platform.access import CourseAccess, require_course_role
from app.storage.models import Module, Quiz, QuizAttempt, utcnow

router = APIRouter(tags=["quizzes"])
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
CourseStudent = Annotated[CourseAccess, Depends(require_course_role("student"))]
CourseMember = Annotated[CourseAccess, Depends(require_course_role("instructor", "student"))]
QuizKind = Literal["practice", "final"]
QuizStatus = Literal["draft", "published", "closed"]


class QuizIn(BaseModel):
    title: str = Field(min_length=1, max_length=200)
    module_id: int | None = None  # None: the whole course
    kind: QuizKind = "practice"
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    assigned_to: list[str] | None = Field(None, max_length=1000)  # student_ids; None: every student
    questions: list[QuizQuestion] = Field(default_factory=list, max_length=core.MAX_QUESTIONS)


class QuizPatch(BaseModel):
    title: str | None = Field(None, min_length=1, max_length=200)
    module_id: int | None = None
    kind: QuizKind | None = None
    status: QuizStatus | None = None
    opens_at: datetime | None = None
    closes_at: datetime | None = None
    assigned_to: list[str] | None = Field(None, max_length=1000)
    questions: list[QuizQuestion] | None = Field(None, max_length=core.MAX_QUESTIONS)


class QuizOut(BaseModel):
    """The instructor's view: answers and explanations included."""

    id: int
    title: str
    module_id: int | None
    kind: QuizKind
    status: QuizStatus
    opens_at: datetime | None
    closes_at: datetime | None
    assigned_to: list[str] | None
    questions: list[QuizQuestion]
    attempts: int
    created_at: datetime
    updated_at: datetime


class AttemptResult(BaseModel):
    correct: bool
    chosen: int
    answer: int
    explanation: str


class OwnAttempt(BaseModel):
    score: int
    total: int
    submitted_at: datetime
    results: list[AttemptResult]


class StudentQuizOut(BaseModel):
    """The student's view: no answers before the student has answered."""

    id: int
    title: str
    module_id: int | None
    kind: QuizKind
    open: bool
    opens_at: datetime | None
    closes_at: datetime | None
    questions: list[PublicQuestion] = []  # while open, and after the student has answered
    attempt: OwnAttempt | None = None


class DraftIn(BaseModel):
    count: int = Field(5, ge=1, le=20)
    kinds: list[Literal["mcq", "true_false"]] = Field(default_factory=lambda: ["mcq", "true_false"],
                                                      min_length=1)
    kc_codes: list[str] | None = Field(None, max_length=50)


class DraftOut(BaseModel):
    job_id: int


class AttemptIn(BaseModel):
    answers: list[int] = Field(max_length=core.MAX_QUESTIONS)


def _services(request: Request):
    return request.app.state.services


def _known_kcs(services, course_id: int) -> set[str]:
    content = _scope(services, course_id).content
    return {k.id for code in content.topics() for k in content.kcs(code)}


def _quiz(services, course_id: int, quiz_id: int) -> Quiz:
    with Session(services.engine) as db:
        quiz = db.get(Quiz, quiz_id)
    if quiz is None or quiz.course_id != course_id:
        raise ApiError(404, ErrorCode.not_found, "quiz not found")
    return quiz


def _attempt_count(services, quiz_id: int) -> int:
    return len(core.attempts(services.engine, quiz_id))


def _out(services, quiz: Quiz) -> QuizOut:
    return QuizOut(id=quiz.id, title=quiz.title, module_id=quiz.module_id, kind=quiz.kind, status=quiz.status,
                   opens_at=quiz.opens_at, closes_at=quiz.closes_at, assigned_to=quiz.assigned_to,
                   questions=core.questions_of(quiz), attempts=_attempt_count(services, quiz.id),
                   created_at=quiz.created_at, updated_at=quiz.updated_at)


def _own(quiz: Quiz, attempt: QuizAttempt) -> OwnAttempt:
    questions = core.questions_of(quiz)
    return OwnAttempt(score=attempt.score, total=attempt.total, submitted_at=attempt.submitted_at, results=[
        AttemptResult(correct=ok, chosen=chosen, answer=q.answer, explanation=q.explanation)
        for q, chosen, ok in zip(questions, attempt.answers, attempt.correct, strict=False)])


def _student_out(services, quiz: Quiz, student_id: str) -> StudentQuizOut:
    attempt = core.own_attempt(services.engine, quiz.id, student_id)
    open_now = core.is_open(quiz)
    return StudentQuizOut(id=quiz.id, title=quiz.title, module_id=quiz.module_id, kind=quiz.kind,
                          open=open_now, opens_at=quiz.opens_at, closes_at=quiz.closes_at,
                          # while open and unanswered, to answer; after answering, to read the result
                          questions=core.public_questions(quiz) if (open_now or attempt) else [],
                          attempt=_own(quiz, attempt) if attempt else None)


def _visible_to_student(quiz: Quiz, student_id: str) -> bool:
    return quiz.status in ("published", "closed") and core.is_assigned(quiz, student_id)


def _check(services, course_id: int, *, module_id: int | None, opens_at, closes_at,
           questions: list[QuizQuestion] | None) -> None:
    if module_id is not None:
        with Session(services.engine) as db:
            module = db.get(Module, module_id)
        if module is None or module.course_id != course_id:
            raise ApiError(404, ErrorCode.not_found, "module not found")
    if opens_at and closes_at and closes_at <= opens_at:
        raise ApiError(422, ErrorCode.invalid, "closes_at must be after opens_at")
    if questions is not None:
        try:
            core.check_questions(questions, _known_kcs(services, course_id))
        except QuizError as e:
            raise ApiError(422, ErrorCode.invalid, str(e)) from None


# ------------------------------------------------------------------------------------------ endpoints
@router.get("/courses/{course_id}/quizzes", response_model=list[QuizOut] | list[StudentQuizOut],
            operation_id="quizzes_list")
def list_quizzes(access: CourseMember, request: Request):
    """Instructors: every quiz of the course. Students: published quizzes assigned to them."""
    services = _services(request)
    with Session(services.engine) as db:
        rows = db.exec(select(Quiz).where(Quiz.course_id == access.course.id)
                       .order_by(col(Quiz.id).desc())).all()
    if access.role == "instructor":
        return [_out(services, q) for q in rows]
    return [_student_out(services, q, access.student_id) for q in rows
            if _visible_to_student(q, access.student_id)]


@router.post("/courses/{course_id}/quizzes", response_model=QuizOut, status_code=201,
             operation_id="quizzes_create")
def create_quiz(body: QuizIn, access: CourseInstructor, request: Request):
    services = _services(request)
    _check(services, access.course.id, module_id=body.module_id, opens_at=body.opens_at,
           closes_at=body.closes_at, questions=body.questions)
    quiz = Quiz(course_id=access.course.id, module_id=body.module_id, title=body.title, kind=body.kind,
                opens_at=body.opens_at, closes_at=body.closes_at, assigned_to=body.assigned_to,
                questions=[q.model_dump() for q in body.questions], created_by=access.account_id)
    with Session(services.engine, expire_on_commit=False) as db:
        db.add(quiz)
        db.commit()
    return _out(services, quiz)


@router.get("/courses/{course_id}/quizzes/{quiz_id}", response_model=QuizOut | StudentQuizOut,
            operation_id="quizzes_get")
def get_quiz(quiz_id: int, access: CourseMember, request: Request):
    services = _services(request)
    quiz = _quiz(services, access.course.id, quiz_id)
    if access.role == "instructor":
        return _out(services, quiz)
    if not _visible_to_student(quiz, access.student_id):
        raise ApiError(404, ErrorCode.not_found, "quiz not found")
    return _student_out(services, quiz, access.student_id)


@router.patch("/courses/{course_id}/quizzes/{quiz_id}", response_model=QuizOut, operation_id="quizzes_update")
def update_quiz(quiz_id: int, body: QuizPatch, access: CourseInstructor, request: Request):
    """Edit, publish (`status: published`, every question reviewed) or close a quiz. Saving `questions`
    marks them reviewed; questions cannot change once students have answered."""
    services = _services(request)
    quiz = _quiz(services, access.course.id, quiz_id)
    changes = body.model_dump(exclude_unset=True)
    if "questions" in changes:
        if _attempt_count(services, quiz.id):
            raise ApiError(409, ErrorCode.conflict, "students have answered: the questions cannot change")
        body.questions = [q.model_copy(update={"reviewed": True}) for q in body.questions or []]
    _check(services, access.course.id, module_id=changes.get("module_id"),
           opens_at=changes.get("opens_at", quiz.opens_at),
           closes_at=changes.get("closes_at", quiz.closes_at),
           questions=body.questions if "questions" in changes else None)
    for name in ("title", "module_id", "kind", "opens_at", "closes_at", "assigned_to"):
        if name in changes:
            setattr(quiz, name, changes[name])
    if "questions" in changes:
        quiz.questions = [q.model_dump() for q in body.questions]
    if body.status is not None and body.status != quiz.status:
        if body.status == "draft" and _attempt_count(services, quiz.id):
            raise ApiError(409, ErrorCode.conflict,
                           "students have answered: the quiz cannot be a draft again")
        if body.status == "published":
            try:
                core.can_publish(quiz)
            except QuizError as e:
                raise ApiError(409, ErrorCode.conflict, str(e)) from None
        quiz.status = body.status
    quiz.updated_at = utcnow()
    with Session(services.engine, expire_on_commit=False) as db:
        db.add(quiz)
        db.commit()
    return _out(services, quiz)


@router.delete("/courses/{course_id}/quizzes/{quiz_id}", status_code=204, operation_id="quizzes_delete")
def delete_quiz(quiz_id: int, access: CourseInstructor, request: Request):
    """Only a quiz nobody has answered (close it otherwise)."""
    services = _services(request)
    quiz = _quiz(services, access.course.id, quiz_id)
    if _attempt_count(services, quiz.id):
        raise ApiError(409, ErrorCode.conflict, "students have answered: close the quiz instead")
    with Session(services.engine) as db:
        db.delete(db.get(Quiz, quiz.id))
        db.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/courses/{course_id}/quizzes/{quiz_id}/drafts", response_model=DraftOut, status_code=202,
             operation_id="quizzes_draft")
def draft_questions(quiz_id: int, body: DraftIn, access: CourseInstructor, request: Request):
    """The local model drafts questions from the course material (a background job, `GET .../jobs/{id}`);
    they are added to the draft quiz unreviewed."""
    services = _services(request)
    quiz = _quiz(services, access.course.id, quiz_id)
    if quiz.status != "draft":
        raise ApiError(409, ErrorCode.conflict, "only a draft quiz gets AI questions")
    if body.kc_codes and not set(body.kc_codes) <= _known_kcs(services, access.course.id):
        raise ApiError(422, ErrorCode.invalid, "kc_codes must be KC codes of this course")
    with Session(services.engine) as db:
        row = db.get(Quiz, quiz.id)
        row.draft_request = body.model_dump()
        db.add(row)
        db.commit()
    job = jobs.enqueue(services.engine, DRAFT, course_id=access.course.id, ref_id=quiz.id,
                       created_by=access.account_id)
    return DraftOut(job_id=job.id)


@router.post("/courses/{course_id}/quizzes/{quiz_id}/attempt", response_model=OwnAttempt, status_code=201,
             operation_id="quizzes_attempt")
def attempt(quiz_id: int, body: AttemptIn, access: CourseStudent, request: Request):
    """Answer the quiz once, while it is open. The result comes back at once; with consent it also updates
    the knowledge model."""
    services = _services(request)
    quiz = _quiz(services, access.course.id, quiz_id)
    if not _visible_to_student(quiz, access.student_id):
        raise ApiError(404, ErrorCode.not_found, "quiz not found")
    if not core.is_open(quiz):
        raise ApiError(409, ErrorCode.conflict, "the quiz is not open")
    questions = core.questions_of(quiz)
    try:
        correct = core.grade(questions, body.answers)
    except QuizError as e:
        raise ApiError(422, ErrorCode.invalid, str(e)) from None
    row = QuizAttempt(quiz_id=quiz.id, course_id=access.course.id, student_id=access.student_id,
                      answers=list(body.answers), correct=correct, score=sum(correct), total=len(correct))
    with Session(services.engine, expire_on_commit=False) as db:
        db.add(row)
        try:
            db.commit()
        except IntegrityError:  # (quiz_id, student_id) is unique: one attempt each
            raise ApiError(409, ErrorCode.conflict, "already answered") from None
    scope = _scope(services, access.course.id)
    known = _known_kcs(services, access.course.id)
    for q, ok in zip(questions, correct, strict=True):
        if q.kc in known:  # without consent `observe` stores nothing
            scope.learner.observe(access.student_id, Evidence(kc_id=q.kc, kind="strong", correct=ok,
                                                              source="quiz"))
    return _own(quiz, row)


@router.get("/courses/{course_id}/quizzes/{quiz_id}/results", response_model=QuizResults,
            operation_id="quizzes_results")
def results(quiz_id: int, access: CourseInstructor, request: Request):
    """Class aggregates (suppressed below the minimum group) and, for students visible to the instructor
    (visibility mode B, acknowledged, not opted out), their own results; each individual view is audited."""
    services = _services(request)
    quiz = _quiz(services, access.course.id, quiz_id)
    return core.quiz_results(services.engine, quiz, viewer_account_id=access.account_id,
                             min_group=services.settings.learner.class_summary_min_group)

