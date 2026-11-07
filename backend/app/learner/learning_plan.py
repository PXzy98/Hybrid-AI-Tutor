"""Offline S9 course visibility transitions and instructor learning-plan guards.

Permissions, durable database writes and audits must be provided by the Z-owned
course platform. No raw student question or learner session text is stored here.
"""
from dataclasses import dataclass
from datetime import datetime
from typing import Literal

from app.learner.visibility_policy import VisibilityDenied, VisibilityState

PlanLevel = Literal["basic", "intermediate", "advanced"]


@dataclass(frozen=True)
class LearningPlan:
    course_id: int
    student_id: str
    focus_kcs: tuple[str, ...]
    goal: PlanLevel
    notes: str
    created_at: datetime


def _instant(value: datetime) -> bool:
    return value.tzinfo is not None and value.utcoffset() is not None


Actor = Literal["student", "instructor"]
_ACTIONS: dict[str, Actor] = {
    "mode_a": "instructor", "mode_b": "instructor",  # the course's mode
    "acknowledge": "student", "opt_out": "student", "opt_in": "student",  # the student's own choices
}


def change_visibility(
    state: VisibilityState, *, action: Literal["mode_a", "mode_b", "acknowledge",
                                              "opt_out", "opt_in"],
    at: datetime, actor: Actor, actor_authorized: bool,
) -> VisibilityState:
    """Make consent transitions explicit; never expose pre-acknowledgment data.

    Only the instructor switches the mode and only the student himself acknowledges, opts out or opts
    back in (course-structure.md 4.5). The opt-out is the student's choice: it survives mode switches
    and a repeated acknowledgement, and only his own opt-in ends it.
    """
    if not actor_authorized or not _instant(at):
        raise VisibilityDenied("Visibility change requires an authorized actor and UTC timestamp.")
    if _ACTIONS.get(action) is None:
        raise VisibilityDenied("Unsupported visibility action.")
    if _ACTIONS[action] != actor:
        raise VisibilityDenied("This visibility change belongs to the other role.")
    cid, sid, hidden = state.course_id, state.student_id, state.hidden_from_instructor
    if action == "mode_a":
        return VisibilityState(cid, sid, "A", None, None, hidden)
    if action == "mode_b":
        # Switching to B again keeps every acknowledgement; from A it starts without consent.
        return state if state.mode == "B" else VisibilityState(cid, sid, "B", None, None, hidden)
    if action == "opt_out":
        return VisibilityState(cid, sid, state.mode, state.acknowledged_at, None, True)
    if state.mode != "B":
        if action == "opt_in":
            return VisibilityState(cid, sid, "A", None, None, False)
        raise VisibilityDenied("Individual visibility is disabled in mode A.")
    if action == "acknowledge":
        if hidden:  # acknowledging the notice does not end an opt-out
            return VisibilityState(cid, sid, "B", at, None, True)
        if state.acknowledged_at is not None and state.visible_since is not None:
            return state  # already acknowledged: the visibility window does not move
        return VisibilityState(cid, sid, "B", at, at, False)
    # opt_in in mode B: always a new consent epoch; never backdate stored visibility.
    return VisibilityState(cid, sid, "B", at, at, False)


def visible_learning_plan(state: VisibilityState, plan: LearningPlan | None) -> LearningPlan | None:
    """The plan to show (student and instructor), or None: no plan in mode A, after an opt-out, or from
    before the current consent epoch."""
    if plan is None or state.mode != "B" or state.hidden_from_instructor or state.visible_since is None:
        return None
    if (plan.course_id, plan.student_id) != (state.course_id, state.student_id):
        return None
    return plan if plan.created_at >= state.visible_since else None


def validate_learning_plan(
    *, state: VisibilityState, plan: LearningPlan, known_kcs: set[str],
    authorized_instructor: bool, audit_update,
) -> LearningPlan:
    """Validate a plan update only after consent, scope, and durable audit checks.

    Must run behind require_course_role; audit_update persists the event and
    returns exactly True. The caller persists the validated plan transactionally.
    """
    if not authorized_instructor or state.mode != "B" or state.hidden_from_instructor:
        raise VisibilityDenied("Learning plan is unavailable.")
    if (state.course_id != plan.course_id or state.student_id != plan.student_id
            or not state.student_id):
        raise VisibilityDenied("Learning plan scope mismatch.")
    if state.acknowledged_at is None or state.visible_since is None:
        raise VisibilityDenied("Student has not acknowledged individual visibility.")
    if not (_instant(state.acknowledged_at) and _instant(state.visible_since)
            and _instant(plan.created_at)):
        raise VisibilityDenied("Invalid consent or plan timestamp.")
    if state.visible_since < state.acknowledged_at or plan.created_at < state.visible_since:
        raise VisibilityDenied("Plan predates student visibility consent.")
    if plan.goal not in ("basic", "intermediate", "advanced"):
        raise VisibilityDenied("Invalid plan goal.")
    if not (1 <= len(plan.focus_kcs) <= 8) or len(set(plan.focus_kcs)) != len(plan.focus_kcs):
        raise VisibilityDenied("Invalid focus KC list.")
    if not set(plan.focus_kcs) <= known_kcs:
        raise VisibilityDenied("Learning plan references another or unknown KC.")
    if len(plan.notes) > 500:
        raise VisibilityDenied("Learning plan note is too long.")
    if audit_update is None or audit_update(state.course_id, state.student_id) is not True:
        raise VisibilityDenied("Plan update must be audited before persistence.")
    return plan
