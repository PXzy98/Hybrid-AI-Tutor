from app.core.schemas import PIIEntity
from app.privacy.redact import redact_known


def ent(text, ph):
    return PIIEntity(type="PERSON", text=text, start=0, end=len(text), score=1.0, placeholder=ph)


def test_longest_value_first():
    entities = [ent("Alice", "<PERSON_2>"), ent("Alice Tremblay", "<PERSON_1>")]
    out = redact_known("Hi Alice Tremblay, Alice!", entities)
    assert out == "Hi <PERSON_1>, <PERSON_2>!"


def test_no_entities_is_identity():
    assert redact_known("plain text", []) == "plain text"


def test_any_case_whole_words():
    """The answer to "I have asthma" starts with "Asthma is…"; "Tom" must not touch "symptoms"."""
    entities = [ent("asthma", "<HEALTH_DETAIL_1>"), ent("Tom", "<PERSON_1>")]
    out = redact_known("Asthma is common. TOM, your symptoms of asthma…", entities)
    assert out == "<HEALTH_DETAIL_1> is common. <PERSON_1>, your symptoms of <HEALTH_DETAIL_1>…"
