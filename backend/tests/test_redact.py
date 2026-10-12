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
