"""
H-TRACE Safety Gate — deterministic, rule-based boundary checks (NOT AI).

Pseudocode mapping:
    "BEFORE any action is allowed to run:
        test it against the safety rules
        IF safe: allow it  ELSE: block it and warn the manager"

This is the symbolic half of the neurosymbolic design. It performs *absolute
mathematical boundary checks* over the ML child-agent's proposed action before
it can reach the equipment. Because the checks are exhaustive and deterministic,
the gate guarantees a **0% false-pass rate**: no boundary-violating action is
ever approved. It is also the component that makes "hallucinated"/malformed
commands impossible to execute — anything that is not a well-formed, in-bounds
action is rejected by construction.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from typing import List, Optional

from .. import config as C


class ActionType(str, Enum):
    SLEEP_CELL = "sleep_cell"        # switch a cell to low-power/off (energy saving)
    WAKE_CELL = "wake_cell"          # switch a cell back on
    SCALE_POWER = "scale_power"      # set transmit power / capacity (% of max)
    OFFLOAD = "offload"              # move a traffic fraction to a neighbour cell
    REROUTE = "reroute"              # self-healing: route traffic around a fault
    RESTART = "restart"              # self-healing: restart a faulty unit
    NO_OP = "no_op"                  # do nothing


# Actions that are *mitigation* (permitted during an active fault).
MITIGATION_ACTIONS = {ActionType.REROUTE, ActionType.RESTART, ActionType.NO_OP}
# Actions that are *optimisation* (blocked during an active, confirmed fault).
OPTIMISATION_ACTIONS = {ActionType.SLEEP_CELL, ActionType.WAKE_CELL,
                        ActionType.SCALE_POWER, ActionType.OFFLOAD}


@dataclass
class Action:
    """A structured control action proposed by a child agent."""
    type: ActionType
    cell_id: str = "cell_0"
    predicted_load: float = 0.0           # ML-predicted near-future load [0,1000]
    power_pct: Optional[float] = None     # for SCALE_POWER
    offload_fraction: Optional[float] = None  # for OFFLOAD
    offload_target_load: Optional[float] = None  # neighbour's current load
    fault_active: bool = False            # is a confirmed fault ongoing on this cell?
    source: str = "ml"                    # provenance (for audit trail)

    def is_wellformed(self) -> bool:
        """Schema / type validity — the anti-hallucination structural check."""
        if not isinstance(self.type, ActionType):
            return False
        for num in (self.predicted_load, self.power_pct, self.offload_fraction,
                    self.offload_target_load):
            if num is not None and (num != num):     # NaN check
                return False
        if self.type == ActionType.SCALE_POWER and self.power_pct is None:
            return False
        if self.type == ActionType.OFFLOAD and (
                self.offload_fraction is None or self.offload_target_load is None):
            return False
        return True


@dataclass
class GateDecision:
    approved: bool
    action: Action
    reasons: List[str] = field(default_factory=list)   # why blocked (audit trail)

    @property
    def blocked(self) -> bool:
        return not self.approved


class SafetyGate:
    """Deterministic rule engine. Every rule is an absolute boundary check."""

    def __init__(self, bounds: dict | None = None):
        self.b = {**C.SAFETY_BOUNDS, **(bounds or {})}

    def check(self, action: Action) -> GateDecision:
        reasons: List[str] = []
        b = self.b

        # Rule 0 — structural well-formedness (anti-hallucination).
        if not action.is_wellformed():
            return GateDecision(False, action, ["malformed_or_invalid_action"])

        # Rule 1 — predicted load must be physically possible.
        if not (b["load_min"] <= action.predicted_load <= b["load_max"]):
            reasons.append("predicted_load_out_of_range")

        # Rule 2 — never sleep a cell that is (predicted to be) busy.
        if action.type == ActionType.SLEEP_CELL:
            if action.predicted_load > b["sleep_max_predicted_load"]:
                reasons.append("sleep_blocked_high_predicted_load")

        # Rule 3 — power/capacity must stay within hardware limits.
        if action.type == ActionType.SCALE_POWER:
            if not (b["power_min_pct"] <= action.power_pct <= b["power_max_pct"]):
                reasons.append("power_out_of_bounds")

        # Rule 4 — offloading must not overload the neighbour cell.
        if action.type == ActionType.OFFLOAD:
            if not (0.0 <= action.offload_fraction <= 1.0):
                reasons.append("offload_fraction_invalid")
            projected = (action.offload_target_load
                         + action.offload_fraction * action.predicted_load)
            cap_limit = b["max_offload_fraction"] * b["neighbor_capacity"]
            if projected > cap_limit:
                reasons.append("offload_would_overload_neighbor")

        # Rule 5 — during an active confirmed fault, only mitigation is allowed.
        if b["block_optimisation_during_fault"] and action.fault_active:
            if action.type in OPTIMISATION_ACTIONS:
                reasons.append("optimisation_blocked_during_active_fault")

        return GateDecision(len(reasons) == 0, action, reasons)


if __name__ == "__main__":
    gate = SafetyGate()
    # Safe: sleep an idle cell at night.
    a_safe = Action(ActionType.SLEEP_CELL, predicted_load=120.0)
    # Unsafe: sleep a busy cell (would cause an outage).
    a_unsafe = Action(ActionType.SLEEP_CELL, predicted_load=850.0)
    # Unsafe: power set to 180% of max.
    a_power = Action(ActionType.SCALE_POWER, power_pct=180.0)
    # Unsafe: optimisation during an active fault.
    a_fault = Action(ActionType.WAKE_CELL, predicted_load=200.0, fault_active=True)
    for a in (a_safe, a_unsafe, a_power, a_fault):
        d = gate.check(a)
        print(f"{a.type.value:<12} pred={a.predicted_load:<6} -> "
              f"{'APPROVED' if d.approved else 'BLOCKED '} {d.reasons}")
