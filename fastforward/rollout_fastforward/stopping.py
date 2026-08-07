"""Sequential stopping rule for probe experiments.

The asymmetry is the point: a confirmed harm (CI floor above the harm
threshold) stands even at budget zero, but "pass" is structurally
unreachable without remaining budget, coverage, AND fidelity — a truncated
or under-instrumented run can only ever be inconclusive, never clean.
"""


def decide(lo: float, hi: float, harm_threshold: float, safe_threshold: float,
           coverage_ok: bool, fidelity_ok: bool, budget_left: float) -> str:
    """One of "fail", "pass", "continue", "inconclusive_budget" — in that
    order of precedence."""
    if lo > harm_threshold:
        return "fail"
    if budget_left <= 0:
        return "inconclusive_budget"
    if hi < safe_threshold and coverage_ok and fidelity_ok:
        return "pass"
    return "continue"
