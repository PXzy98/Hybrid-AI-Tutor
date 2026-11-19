"""French versions of the fixed texts the backend shows students (v5: the French UI showed English).

The pipeline and the privacy profiles write their notes in English; API v2 translates them at the response
boundary when the request's language is French. Only these fixed texts are translated, never model output
or anything a person wrote. API v1 stays English (frozen). The French texts are in `fr.yaml`.
"""
import re
from functools import cache
from pathlib import Path

import yaml

from app.api.v1.ask import DEFAULT_FAILURE, FAILURE_MESSAGES
from app.api.v1.onboarding import PREFERENCE_QUESTIONS, Choice, PreferenceQuestion
from app.pipeline.steps import generate, route, verify
from app.privacy.profiles import CONSENT_BASE, STATISTICS_ONLY_NOTE

MODEL_UNAVAILABLE = ("The selected model is unavailable. Check the local server or Cloud configuration and "
                     "retry.")  # app/api/v1/ask.py `_error`, generate step

# the English constants, by the names fr.yaml uses
ENGLISH = {
    "CLOUD_FALLBACK_WARNING": generate.CLOUD_FALLBACK_WARNING,
    "CLOUD_MISSING_WARNING": generate.CLOUD_MISSING_WARNING,
    "PRIVACY_BLOCK_WARNING": generate.PRIVACY_BLOCK_WARNING,
    "LOCAL_ONLY_WARNING": generate.LOCAL_ONLY_WARNING,
    "CLOUD_LIMIT_NOTE": generate.CLOUD_LIMIT_NOTE,
    "GENERALIZED_NOTE": generate.GENERALIZED_NOTE,
    "LOCAL_CAPABILITY_NOTE": generate.LOCAL_CAPABILITY_NOTE,
    "UNVERIFIED_SOURCES_NOTE": route.UNVERIFIED_SOURCES_NOTE,
    "REPLACED_WARNING": verify.REPLACED_WARNING,
    "GROUNDING_WARNING": verify.WARNINGS["grounding"],
    "LEAK_WARNING": verify.WARNINGS["pii_leak"],  # profile_leak has the same text
    "SAFE_FALLBACK": verify.SAFE_FALLBACK,
    "SAFE_FALLBACK_SOURCES": verify.SAFE_FALLBACK_SOURCES,
    "DEFAULT_FAILURE": DEFAULT_FAILURE,
    "PRIVACY_FILTER_FAILURE": FAILURE_MESSAGES["privacy_filter"],
    "MODEL_UNAVAILABLE": MODEL_UNAVAILABLE,
    "STATISTICS_ONLY_NOTE": STATISTICS_ONLY_NOTE,
}

# the v2 consent text in English: the reviewed v1 text names the old "What I know" page, now "My progress"
CONSENT_EN = CONSENT_BASE.replace("under 'What I know'", "on 'My progress'")
_STEP_FAILED = re.compile(r"^([a-z_]+): could not be completed$")


@cache
def _french() -> dict:
    return yaml.safe_load((Path(__file__).with_name("fr.yaml")).read_text(encoding="utf-8"))


@cache
def _notes() -> dict[str, str]:
    notes = _french()["notes"]
    return {ENGLISH[name]: french for name, french in notes.items()}


def is_french(language: str | None) -> bool:
    return (language or "").lower().startswith("fr")


def text(value: str, language: str | None) -> str:
    """The French version of a fixed backend text, or the text itself (other languages, unknown text)."""
    if not is_french(language):
        return value
    notes = _notes()
    if value in notes:
        return notes[value]
    both = verify.SAFE_FALLBACK + verify.SAFE_FALLBACK_SOURCES
    if value == both:
        return notes[verify.SAFE_FALLBACK] + notes[verify.SAFE_FALLBACK_SOURCES]
    step = _STEP_FAILED.match(value)
    if step:
        return _french()["step_failed"].format(step=step.group(1))
    return value


def consent_text(profile_name: str, english: str, language: str | None, *, statistics_only: bool) -> str:
    """The v2 onboarding consent text in the student's language; `english` is the profile's text from
    `app.privacy.profiles.consent_text`, used for every other language."""
    if not is_french(language):
        return english.replace(CONSENT_BASE, CONSENT_EN, 1)
    fr = _french()
    parts = [fr["consent"]]
    if profile_name in fr["consent_notes"]:
        parts.append(fr["consent_notes"][profile_name])
    if statistics_only:
        parts.append(_notes()[STATISTICS_ONLY_NOTE])
    return " ".join(parts)


def preference_questions(language: str | None) -> list[PreferenceQuestion]:
    if not is_french(language):
        return PREFERENCE_QUESTIONS
    fr = _french()["preferences"]
    return [PreferenceQuestion(id=q.id, question=fr[q.id]["question"],
                               options=[Choice(value=c.value, label=fr[q.id][c.value]) for c in q.options])
            for q in PREFERENCE_QUESTIONS]
