from fastapi import APIRouter

from app.api.v1 import ask, health, sessions, topics

api_router = APIRouter(prefix="/api/v1")
for module in (ask, sessions, topics, health):
    api_router.include_router(module.router)
