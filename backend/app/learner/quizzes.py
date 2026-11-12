"""Quizzes (course-structure.md 4.6; guide 4.9): progress checks the instructor writes or drafts with AI.

Multiple choice and true/false only, graded automatically, for progress only (never a grade). A quiz is a
draft until the instructor publishes it; AI-drafted questions must be reviewed first. Students see a
published quiz assigned to them while it is open, without the answers; each student answers once. With
the student's consent the answers also update the knowledge model (strong evidence, source `quiz`).

What the instructor sees of the results follows the overview rules (course-structure.md 4.5): aggregates
of the class (small groups suppressed), and individual results only in visibility mode B, after the
student's acknowledgement, without an opt-out, from attempts after `visible_since`, each view audited.
A `final` quiz is the end-of-term post-test: its results are compared with the course diagnostic (the
pre-test, onboarding answers).
"""
from collections.abc import Sequence
from dataclasses import dataclass
from datetime import datetime
from statistics import mean
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, model_validator
from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.learner import course_views
from app.learner.visibility_policy import VisibilityDenied, instructor_visible_records
from app.storage.models import AuditLog, EvidenceLog, Quiz, QuizAttempt, utcnow

QuestionKind = Literal["mcq", "true_false"]
TRUE_FALSE = ["True", "False"]
MAX_QUESTIONS = 50


class QuizError(ValueError):
    """A request that the quiz's state does not allow (HTTP 409 or 422)."""


class QuizQuestion(BaseModel):
    """A question as stored and as the instructor edits it."""

    model_config = ConfigDict(extra="forbid")

    kind: QuestionKind
    kc: str | None = Field(None, max_length=64)  # KC code of the course; None: not linked to a KC
    stem: str = Field(min_length=3, max_length=900)
    options: list[str] = Field(default_factory=list, max_length=6)  # true/false: set to True, False
    answer: int = Field(ge=0, le=5)  # index into options
    explanation: str = Field("", max_length=1000)
    sources: list[str] = Field(default_factory=list, max_length=12)  # material file names (AI drafts)
    reviewed: bool = True  # False for AI drafts until the instructor saves them

    @model_validator(mode="after")
    def _check(self) -> "QuizQuestion":
        if self.kind == "true_false":
            self.options = list(TRUE_FALSE)
            if self.answer > 1:
                raise ValueError("a true/false answer is 0 (True) or 1 (False)")
            return self
        options = [o.strip() for o in self.options]
        if not 2 <= len(options) <= 6 or any(not o or len(o) > 300 for o in options):
            raise ValueError("a multiple choice question has 2 to 6 options of at most 300 characters")
        if len({o.casefold() for o in options}) != len(options):
            raise ValueError("options must differ")
        if self.answer >= len(options):
            raise ValueError("the answer must be one of the options")
        self.options = options
        return self


class PublicQuestion(BaseModel):
    """A question as a student sees it before answering: no answer, no explanation."""

    kind: QuestionKind
    stem: str
    options: list[str]


def check_questions(questions: Sequence[QuizQuestion], known_kcs: set[str]) -> None:
    if len(questions) > MAX_QUESTIONS:
        raise QuizError(f"a quiz has at most {MAX_QUESTIONS} questions")
    unknown = sorted({q.kc for q in questions if q.kc is not None and q.kc not in known_kcs})
    if unknown:
        raise QuizError("unknown KC codes: " + ", ".join(unknown))


def questions_of(quiz: Quiz) -> list[QuizQuestion]:
    return [QuizQuestion.model_validate(q) for q in quiz.questions or []]


def public_questions(quiz: Quiz) -> list[PublicQuestion]:
    return [PublicQuestion(kind=q.kind, stem=q.stem, options=q.options) for q in questions_of(quiz)]


def is_open(quiz: Quiz, now: datetime | None = None) -> bool:
    now = now or utcnow()
    return (quiz.status == "published" and (quiz.opens_at is None or quiz.opens_at <= now)
            and (quiz.closes_at is None or now < quiz.closes_at))


def is_assigned(quiz: Quiz, student_id: str) -> bool:
    return quiz.assigned_to is None or student_id in quiz.assigned_to


def can_publish(quiz: Quiz) -> None:
    questions = questions_of(quiz)
    if not questions:
        raise QuizError("a quiz needs at least one question")
    if not all(q.reviewed for q in questions):
        raise QuizError("review the AI-drafted questions before publishing")


def grade(questions: Sequence[QuizQuestion], answers: Sequence[int]) -> list[bool]:
    if len(answers) != len(questions):
        raise QuizError("answer every question once")
    out = []
    for q, a in zip(questions, answers, strict=True):
        if not 0 <= a < len(q.options):
            raise QuizError("an answer is not one of the options")
        out.append(a == q.answer)
    return out


def attempts(engine: Engine, quiz_id: int) -> list[QuizAttempt]:
    with Session(engine) as db:
        return list(db.exec(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id)
                            .order_by(col(QuizAttempt.id))).all())


def own_attempt(engine: Engine, quiz_id: int, student_id: str) -> QuizAttempt | None:
    with Session(engine) as db:
        return db.exec(select(QuizAttempt).where(QuizAttempt.quiz_id == quiz_id,
                                                 QuizAttempt.student_id == student_id)).first()


# ------------------------------------------------------------------------------------------- results
class QuestionStat(BaseModel):
    position: int
    kc: str | None
    correct_rate: float


class StudentResult(BaseModel):
    student_id: str
    score: int
    total: int
    submitted_at: datetime
    pre_test: float | None = None  # final quizzes: the student's diagnostic share correct, if visible


class QuizResults(BaseModel):
    quiz_id: int
    attempts: int
    sufficient_sample: bool  # False: fewer attempts than the class summary's minimum group
    min_group_size: int
    mean_score: float | None = None  # share correct, 0..1
    questions: list[QuestionStat] = []
    pre_post: dict | None = None  # final quizzes: {"students", "pre_mean", "post_mean"}
    students: list[StudentResult] = []  # only students who are visible to the instructor


@dataclass(frozen=True)
class _Record:
    """An attempt or a diagnostic answer as a visibility record (no text)."""

    course_id: int
    student_id: str
    created_at: datetime
    value: object


def _diagnostic(engine: Engine, course_id: int, student_ids: Sequence[str]) -> dict[str, list[_Record]]:
    """The course diagnostic (pre-test): onboarding answers per student."""
    out: dict[str, list[_Record]] = {}
    if not student_ids:
        return out
    with Session(engine) as db:
        rows = db.exec(select(EvidenceLog).where(EvidenceLog.course_id == course_id,
                                                 EvidenceLog.kind == "diagnostic",
                                                 col(EvidenceLog.student_id).in_(list(student_ids)))).all()
    for r in rows:
        if r.correct is not None:
            out.setdefault(r.student_id, []).append(_Record(course_id, r.student_id, r.created_at,
                                                            bool(r.correct)))
    return out


def _share(records: Sequence[_Record]) -> float | None:
    return round(mean(1.0 if r.value else 0.0 for r in records), 3) if records else None


def quiz_results(engine: Engine, quiz: Quiz, *, viewer_account_id: int, min_group: int) -> QuizResults:
    rows = attempts(engine, quiz.id)
    out = QuizResults(quiz_id=quiz.id, attempts=len(rows), sufficient_sample=len(rows) >= min_group,
                      min_group_size=min_group)
    if out.sufficient_sample and rows:
        out.mean_score = round(mean(r.score / r.total for r in rows if r.total), 3)
        for i, q in enumerate(questions_of(quiz)):
            answered = [r.correct[i] for r in rows if i < len(r.correct)]
            if answered:
                out.questions.append(QuestionStat(position=i, kc=q.kc,
                                                  correct_rate=round(mean(map(float, answered)), 3)))
    pre = _diagnostic(engine, quiz.course_id, [r.student_id for r in rows]) if quiz.kind == "final" else {}
    if quiz.kind == "final":
        pairs = [(_share(pre[r.student_id]), r.score / r.total) for r in rows
                 if r.total and pre.get(r.student_id)]
        if len(pairs) >= min_group:
            out.pre_post = {"students": len(pairs), "pre_mean": round(mean(p for p, _ in pairs), 3),
                            "post_mean": round(mean(q for _, q in pairs), 3)}
        else:
            out.pre_post = {"students": len(pairs), "pre_mean": None, "post_mean": None}

    def audit(cid: int, sid: str) -> bool:
        with Session(engine) as db:
            db.add(AuditLog(account_id=viewer_account_id, action="learner.quiz_results.view",
                            target=f"course:{cid}", details={"student_id": sid, "quiz_id": quiz.id}))
            db.commit()
        return True

    for r in rows:
        state = course_views.visibility_state(engine, quiz.course_id, r.student_id)
        if state is None:
            continue
        records = [_Record(quiz.course_id, r.student_id, r.submitted_at, r), *pre.get(r.student_id, [])]
        try:
            shown = instructor_visible_records(state=state, records=records, authorized_instructor=True,
                                               audit_view=audit)
        except VisibilityDenied:
            continue  # mode A, not acknowledged, opted out
        if not any(s.value is r for s in shown):
            continue  # answered before the student became visible
        visible_pre = [s for s in shown if s.value is not r]
        out.students.append(StudentResult(student_id=r.student_id, score=r.score, total=r.total,
                                          submitted_at=r.submitted_at, pre_test=_share(visible_pre)))
    return out
