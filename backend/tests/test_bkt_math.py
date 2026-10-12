import pytest

from app.learner.knowledge.bkt_math import learn, level_with_hysteresis, posterior, weak_update


def test_posterior_correct_by_hand():
    # 0.2*0.9 / (0.2*0.9 + 0.8*0.25) = 0.18 / 0.38
    assert posterior(0.2, True, slip=0.1, guess=0.25) == pytest.approx(0.18 / 0.38)


def test_posterior_incorrect_by_hand():
    # 0.2*0.1 / (0.2*0.1 + 0.8*0.75) = 0.02 / 0.62
    assert posterior(0.2, False, slip=0.1, guess=0.25) == pytest.approx(0.02 / 0.62)


def test_learn_by_hand():
    assert learn(0.5, 0.1) == pytest.approx(0.55)


def test_weak_update_is_a_milder_observation():
    assert weak_update(0.5, 0.3, 0.6) == pytest.approx(1 / 3)
    strong_wrong = posterior(0.5, False, 0.1, 0.25)
    assert strong_wrong < weak_update(0.5, 0.3, 0.6) < 0.5  # likelihood ratio 7.5 vs 2


def test_probabilities_never_reach_zero_or_one():
    p = 0.5
    for _ in range(200):
        p = learn(posterior(p, True, 0.1, 0.25), 0.1)
    assert 0 < p < 1
    for _ in range(200):
        p = posterior(p, False, 0.1, 0.25)
    assert 0 < p < 1 and posterior(p, True, 0.1, 0.25) > p  # still able to move


BANDS = {"basic_below": 0.40, "advanced_above": 0.70, "h": 0.05}


@pytest.mark.parametrize(("p", "level"), [(0.2, "basic"), (0.39, "basic"), (0.40, "intermediate"),
                                          (0.70, "intermediate"), (0.71, "advanced")])
def test_first_level_uses_plain_bands(p, level):
    assert level_with_hysteresis(p, None, **BANDS) == level


def test_hysteresis_prevents_flip_flop_around_040():
    level = level_with_hysteresis(0.42, None, **BANDS)
    assert level == "intermediate"
    for p in (0.37, 0.43, 0.38, 0.42, 0.37):  # wobbling within 0.40 ± 0.03
        level = level_with_hysteresis(p, level, **BANDS)
        assert level == "intermediate"
    assert level_with_hysteresis(0.34, level, **BANDS) == "basic"  # clearly below 0.40 - 0.05
    for p in (0.43, 0.38, 0.44):
        assert level_with_hysteresis(p, "basic", **BANDS) == "basic"
    assert level_with_hysteresis(0.46, "basic", **BANDS) == "intermediate"


def test_hysteresis_at_070_and_big_jumps():
    assert level_with_hysteresis(0.73, "intermediate", **BANDS) == "intermediate"
    assert level_with_hysteresis(0.76, "intermediate", **BANDS) == "advanced"
    assert level_with_hysteresis(0.67, "advanced", **BANDS) == "advanced"
    assert level_with_hysteresis(0.64, "advanced", **BANDS) == "intermediate"
    assert level_with_hysteresis(0.9, "basic", **BANDS) == "advanced"
    assert level_with_hysteresis(0.1, "advanced", **BANDS) == "basic"
