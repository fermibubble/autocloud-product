"""What Fast-Forward can actually accelerate — the honesty inventory.

Capabilities gate the planner: an experiment whose mode is not available
is never executable, and hazard classes compiled with an empty experiment
list (state/schedule/concurrency in the MVP) stay unsupported rather than
silently passing.
"""


def capabilities() -> dict:
    return {
        "modes": ["signal", "probe"],
        "age_axes": {
            "connection_cycles": "full",
            "requests": "full",
            "retries": "full",
            "expiry_events": "probe_advance",
            "wall_clock": "partial",
            "state": "none",
            "schedule": "none",
            "concurrency": "none",
        },
        "clock_coverage": "partial",
    }


def executable(experiment: str, caps: dict) -> bool:
    """An experiment "mode:template" is executable iff its mode is available.
    Classes compiled with experiments [] have nothing executable by construction."""
    mode = experiment.split(":", 1)[0]
    return mode in caps.get("modes", ())
