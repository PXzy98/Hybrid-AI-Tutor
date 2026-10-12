from fastapi import APIRouter
from pydantic import BaseModel

from app.api.deps import ServicesDep

router = APIRouter()

# Display names until content/topics/<topic>/kcs.yaml provides them (Step 5).
TOPIC_NAMES = {
    "high_blood_pressure": "High Blood Pressure",
    "type2_diabetes": "Type 2 Diabetes",
    "asthma": "Asthma",
    "migraine": "Migraine",
    "pneumonia": "Pneumonia",
}


class TopicInfo(BaseModel):
    id: str
    name: str
    kc_count: int = 0  # filled from content in Step 5
    reviewed_item_count: int = 0


@router.get("/topics", response_model=list[TopicInfo])
def list_topics(services: ServicesDep, course_id: str = "default"):
    return [TopicInfo(id=t, name=TOPIC_NAMES.get(t, t.replace("_", " ").title()))
            for t in services.settings.topics(course_id)]
