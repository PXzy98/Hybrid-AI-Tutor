"""Task X10: the biomedical engineering course type: the health rules of medical_science and the engineering
rules of ece in one profile, its subject prompt and its web search sites. Every text is fictional."""
from pathlib import Path

import pytest
import yaml

from app.core.config import get_settings
from app.privacy import profiles
from app.privacy.profiles import consent_text, privacy_profile, scan_document
from app.prompts.render import subject_partial
from app.routing.models import load_weights, model_dir, weights_path
from tests.test_privacy_z11 import _found

NAME = "biomedical_engineering"


def test_the_profile_joins_the_medical_and_the_engineering_rules():
    bme = privacy_profile(NAME)
    medical, ece = privacy_profile("medical_science"), privacy_profile("ece")
    assert set(medical.recognizers) | set(ece.recognizers) == set(bme.recognizers)
    assert (bme.health_detail_policy, bme.checkers, bme.medical_disclaimer, bme.prompt) == (
        "generalize", ("medical_safety",), True, NAME)
    assert NAME in profiles.profile_names()


def test_the_subject_prompt_keeps_the_health_safety_rules():
    prompt = subject_partial(NAME)
    assert "biomedical engineering" in prompt
    assert "Health safety rules" in prompt and "never give a personal treatment plan" in prompt


def test_consent_note_and_web_search_sites():
    assert "does not give medical advice" in consent_text(privacy_profile(NAME))
    config = yaml.safe_load((Path(__file__).resolve().parents[2] / "config.yaml").read_text(encoding="utf-8"))
    assert "fda.gov" in config["websearch"]["allowlist"][NAME]
    assert config["websearch"]["searxng_engines"][NAME]


@pytest.mark.parametrize(("text", "kind", "value"), [
    ("the Arduino of my ECG front end at 192.168.1.42:8080 stops", "INTERNAL_ADDRESS", "192.168.1.42:8080"),
    ("my filter code is at github.com/jtremblay42/bmg-lab2", "REPO_URL", "github.com/jtremblay42/bmg-lab2"),
    ("Ann Lee, student 300418277, asks about the pulse oximeter lab", "STUDENT_ID", "300418277"),
])
def test_lab_details_and_identifiers_are_found(text, kind, value):
    assert value in _found(NAME, text).get(kind, [])


def test_a_personal_health_detail_is_found():
    text = "I have epilepsy and my EEG lab partner wants to record me. Is that ok?"
    assert "HEALTH_DETAIL" in _found(NAME, text)


@pytest.mark.parametrize("text", [
    "How does a 60 Hz notch filter remove mains noise from an ECG signal sampled at 500 Hz?",
    "A 12-bit ADC with a 3.3 V reference: what is the voltage of one step?",
    "What are the sensitivity and specificity of a test with 90 true positives and 10 false negatives?",
])
def test_course_questions_keep_their_values(text):
    assert not _found(NAME, text)


def test_course_material_with_a_fictional_patient_is_not_refused():
    text = ("Case: a 54 year old patient presents with chest pain; the ECG shows ST elevation in leads II, "
            "III and aVF. Design the amplifier stage: gain 1000, CMRR above 100 dB.")
    assert scan_document(text, privacy_profile(NAME)).blocking == ()


def test_the_type_routes_with_its_own_heads():
    cfg = get_settings().routing
    for method in cfg.enabled_methods:
        path = weights_path(cfg, method, NAME)
        assert path == model_dir(cfg) / NAME / f"semantic_{method}.npz"
        metadata, _ = load_weights(cfg, method, NAME)
        assert metadata["course_type"] == NAME
    assert weights_path(cfg, "lr", "ece") == model_dir(cfg) / "semantic_lr.npz"  # other types unchanged
