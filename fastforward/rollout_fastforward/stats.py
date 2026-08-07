"""Robust statistics for accelerated-probe measurements.

Probe series are short and contaminated (warmup spikes, gross outliers),
so everything here is median/MAD-based: Theil-Sen slopes with a pairwise-
slope CI, Huber means, MAD z-scores. No parametric assumptions.
"""

_EPS = 1e-9
_MAD_K = 1.4826  # normal-consistency constant


def _median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    if n == 0:
        raise ValueError("median of empty sequence")
    mid = n // 2
    return s[mid] if n % 2 else (s[mid - 1] + s[mid]) / 2.0


def _percentile(sorted_vals: list[float], q: float) -> float:
    n = len(sorted_vals)
    if n == 1:
        return sorted_vals[0]
    pos = q * (n - 1)
    i = int(pos)
    frac = pos - i
    if i + 1 >= n:
        return sorted_vals[-1]
    return sorted_vals[i] * (1 - frac) + sorted_vals[i + 1] * frac


def theil_sen(points: list[tuple[float, float]]) -> dict:
    """Median of pairwise slopes; lo/hi are the 5th/95th percentiles of the
    pairwise-slope distribution (a robust CI proxy)."""
    pts = list(points)
    slopes = []
    for i in range(len(pts)):
        xi, yi = pts[i]
        for j in range(i + 1, len(pts)):
            dx = pts[j][0] - xi
            if dx == 0:
                continue
            slopes.append((pts[j][1] - yi) / dx)
    if not slopes:
        return {"slope": 0.0, "lo": 0.0, "hi": 0.0}
    slopes.sort()
    return {"slope": _percentile(slopes, 0.5),
            "lo": _percentile(slopes, 0.05),
            "hi": _percentile(slopes, 0.95)}


def mad(values: list[float]) -> float:
    med = _median(values)
    return _median([abs(v - med) for v in values])


def mad_z(value: float, median: float, mad_val: float) -> float:
    return (value - median) / max(_MAD_K * mad_val, _EPS)


def huber_mean(values: list[float], k: float = 1.5, iters: int = 20) -> float:
    vals = [float(v) for v in values]
    mu = _median(vals)
    scale = max(_MAD_K * mad(vals), _EPS)
    for _ in range(iters):
        weights = []
        for v in vals:
            d = abs(v - mu)
            weights.append(1.0 if d <= k * scale else (k * scale) / d)
        new_mu = sum(w * v for w, v in zip(weights, vals)) / sum(weights)
        if abs(new_mu - mu) < 1e-12:
            break
        mu = new_mu
    return mu


def retry_m(p_f: float, e_k: float) -> float:
    """Retry amplification multiplier: m > 1 means unbounded growth."""
    return p_f * e_k


def time_to_threshold(current: float, slope_per_op: float, threshold: float,
                      ops_per_min: float) -> float:
    """Minutes until threshold at the observed slope; inf when not growing."""
    if current >= threshold:
        return 0.0
    if slope_per_op <= 0 or ops_per_min <= 0:
        return float("inf")
    return (threshold - current) / (slope_per_op * ops_per_min)
