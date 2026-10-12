import itertools
import re

import pytest

from app.core.schemas import (
    AskRequest,
    CloudLabels,
    CloudRequest,
    LearnerContext,
    Preferences,
    RequestContext,
)
from app.prompts import base_system, render_cloud, render_local, system_prompt
from app.prompts.render import PROMPT_DIR, level_partial, style_partial

LEVELS = ["basic", "intermediate", "advanced"]
STYLES = list(itertools.product(["example_first", "concept_first"], ["concise", "detailed"]))


@pytest.mark.parametrize(("level", "style"), list(itertools.product(LEVELS, STYLES)))
def test_every_combination_keeps_the_safety_block(level, style):
    prompt = system_prompt(level, *style)
    assert prompt.startswith(base_system())  # the base safety rules come first, unchanged
    assert level_partial(level) in prompt and style_partial(*style) in prompt
    assert prompt.count("Safety rules.") == 1


def test_partials_do_not_touch_safety_or_content():
    """Partials change depth and form only (design §2 principles 3 and 8)."""
    banned = re.compile(r"diagnos|dose|medicat|prescri|safety|rule|ignore|override|instead of the", re.I)
    files = sorted((PROMPT_DIR / "levels").glob("*.md")) + sorted((PROMPT_DIR / "style").glob("*.md"))
    assert len(files) == 7
    for f in files:
        assert not banned.search(f.read_text(encoding="utf-8")), f.name


def make_ctx(learner) -> RequestContext:
    return RequestContext(request_id="r", learner=learner,
                          request=AskRequest(student_id="s", topic="asthma", question="What is asthma?"))


def test_local_prompt_uses_level_and_preferences():
    ctx = make_ctx(LearnerContext(focus_level="advanced",
                                  preferences=Preferences(sequencing="concept_first", detail="detailed")))
    system = render_local(ctx)[0]["content"]
    assert level_partial("advanced") in system and style_partial("concept_first", "detailed") in system


def test_unpersonalized_local_prompt_is_the_base_only():
    assert render_local(make_ctx(LearnerContext(personalized=False)))[0]["content"] == base_system()
    assert render_local(make_ctx(None))[0]["content"] == base_system()


def test_cloud_prompt_uses_labels_only():
    req = CloudRequest(sanitized_question="q", topic="asthma",
                       labels=CloudLabels(level="basic", sequencing="example_first", detail="detailed"))
    system = render_cloud(req)[0]["content"]
    assert level_partial("basic") in system and style_partial("example_first", "detailed") in system
