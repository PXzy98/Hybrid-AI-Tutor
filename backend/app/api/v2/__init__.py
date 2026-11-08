"""HTTP API v2 (docs/design/api-v2.md). All v4 endpoints go here; /api/v1 is frozen.

Add a module per endpoint group (auth, admin, courses, members, content, materials, ask, learner,
instructor_ai, ...) and include its router below. Course-scoped routes live under
`/courses/{course_id}/...` and start with `Depends(require_course_role(...))`.
"""
from fastapi import APIRouter

from app.api.v2 import auth, courses, model_endpoints

api_router_v2 = APIRouter(prefix="/api/v2")
api_router_v2.include_router(auth.router)
api_router_v2.include_router(courses.router)
api_router_v2.include_router(model_endpoints.router)
