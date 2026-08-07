"""Robust-stats tests: recovery under contamination, boundary behavior."""

import math
import random

from rollout_fastforward.stats import (huber_mean, mad, mad_z, retry_m,
                                       theil_sen, time_to_threshold)


def test_theil_sen_recovers_slope_under_contamination():
    # Heavy-tailed noise plus 20 percent gross outliers; Theil-Sen's
    # breakdown point (~29 percent) must ride it out.
    rng = random.Random(42)
    pts = []
    for i in range(200):
        noise = (rng.paretovariate(2.5) - 1.67) * (1 if rng.random() < 0.5 else -1)
        y = 0.5 * i + noise
        if rng.random() < 0.2:
            y += rng.choice([-1.0, 1.0]) * 150.0
        pts.append((float(i), y))
    est = theil_sen(pts)
    assert abs(est["slope"] - 0.5) <= 0.1  # within 20 percent
    assert est["lo"] <= est["slope"] <= est["hi"]


def test_theil_sen_flat_series_ci_contains_zero():
    rng = random.Random(7)
    pts = [(float(i), 5.0 + rng.gauss(0, 0.2)) for i in range(60)]
    est = theil_sen(pts)
    assert est["lo"] <= 0.0 <= est["hi"]


def test_theil_sen_degenerate_inputs():
    assert theil_sen([]) == {"slope": 0.0, "lo": 0.0, "hi": 0.0}
    assert theil_sen([(1.0, 2.0), (1.0, 9.0)])["slope"] == 0.0  # vertical only


def test_retry_m_boundaries():
    assert math.isclose(retry_m(0.3, 4), 1.2)  # demo-retry: amplifying
    assert retry_m(0.0, 10) == 0.0
    assert math.isclose(retry_m(0.25, 4), 1.0)  # exactly balanced
    assert retry_m(0.2, 4) < 1.0  # damped


def test_time_to_threshold():
    assert math.isclose(time_to_threshold(100, 3.0, 1000, 10), 30.0)
    assert time_to_threshold(100, 0.0, 1000, 10) == float("inf")
    assert time_to_threshold(100, -0.5, 1000, 10) == float("inf")
    assert time_to_threshold(1000, 3.0, 1000, 10) == 0.0  # already breached


def test_mad_and_mad_z():
    assert mad([1, 2, 3, 4, 5]) == 1
    z = mad_z(5.0, 3.0, 1.0)
    assert math.isclose(z, 2.0 / 1.4826, rel_tol=1e-9)
    # mad 0 must not divide by zero — guarded by epsilon, stays finite.
    assert math.isfinite(mad_z(5.0, 3.0, 0.0))
    assert mad_z(3.0, 3.0, 0.0) == 0.0


def test_huber_mean_resists_outliers():
    vals = [1.0, 1.1, 0.9, 1.05, 0.95, 100.0]
    assert abs(huber_mean(vals) - 1.0) < 0.5
    assert abs(sum(vals) / len(vals) - 1.0) > 10  # the plain mean does not
