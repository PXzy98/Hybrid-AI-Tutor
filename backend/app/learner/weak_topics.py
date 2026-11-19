"""Topics the class finds hard (v5 V8, instructor side of the closed loop).

From the published quizzes' answers: per knowledge component, how many different students answered one of its
questions and the share of correct answers. A KC is listed only when at least the minimum group answered it
and the share is below WEAK_BELOW, so nothing points at one student. The instructor can then draft extra
material on it (AI assistant, custom request); no student is named, no individual result is used.
"""
from dataclasses import dataclass

from sqlalchemy import Engine
from sqlmodel import Session, col, select

from app.storage.models import Kc, Quiz, QuizAttempt

WEAK_BELOW = 0.6  # share of correct answers under which a KC counts as hard for the class


@dataclass(frozen=True)
class WeakTopic:
    kc_code: str
    name: str
    module_id: int | None
    students: int  # different students who answered a question of this KC (at least the minimum group)
    correct_rate: float


def weak_topics(engine: Engine, course_id: int, min_group: int) -> list[WeakTopic]:
    with Session(engine) as db:
        quizzes = {q.id: q for q in db.exec(select(Quiz).where(Quiz.course_id == course_id,
                                                                Quiz.status != "draft")).all()}
        attempts = db.exec(select(QuizAttempt).where(col(QuizAttempt.quiz_id).in_(list(quizzes)))).all() \
            if quizzes else []
        kcs = {k.code: k for k in db.exec(select(Kc).where(Kc.course_id == course_id)).all()}
    answers: dict[str, list[bool]] = {}
    students: dict[str, set[str]] = {}
    for attempt in attempts:
        for question, correct in zip(quizzes[attempt.quiz_id].questions, attempt.correct, strict=False):
            code = question.get("kc")
            if code in kcs:
                answers.setdefault(code, []).append(bool(correct))
                students.setdefault(code, set()).add(attempt.student_id)
    out = []
    for code, given in answers.items():
        rate = sum(given) / len(given)
        if len(students[code]) >= min_group and rate < WEAK_BELOW:
            kc = kcs[code]
            out.append(WeakTopic(code, kc.name, kc.module_id, len(students[code]), round(rate, 3)))
    return sorted(out, key=lambda w: (w.correct_rate, w.kc_code))
