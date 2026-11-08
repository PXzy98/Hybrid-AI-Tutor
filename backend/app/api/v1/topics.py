from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ServicesDep
from app.auth.deps import AnyUser
from app.core.topics import topic_name

router = APIRouter()



class TopicInfo(BaseModel):
    id: str
    name: str
    kc_count: int = 0
    reviewed_item_count: int = 0  # API v1 name: the active (published) check questions


@router.get("/topics", response_model=list[TopicInfo])
def list_topics(_: AnyUser, services: ServicesDep, course_id: str = "default"):
    content = services.content
    out = []
    for t in services.settings.topics(course_id):
        tc = content.topic(t)
        out.append(TopicInfo(id=t, name=tc.name if tc else topic_name(t), kc_count=len(content.kcs(t)),
                             reviewed_item_count=content.active_item_count(t)))
    return out
