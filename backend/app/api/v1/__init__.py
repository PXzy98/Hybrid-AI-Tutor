from fastapi import APIRouter

from app.api.v1 import admin_students, ask, auth, health, sessions, topics

api_router = APIRouter(prefix="/api/v1")
for module in (auth, ask, sessions, topics, admin_students, health):
    api_router.include_router(module.router)
