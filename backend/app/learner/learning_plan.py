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


def change_visibility(
    state: VisibilityState, *, action: Literal["mode_a", "mode_b", "acknowledge",
                                              "opt_out", "opt_in"],
    at: datetime, actor_authorized: bool,
) -> VisibilityState:
    """Make consent transitions explicit; never expose pre-acknowledgment data."""
    if not actor_authorized or not _instant(at):
        raise VisibilityDenied("Visibility change requires an authorized actor and UTC timestamp.")
    if action == "mode_a":
        return VisibilityState(state.course_id, state.student_id, "A", None, None, False)
    if action == "mode_b":
        return VisibilityState(state.course_id, state.student_id, "B", None, None, False)
    if state.mode != "B":
        raise VisibilityDenied("Individual visibility is disabled in mode A.")
    if action in ("acknowledge", "opt_in"):
        # Opt-in is always a new consent epoch; never backdate stored visibility.
        return VisibilityState(state.course_id, state.student_id, "B", at, at, False)
    if action == "opt_out":
        return VisibilityState(state.course_id, state.student_id, "B", None, None, True)
    raise VisibilityDenied("Unsupported visibility action.")


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
