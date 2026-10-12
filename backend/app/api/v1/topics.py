from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ServicesDep
from app.auth.deps import AnyUser
from app.core.topics import topic_name

router = APIRouter()



class TopicInfo(BaseModel):
    id: str
    name: str
    kc_count: int = 0  # filled from content in Step 5
    reviewed_item_count: int = 0


@router.get("/topics", response_model=list[TopicInfo])
def list_topics(_: AnyUser, services: ServicesDep, course_id: str = "default"):
    return [TopicInfo(id=t, name=topic_name(t))
            for t in services.settings.topics(course_id)]
