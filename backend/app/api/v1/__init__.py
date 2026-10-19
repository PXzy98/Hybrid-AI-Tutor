from fastapi import APIRouter

from app.api.v1 import (
    admin,
    admin_students,
    ask,
    auth,
    check,
    health,
    learner_me,
    onboarding,
    sessions,
    survey,
    topics,
)

api_router = APIRouter(prefix="/api/v1")
for module in (auth, ask, check, onboarding, learner_me, sessions, topics, admin_students, admin, health):
    api_router.include_router(module.router)
api_router.include_router(survey.router)
