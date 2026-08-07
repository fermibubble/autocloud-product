"""Stopping-rule tests: the pass branch must be unreachable without
budget, coverage, and fidelity — no truncated run can ever look clean."""

import random

from rollout_fastforward.stopping import decide


def test_confirmed_harm_fails_even_at_budget_zero():
    assert decide(5.0, 9.0, 1.0, 0.5, True, True, 0) == "fail"
    assert decide(5.0, 9.0, 1.0, 0.5, False, False, -3) == "fail"


def test_budget_exhaustion_is_inconclusive_not_pass():
    # hi < safe and everything ok — but no budget left.
    assert decide(-1.0, 0.1, 1.0, 0.5, True, True, 0) == "inconclusive_budget"
    assert decide(-1.0, 0.1, 1.0, 0.5, True, True, -1) == "inconclusive_budget"


def test_pass_branch():
    assert decide(-1.0, 0.1, 1.0, 0.5, True, True, 10) == "pass"


def test_continue_branch():
    # CI straddles: neither confirmed harm nor confirmed safe.
    assert decide(0.2, 2.0, 1.0, 0.5, True, True, 10) == "continue"


def test_pass_requires_coverage_and_fidelity():
    assert decide(-1.0, 0.1, 1.0, 0.5, False, True, 10) == "continue"
    assert decide(-1.0, 0.1, 1.0, 0.5, True, False, 10) == "continue"
    assert decide(-1.0, 0.1, 1.0, 0.5, False, False, 10) == "continue"


def test_no_truncated_budget_stream_ever_passes():
    # Property: with budget_left <= 0 the only possible verdicts are
    # "fail" (confirmed harm) and "inconclusive_budget". Never "pass".
    rng = random.Random(1234)
    for _ in range(500):
        lo = rng.uniform(-10, 10)
        hi = lo + rng.uniform(0, 10)
        out = decide(lo, hi, rng.uniform(-10, 10), rng.uniform(-10, 10),
                     rng.random() < 0.5, rng.random() < 0.5,
                     -rng.uniform(0, 5) if rng.random() < 0.5 else 0)
        assert out in ("fail", "inconclusive_budget")


def test_no_uncovered_or_low_fidelity_run_ever_passes():
    rng = random.Random(99)
    for _ in range(500):
        lo = rng.uniform(-10, 10)
        hi = lo + rng.uniform(0, 10)
        cov = rng.random() < 0.5
        fid = rng.random() < 0.5
        if cov and fid:
            continue
        out = decide(lo, hi, rng.uniform(-10, 10), rng.uniform(-10, 10),
                     cov, fid, rng.uniform(0.1, 100))
        assert out != "pass"
