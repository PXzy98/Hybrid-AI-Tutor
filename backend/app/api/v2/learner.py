"""Learner endpoints of a course (api-v2.md 3.5 and 3.6; course-structure.md 4; task S9).

Students: check answers, the course diagnostic, "What I know" in this course, the visibility choices
(acknowledge mode B, opt out, opt back in) and deleting their own data in the course.
Instructors: the class summary (aggregates, every mode), and in visibility mode B the individual overview
and the learning plan of a student who acknowledged it and did not opt out. Every individual view is
audited; a student who is not visible is answered exactly like one who does not exist (404).
"""
from datetime import datetime
from typing import Annotated, Literal

from fastapi import APIRouter, Depends, Request, Response, status
from pydantic import BaseModel, Field

from app.admin.summary import ClassSummary, class_summary
from app.api.v1.check import CheckResponse
from app.api.v1.learner_me import OpenMisconception
from app.api.v1.onboarding import (
    PREFERENCE_QUESTIONS,
    DiagnosticAnswer,
    KcBand,
    OnboardingResult,
    PreferenceAnswers,
    PreferenceQuestion,
)
from app.api.v2.ask import _scope
from app.api.v2.errors import ApiError, ErrorCode
from app.core.schemas import CheckItemPublic, Preferences
from app.learner import course_views
from app.learner.checks import diagnostic_items, evidence_for, grade
from app.learner.instructor_view import InstructorProfileView, NotVisible, profile_for_instructor
from app.learner.preference import PreferenceSignal
from app.learner.visibility_policy import VisibilityDenied
from app.platform.access import CourseAccess, require_course_role
from app.platform.course_scope import CourseScope
from app.privacy.profiles import consent_text, privacy_profile

router = APIRouter(tags=["learner"])
CourseStudent = Annotated[CourseAccess, Depends(require_course_role("student"))]
CourseInstructor = Annotated[CourseAccess, Depends(require_course_role("instructor"))]
NOT_AVAILABLE = "This student's individual data is not available."


class CheckIn(BaseModel):
    item_id: str = Field(max_length=64)
    choice: Literal["A", "B", "C", "D"]


class OnboardingOut(BaseModel):
    module_id: int
    consent_text: str
    consent_given: bool | None  # None: never asked
    preference_questions: list[PreferenceQuestion]
    diagnostic: list[CheckItemPublic]  # empty when the module has no published check items


class OnboardingIn(BaseModel):
    module_id: int
    consent: bool | None = None  # None: leave as it is
    preferences: PreferenceAnswers = PreferenceAnswers()
    answers: list[DiagnosticAnswer] = Field(default_factory=list, max_length=20)


class ModuleProfile(BaseModel):
    module_id: int
    code: str
    title: str
    kcs: list[KcBand]
    misconceptions: list[OpenMisconception] = []


class VisibilityOut(BaseModel):
    """What the instructor can see of this student (course-structure.md 4.5)."""

    mode: Literal["A", "B"]  # A: aggregates only; B: individual overviews after the acknowledgement
    acknowledged: bool
    opted_out: bool
    visible_to_instructor: bool
    visible_since: datetime | None = None


class PlanOut(BaseModel):
    focus_kcs: list[str]
    goal: Literal["basic", "intermediate", "advanced"]
    notes: str
    updated_at: datetime


class CourseProfileOut(BaseModel):
    personalized: bool  # False without consent: nothing is stored, so there is nothing to show
    preferences: Preferences | None = None
    modules: list[ModuleProfile] = []
    visibility: VisibilityOut
    plan: PlanOut | None = None  # the instructor's plan, when the student is visible


class VisibilityIn(BaseModel):
    action: Literal["acknowledge", "opt_out", "opt_in"]


class PlanIn(BaseModel):
    focus_kcs: list[str] = Field(min_length=1, max_length=8)
    goal: Literal["basic", "intermediate", "advanced"]
    notes: str = Field("", max_length=500)


def _services(request: Request):
    return request.app.state.services


def _module_code(scope: CourseScope, module_id: int) -> str:
    code = next((c for c, mid in scope.modules.items() if mid == module_id), None)
    if code is None:
        raise ApiError(404, ErrorCode.not_found, "module not found")
    return code


def _visibility(state) -> VisibilityOut:
    visible = state.mode == "B" and not state.hidden_from_instructor and state.visible_since is not None
    return VisibilityOut(mode=state.mode, acknowledged=state.acknowledged_at is not None,
                         opted_out=state.hidden_from_instructor, visible_to_instructor=visible,
                         visible_since=state.visible_since if visible else None)


def _plan_out(plan) -> PlanOut | None:
    if plan is None:
        return None
    return PlanOut(focus_kcs=list(plan.focus_kcs), goal=plan.goal, notes=plan.notes,
                   updated_at=plan.created_at)


# ------------------------------------------------------------------------------------------- students
@router.post("/courses/{course_id}/check", response_model=CheckResponse, operation_id="learner_check")
def check(body: CheckIn, access: CourseStudent, request: Request):
    """Answer a check question of this course: graded by the key, applied as strong evidence."""
    scope = _scope(_services(request), access.course.id)
    content, learner, sid = scope.content, scope.learner, access.student_id
    item = content.item(body.item_id)
    if item is None or item not in content.items(item.kc):  # unknown, another course's, or not published
        raise ApiError(404, ErrorCode.not_found, "check question not found")
    graded = grade(item, body.choice)
    state = learner.observe(sid, evidence_for(item, graded, "strong", "check"))
    learner.check_answered(sid, item, graded)
    next_kc = learner.recommender.next_kc(sid, content.topic_of(item.kc)) if state else None
    return CheckResponse(correct=graded.correct, correct_choice=graded.correct_choice,
                         explanation=item.explanation, kc_id=item.kc,
                         kc_level=state.level if state else None,
                         kc_band=learner.band(state) if state else None, next_kc=next_kc)


@router.get("/courses/{course_id}/onboarding", response_model=OnboardingOut,
            operation_id="learner_onboarding_get")
def get_onboarding(module_id: int, access: CourseStudent, request: Request):
    scope = _scope(_services(request), access.course.id)
    code = _module_code(scope, module_id)
    return OnboardingOut(module_id=module_id,
                         consent_text=consent_text(privacy_profile(access.course.course_type)),
                         consent_given=scope.learner.repo.consent(access.student_id),
                         preference_questions=PREFERENCE_QUESTIONS,
                         diagnostic=[i.public() for i in diagnostic_items(scope.content, code)])


@router.post("/courses/{course_id}/onboarding", response_model=OnboardingResult,
             operation_id="learner_onboarding_submit")
def post_onboarding(body: OnboardingIn, access: CourseStudent, request: Request):
    """Consent and preferences are global; the diagnostic answers count in this course only."""
    scope = _scope(_services(request), access.course.id)
    code = _module_code(scope, body.module_id)
    learner, sid = scope.learner, access.student_id
    if body.consent is not None:
        learner.set_consent(sid, body.consent)
    if not learner.has_consent(sid):
        return OnboardingResult(personalized=False)  # nothing else is stored without consent
    for dimension in ("sequencing", "detail"):
        value = getattr(body.preferences, dimension)
        if value:
            learner.update_preferences(sid, PreferenceSignal(dimension=dimension, value=value, explicit=True,
                                                             source="onboarding"))
    try:
        assessed, skipped = learner.apply_diagnostic(sid, code, [(a.item_id, a.choice) for a in body.answers])
    except ValueError as exc:
        raise ApiError(422, ErrorCode.invalid, str(exc)) from None
    ctx = learner.context(sid, code)
    kcs = [KcBand(kc_id=k.id, name=k.name, band=learner.band(ctx.kc_states[k.id]))
           for k in scope.content.kcs(code)]
    return OnboardingResult(personalized=True, assessed=assessed, skipped=skipped, kcs=kcs)


@router.get("/courses/{course_id}/me/profile", response_model=CourseProfileOut,
            operation_id="learner_profile")
def my_profile(access: CourseStudent, request: Request):
    """"What I know" in this course (bands, never probabilities), what the instructor can see, and the
    instructor's plan when there is one."""
    services = _services(request)
    scope = _scope(services, access.course.id)
    content, learner, sid = scope.content, scope.learner, access.student_id
    state = course_views.visibility_state(services.engine, access.course.id, sid)
    out = CourseProfileOut(personalized=learner.has_consent(sid), visibility=_visibility(state),
                           plan=_plan_out(course_views.shown_plan(services.engine, access.course.id, sid)))
    if not out.personalized:
        return out
    out.preferences = learner.preferences.get(sid)
    for code in content.topics():
        kc_ids = [k.id for k in content.kcs(code)]
        states = learner.knowledge.state(sid, kc_ids)
        out.modules.append(ModuleProfile(
            module_id=scope.modules[code], code=code, title=content.topic(code).name,
            kcs=[KcBand(kc_id=k.id, name=k.name, band=learner.band(states[k.id])) for k in content.kcs(code)],
            misconceptions=[OpenMisconception.of(m) for m in learner.open_misconceptions(sid, kc_ids)]))
    return out


@router.post("/courses/{course_id}/me/visibility", response_model=VisibilityOut,
             operation_id="learner_visibility", responses={409: {"description": "not possible in this mode"}})
def my_visibility(body: VisibilityIn, access: CourseStudent, request: Request):
    """Acknowledge visibility mode B (from then on the instructor can see new data), opt out, or opt back in
    (a new start: earlier data stays hidden)."""
    try:
        state = course_views.change_student_visibility(
            _services(request).engine, access.course.id, access.student_id, body.action, access.account_id)
    except VisibilityDenied as exc:
        raise ApiError(409, ErrorCode.conflict, str(exc)) from None
    return _visibility(state)


@router.delete("/courses/{course_id}/me/learning-data", status_code=status.HTTP_204_NO_CONTENT,
               operation_id="learner_delete_course_data")
def delete_my_course_data(access: CourseStudent, request: Request):
    """Forget what the tutor learned about the caller in this course, with the conversations and the plan.
    Other courses, the preferences, the consent and the membership stay."""
    services = _services(request)
    scope = _scope(services, access.course.id)
    course_views.delete_own_course_data(services.engine, scope.learner, access.course.id, access.student_id)
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# ---------------------------------------------------------------------------------------- instructors
@router.get("/courses/{course_id}/class-summary", response_model=ClassSummary,
            operation_id="learner_class_summary")
def get_class_summary(module_id: int, access: CourseInstructor, request: Request):
    """Aggregates of one module over the course's consenting students; small groups are suppressed."""
    services = _services(request)
    scope = _scope(services, access.course.id)
    code = _module_code(scope, module_id)
    return class_summary(services.engine, scope.learner, scope.content, code,
                         services.settings.learner.class_summary_min_group,
                         members=course_views.course_student_ids(services.engine, access.course.id))


@router.get("/courses/{course_id}/students/{student_id}/overview", response_model=InstructorProfileView,
            operation_id="learner_student_overview")
def student_overview(student_id: str, access: CourseInstructor, request: Request):
    """One student's overview: only in mode B, after the student's acknowledgement, without an opt-out, and
    only data from after the acknowledgement. Each view is written to the audit log."""
    services = _services(request)
    scope = _scope(services, access.course.id)
    store = course_views.DbLearnerViewStore(services.engine, services.settings, scope.content)
    try:
        return profile_for_instructor(access, student_id, store=store)
    except NotVisible:
        raise ApiError(404, ErrorCode.not_found, NOT_AVAILABLE) from None


@router.get("/courses/{course_id}/students/{student_id}/plan", response_model=PlanOut,
            operation_id="learner_plan_get")
def get_plan(student_id: str, access: CourseInstructor, request: Request):
    plan = course_views.shown_plan(_services(request).engine, access.course.id, student_id,
                                   viewer_account_id=access.account_id)  # audited
    if plan is None:
        raise ApiError(404, ErrorCode.not_found, "no learning plan is available for this student")
    return _plan_out(plan)


@router.put("/courses/{course_id}/students/{student_id}/plan", response_model=PlanOut,
            operation_id="learner_plan_update")
def put_plan(student_id: str, body: PlanIn, access: CourseInstructor, request: Request):
    """Set the learning plan of a visible student: KCs of this course to focus on, a goal level, a note."""
    services = _services(request)
    scope = _scope(services, access.course.id)
    known = {k.id for code in scope.content.topics() for k in scope.content.kcs(code)}
    if not set(body.focus_kcs) <= known or len(set(body.focus_kcs)) != len(body.focus_kcs):
        raise ApiError(422, ErrorCode.invalid, "focus_kcs must be distinct KC codes of this course")
    try:
        plan = course_views.save_plan(services.engine, access.course.id, student_id,
                                      focus_kcs=body.focus_kcs, goal=body.goal, notes=body.notes,
                                      known_kcs=known, account_id=access.account_id)
    except (LookupError, VisibilityDenied):
        raise ApiError(404, ErrorCode.not_found, NOT_AVAILABLE) from None
    return _plan_out(plan)
