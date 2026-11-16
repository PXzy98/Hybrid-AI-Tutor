"""S8: the course-level layered knowledge model in the app (`learner.knowledge: course`, guide 4.10).

The fictional demo course has prerequisites HBP.1 -> HBP.2 -> HBP.4 and HBP.1 -> HBP.3 -> HBP.5.
"""
from pathlib import Path

import pytest
import yaml

from app.core.registry import import_submodules, knowledge_models
from app.core.schemas import Evidence
from app.core.services import build_services
from app.platform.settings import _known_knowledge_models

S = "student-1"


def strong(kc, correct, item=None):
    return Evidence(kc_id=kc, kind="strong", correct=correct, item_id=item, source="check")


@pytest.fixture
def make(use_config):
    """A learner model; every instance shares the test database, so each test uses its own student IDs."""
    def _make(knowledge="course", students=(S,), **learner):
        services = build_services(use_config({"learner": {"knowledge": knowledge, **learner}}))
        for student in students:
            services.learner.set_consent(student, True)
        return services.learner
    return _make


def test_it_is_registered_selectable_and_the_configured_default():
    import_submodules("app.learner.knowledge")
    assert "course" in knowledge_models.names() and "course" in _known_knowledge_models()
    config = yaml.safe_load((Path(__file__).resolve().parents[2] / "config.yaml").read_text(encoding="utf-8"))
    assert config["learner"]["knowledge"] == "course"


def test_with_nothing_observed_it_equals_bkt(make):
    course, bkt = make("course"), make("bkt")
    kcs = ["HBP.1", "HBP.2", "HBP.4", "HBP.6"]
    assert course.knowledge.state(S, kcs) == bkt.knowledge.state(S, kcs)


def test_ability_moves_the_start_of_kcs_not_practised_yet(make):
    lm = make(students=("good", "weak"))
    for _ in range(4):
        lm.observe("good", strong("HBP.1", True, "HBP.1-q4"))  # advanced items answered right
    prior = 0.2
    assert lm.knowledge.ability("good") > 0
    assert lm.knowledge.state("good", ["HBP.3"])["HBP.3"].p_mastery > prior
    lm.observe("weak", strong("HBP.1", False, "HBP.1-q1"))  # a basic item answered wrong
    assert lm.knowledge.ability("weak") < 0
    assert lm.knowledge.state("weak", ["HBP.3"])["HBP.3"].p_mastery < prior
    # no ability effect at all: plain BKT
    flat = make(students=("flat",), course_model={"ability_gain": 0.3, "ability_weight": 0.0})
    for _ in range(4):
        flat.observe("flat", strong("HBP.1", True, "HBP.1-q4"))
    assert flat.knowledge.state("flat", ["HBP.3"])["HBP.3"].p_mastery == prior


def test_a_weak_prerequisite_caps_what_is_shown_but_not_what_is_stored(make):
    course, bkt = make("course", students=("c",)), make("bkt", students=("b",))
    for lm, student in ((course, "c"), (bkt, "b")):
        for _ in range(4):
            lm.observe(student, strong("HBP.2", True))
        for _ in range(3):
            lm.observe(student, strong("HBP.1", False))
    raw = course.knowledge.repo.states("c", ["HBP.2"])["HBP.2"]
    plain = bkt.knowledge.repo.states("b", ["HBP.2"])["HBP.2"]
    assert (raw.p_mastery, raw.n_obs) == (plain.p_mastery, plain.n_obs)  # the stored estimate is plain BKT
    hbp1 = course.knowledge.state("c", ["HBP.1"])["HBP.1"].p_mastery
    shown = course.knowledge.state("c", ["HBP.2"])["HBP.2"]
    assert shown.p_mastery == pytest.approx(0.25 + 0.75 * hbp1, abs=1e-6)
    assert shown.p_mastery < raw.p_mastery and shown.n_obs == raw.n_obs == 4
    # the cap reaches further down the chain, and lifts once the prerequisite is learned
    assert course.knowledge.state("c", ["HBP.4"])["HBP.4"].p_mastery <= shown.p_mastery
    for _ in range(5):
        course.observe("c", strong("HBP.1", True))
    assert course.knowledge.state("c", ["HBP.2"])["HBP.2"].p_mastery == raw.p_mastery


def test_an_update_starts_from_the_stored_estimate(make):
    course = make()
    for _ in range(3):
        course.observe(S, strong("HBP.1", False))  # caps HBP.2
    before = course.knowledge.repo.states(S, ["HBP.2"])
    shown = course.observe(S, strong("HBP.2", True))  # returns the shown (capped) state
    stored = course.knowledge.repo.states(S, ["HBP.2"])["HBP.2"]
    assert not before and stored.p_mastery > shown.p_mastery  # updated from the raw prior, cap applied on top
    assert shown == course.knowledge.state(S, ["HBP.2"])["HBP.2"]
