# Display names until content/topics/<topic>/kcs.yaml provides them (Step 5).
TOPIC_NAMES = {
    "high_blood_pressure": "High Blood Pressure",
    "type2_diabetes": "Type 2 Diabetes",
    "asthma": "Asthma",
    "migraine": "Migraine",
    "pneumonia": "Pneumonia",
}


def topic_name(topic_id: str) -> str:
    return TOPIC_NAMES.get(topic_id, topic_id.replace("_", " ").title())
