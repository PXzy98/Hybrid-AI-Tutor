"""Bayesian Knowledge Tracing arithmetic (design §5.1). Pure functions: no I/O, no state."""
from app.core.schemas import Level

EPS = 1e-4  # keep P(L) away from 0 and 1, so later evidence can still move it


def _clamp(p: float) -> float:
    return min(1 - EPS, max(EPS, p))


def posterior(p: float, correct: bool, slip: float, guess: float) -> float:
    """P(L | observation) after one graded answer.

    correct:   P(L)(1-s) / [P(L)(1-s) + (1-P(L)) g]
    incorrect: P(L) s     / [P(L) s     + (1-P(L)) (1-g)]
    """
    if correct:
        known, unknown = p * (1 - slip), (1 - p) * guess
    else:
        known, unknown = p * slip, (1 - p) * (1 - guess)
    total = known + unknown
    return _clamp(known / total) if total > 0 else _clamp(p)


def learn(p: float, transit: float) -> float:
    """Chance of learning the KC on this practice opportunity: P(L) + (1 - P(L)) T."""
    return _clamp(p + (1 - p) * transit)


def weak_update(p: float, p_signal_given_l: float, p_signal_given_not_l: float) -> float:
    """A noisy observation (e.g. a confusion signal): Bayes with its own likelihoods, no learning step.

    With the defaults 0.30 / 0.60 the likelihood ratio is 2, against about 7.5 for a wrong MCQ answer.
    """
    known, unknown = p * p_signal_given_l, (1 - p) * p_signal_given_not_l
    total = known + unknown
    return _clamp(known / total) if total > 0 else _clamp(p)


def level_with_hysteresis(p: float, previous: Level | None, basic_below: float, advanced_above: float,
                          h: float) -> Level:
    """Level band for P(L). Moving to another band needs a margin of h past the boundary, so the level does
    not flip between turns when P(L) hovers near 0.40 or 0.70."""
    if previous == "basic":
        lo, hi = basic_below + h, advanced_above + h
    elif previous == "advanced":
        lo, hi = basic_below - h, advanced_above - h
    elif previous == "intermediate":
        lo, hi = basic_below - h, advanced_above + h
    else:  # first time: plain bands
        lo, hi = basic_below, advanced_above
    if p < lo:
        return "basic"
    if p > hi:
        return "advanced"
    return "intermediate"
