"""Fast-Forward request state machine.

Terminal states are immutable — once a request has decided, nothing may
rewrite history. COMPILED->ANALYZING is the no-hazard fast path; any
non-terminal state may bail to UNSUPPORTED or CANCELED.
"""

STATES = (
    "RECEIVED", "COMPILED", "PLANNED", "RUNNING", "ANALYZING",
    "COMPLETED", "UNSUPPORTED", "COUNTEREXAMPLE", "BUDGET_EXHAUSTED", "CANCELED",
)

TERMINAL = frozenset({
    "COMPLETED", "UNSUPPORTED", "COUNTEREXAMPLE", "BUDGET_EXHAUSTED", "CANCELED",
})

_ESCAPES = frozenset({"UNSUPPORTED", "CANCELED"})  # reachable from any non-terminal

LEGAL = {
    "RECEIVED": frozenset({"COMPILED"}) | _ESCAPES,
    "COMPILED": frozenset({"PLANNED", "ANALYZING"}) | _ESCAPES,
    "PLANNED": frozenset({"RUNNING"}) | _ESCAPES,
    "RUNNING": frozenset({"ANALYZING"}) | _ESCAPES,
    "ANALYZING": frozenset({"COMPLETED", "COUNTEREXAMPLE", "BUDGET_EXHAUSTED"}) | _ESCAPES,
    "COMPLETED": frozenset(),
    "UNSUPPORTED": frozenset(),
    "COUNTEREXAMPLE": frozenset(),
    "BUDGET_EXHAUSTED": frozenset(),
    "CANCELED": frozenset(),
}


def validate_transition(cur: str, new: str) -> None:
    """Raise ValueError unless cur -> new is a legal transition."""
    if cur not in LEGAL:
        raise ValueError(f"unknown state {cur!r}")
    if new not in STATES:
        raise ValueError(f"unknown state {new!r}")
    if cur in TERMINAL:
        raise ValueError(f"terminal state {cur} is immutable (attempted -> {new})")
    if new not in LEGAL[cur]:
        raise ValueError(f"illegal transition {cur} -> {new}")
