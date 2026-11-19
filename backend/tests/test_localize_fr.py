"""v5: the fixed texts the backend shows students come in French when the UI is French (onboarding consent
and preference questions, chat notes and errors). Model output is never translated. Fictional data."""
import pytest

from app.api.v2 import localize
from app.pipeline.steps.generate import CLOUD_LIMIT_NOTE
from app.privacy.profiles import CONSENT_BASE
from tests.test_ask_v2 import World, _login


@pytest.fixture
def world(make_client):
    # the deployment defaults: statistics only (V1), and no cloud answers left today (a fixed note)
    config = {"learner": {"instructor_individual_view": False},
              "limits": {"usage": {"cloud_calls_per_day": 0}}}
    with make_client(config) as client:
        w = World(client)
        w.consent("alice")
        yield w


def test_every_english_note_has_a_french_text_and_back():
    assert set(localize._french()["notes"]) == set(localize.ENGLISH)
    for english, french in localize._notes().items():
        assert french and french != english


def test_onboarding_comes_in_the_ui_language(world):
    alice = _login(world.app, "alice")
    url = f"{world.url}/onboarding"
    en = alice.get(url, params={"module_id": world.module}).json()
    assert "on 'My progress'" in en["consent_text"] and "What I know" not in en["consent_text"]
    assert en["preference_questions"][0]["options"][0]["label"] == "A concrete example first"
    fr = alice.get(url, params={"module_id": world.module, "language": "fr"}).json()
    assert fr["consent_text"].startswith("Pour adapter les explications")
    assert "Ma progression" in fr["consent_text"] and "clés d’API" in fr["consent_text"]  # the ece note
    assert "Personne, pas même l’enseignant" in fr["consent_text"]  # statistics only (V1)
    assert [o["label"] for o in fr["preference_questions"][1]["options"]] == [
        "Courtes et directes", "Détaillées, étape par étape"]
    assert [o["value"] for o in fr["preference_questions"][1]["options"]] == ["concise", "detailed"]
    assert alice.get(url, params={"module_id": world.module, "language": "de"}).status_code == 422


def test_chat_notes_come_in_french_and_the_answer_is_not_translated(world):
    alice = _login(world.app, "alice")
    body = {"question": "What is Ohm's law?", "module_id": world.module}
    en = alice.post(f"{world.url}/ask", json=body).json()
    assert CLOUD_LIMIT_NOTE in en["warnings"]
    fr = alice.post(f"{world.url}/ask", json={**body, "language": "fr"}).json()
    assert localize._notes()[CLOUD_LIMIT_NOTE] in fr["warnings"] and CLOUD_LIMIT_NOTE not in fr["warnings"]
    assert fr["answer"] == "Fake local answer."  # the model's answer stays as written


def test_unknown_texts_and_other_languages_stay_as_they_are():
    assert localize.text("Something a model wrote.", "fr") == "Something a model wrote."
    assert localize.text(CLOUD_LIMIT_NOTE, "en") == CLOUD_LIMIT_NOTE
    assert localize.text("verify: could not be completed", "fr") == "verify : n’a pas pu être terminé"
    assert localize.consent_text("general", CONSENT_BASE, "en", statistics_only=False) == localize.CONSENT_EN
