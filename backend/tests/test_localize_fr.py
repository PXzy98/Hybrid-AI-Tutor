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
    de = alice.get(url, params={"module_id": world.module, "language": "de"}).json()
    assert de["consent_text"] == en["consent_text"]  # other languages: English


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


def test_french_catalog_is_complete_for_profiles_and_preferences():
    from app.api.v1.onboarding import PREFERENCE_QUESTIONS
    from app.privacy.profiles import _raw, profile_names
    with_note = {n for n in profile_names() if _raw(n).get("consent_note")}
    assert set(localize._french()["consent_notes"]) == with_note
    fr = localize._french()["preferences"]
    for q in PREFERENCE_QUESTIONS:
        assert fr[q.id]["question"]
        assert all(fr[q.id][c.value] for c in q.options)


def test_a_missing_french_text_falls_back_to_english_never_drops_the_note(monkeypatch):
    from app.api.v1.onboarding import PREFERENCE_QUESTIONS
    from app.privacy.profiles import STATISTICS_ONLY_NOTE, consent_text, privacy_profile
    profile = privacy_profile("medical_science")
    english = consent_text(profile, statistics_only=True)
    french = dict(localize._french())
    french["consent_notes"], french["preferences"] = {}, {}
    monkeypatch.setattr(localize, "_french", lambda: french)
    out = localize.consent_text(profile.name, english, "fr", statistics_only=True)
    note = english.removeprefix(localize.CONSENT_BASE).removesuffix(STATISTICS_ONLY_NOTE).strip()
    assert note and note in out and out.startswith("Pour adapter")
    assert localize.preference_questions("fr") == PREFERENCE_QUESTIONS


def test_appended_referral_and_misconception_header_are_translated():
    from app.learner.misconceptions import NOTE_HEADER
    from app.pipeline.steps.verify import REFERRAL
    notes = localize._notes()
    a = "Model words.\n\n" + NOTE_HEADER + " Fix it.\n\n" + REFERRAL
    assert localize.answer(a, "fr") == ("Model words.\n\n" + notes[NOTE_HEADER] + " Fix it.\n\n"
                                        + notes[REFERRAL])
    assert localize.answer(a, "en") == a
    assert localize.answer("Plain " + REFERRAL, "fr") == "Plain " + REFERRAL  # not appended by the pipeline


def test_stored_safe_answer_is_french_when_the_conversation_is_read_in_french(world):
    from app.core.schemas import Turn
    from app.pipeline.steps.verify import SAFE_FALLBACK
    alice = _login(world.app, "alice")
    cid = alice.post(f"{world.url}/ask", json={"question": "What is Ohm's law?",
                                               "module_id": world.module}).json()["conversation_id"]
    from app.api.v2.ask import _scope
    sessions = _scope(world.services, world.course).sessions
    sessions.append(cid, world.students["alice"].student_id, Turn(role="tutor", text=SAFE_FALLBACK))
    url = f"{world.url}/conversations/{cid}"
    en = alice.get(url).json()["turns"][-1]["text"]
    fr = alice.get(url, params={"language": "fr"}).json()["turns"][-1]["text"]
    assert en == SAFE_FALLBACK and fr == localize._notes()[SAFE_FALLBACK]


def test_any_french_variant_is_french_in_onboarding(world):
    alice = _login(world.app, "alice")
    r = alice.get(f"{world.url}/onboarding", params={"module_id": world.module, "language": "fr-CA"})
    assert r.status_code == 200 and r.json()["consent_text"].startswith("Pour adapter")


def test_model_unavailable_is_the_v1_text():
    from app.api.v1 import ask
    assert localize.ENGLISH["MODEL_UNAVAILABLE"] is ask.MODEL_UNAVAILABLE


def test_the_routing_panel_knows_the_privacy_notice_in_both_languages():
    # v6 X3: the student's routing panel adds a step when the answer carries this notice; it matches the text,
    # so a reworded notice must be reworded in RoutingProgress.tsx too
    from pathlib import Path

    from app.pipeline.steps.generate import PRIVACY_BLOCK_WARNING

    frontend = Path(__file__).resolve().parents[2] / "frontend"
    panel = (frontend / "src/components/RoutingProgress.tsx").read_text("utf-8")
    for text in (PRIVACY_BLOCK_WARNING, localize._notes()[PRIVACY_BLOCK_WARNING]):
        assert f'"{text}"' in panel
