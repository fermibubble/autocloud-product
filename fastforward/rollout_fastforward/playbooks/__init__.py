"""Probe playbooks: template name -> runner over a ProbeContext.

Every playbook returns {disposition: counterexample|within_envelope|
inconclusive|unsupported, measurements, fidelity_axes, fidelity_report,
counterexample?, stop_reason} and never passes without a reference: a
missing stable profile triggers a paired clean run, and a missing clean
spec leaves the hazard inconclusive.
"""

from .. import fidelity, inventory

_CLOCK_AXIS = {"full": 1.0, "partial": 0.5, "none": 0.0}


def clock_axis() -> float:
    """clock_coverage per the honesty inventory (partial -> 0.5)."""
    return _CLOCK_AXIS[inventory.capabilities()["clock_coverage"]]


def base_axes(side_effect_attempts) -> dict:
    """Shared fidelity axes for sim probe runs. side_effect_semantics is 1.0
    only when attempts were observed AND contained by the membrane (the sim
    target's structural guarantee); an unobservable membrane scores 0."""
    return {
        "input_shape": 0.7,           # synthetic lifecycle shapes
        "concurrency": 0.6,
        "clock_coverage": clock_axis(),
        "state_representativeness": fidelity.SIM_STATE_CAP,
        "dependency_behavior": 0.8,   # dial-driven
        "side_effect_semantics": 1.0 if side_effect_attempts is not None else 0.0,
    }


def median(vals: list[float]) -> float:
    s = sorted(vals)
    n = len(s)
    return s[n // 2] if n % 2 else (s[n // 2 - 1] + s[n // 2]) / 2.0


from . import credential, leak, retry  # noqa: E402  (helpers above are theirs)

TEMPLATES = {
    "resource_lifecycle_v1": leak.run,
    "rate_balance_v1": retry.run,
    "cred_lifecycle_v1": credential.run,
}


def get(template: str):
    return TEMPLATES.get(template)
