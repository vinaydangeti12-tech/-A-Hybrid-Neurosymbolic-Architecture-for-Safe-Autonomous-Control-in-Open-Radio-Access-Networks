"""Policy enforcement tools — the Safety Gate layer.

Enforcement now runs TWO complementary deterministic checks and only allows an
action if BOTH pass:

  1. The regional percentage limits below (operator policy: e.g. never shut down
     more than 60% of TRXs in one cycle).
  2. The REAL H-TRACE Safety Gate from agents/htrace_core.py (the same absolute
     boundary engine the edge agents use: sleep only on low predicted load,
     power 0-100%, offload must not overload a neighbour, mitigation-only during
     a fault). This is rule-based, NOT AI, so it cannot hallucinate an approval.
"""

from datetime import datetime
from typing import Any, Dict

# Real deterministic Safety Gate from the core. Defensive import so enforcement
# still applies the regional percentage limits if the core is unavailable.
try:
    from agents.htrace_core import CORE, Action, ActionType
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE, Action, ActionType
    except Exception:
        CORE = None; Action = None; ActionType = None


# Hard limits enforced by the regional policy layer
SAFETY_LIMITS = {
    "max_trx_shutdown_pct": 60,    # Never shut down more than 60% of TRXs at once
    "min_coverage_pct": 85,         # Always maintain at least 85% coverage
    "max_reroute_pct": 80,          # Max traffic shift in a single action
    "max_power_reduction_pct": 40,  # Max power reduction per TRX cycle
}


def _core_gate(action) -> Dict:
    """Run the real H-TRACE Safety Gate; return {approved, reasons, deterministic}."""
    if CORE is not None and action is not None:
        d = CORE.gate.check(action)
        return {"approved": bool(d.approved), "reasons": list(d.reasons),
                "deterministic": True}
    return {"approved": True, "reasons": [], "deterministic": False}


def _build_action(action: str, parameters: Dict[str, Any]):
    """Map an enforcement request to a core Action for the real Safety Gate."""
    if ActionType is None:
        return None
    if action == "trx_shutdown":
        # Sleeping TRX units = SLEEP_CELL; gate it against the predicted load.
        pred = float(parameters.get("predicted_load", 0.0))
        return Action(ActionType.SLEEP_CELL, cell_id=parameters.get("tower_id", "cell_0"),
                      predicted_load=pred)
    if action == "traffic_reroute":
        pct = float(parameters.get("percentage", 0)) / 100.0
        load = float(parameters.get("predicted_load", 0.0))
        return Action(ActionType.OFFLOAD, cell_id=parameters.get("tower_id", "cell_0"),
                      predicted_load=load, offload_fraction=pct,
                      offload_target_load=float(parameters.get("target_load", 300.0)))
    if action == "power_reduction":
        # Map a reduction-% to a remaining power-% for the gate's 0-100 check.
        remaining = max(0.0, 100.0 - float(parameters.get("reduction_percentage", 0)))
        return Action(ActionType.SCALE_POWER, cell_id=parameters.get("tower_id", "cell_0"),
                      power_pct=remaining)
    return None


def enforce_policy(action: str, parameters: Dict[str, Any]) -> Dict:
    """
    Validate an action against regional policy limits AND the real Safety Gate.
    Allowed only if both deterministic checks pass.

    Args:
        action: Action type ('trx_shutdown', 'traffic_reroute', 'power_reduction')
        parameters: Action-specific parameters

    Returns:
        Dict with 'allowed' bool, 'reason' string and the core 'safety_gate' result.
    """
    result = {
        "action": action,
        "parameters": parameters,
        "timestamp": datetime.now().isoformat(),
        "evaluated_limits": SAFETY_LIMITS,
    }

    # Layer 1 — regional percentage limits.
    limit_ok = True
    limit_reason = f"Action '{action}' has no specific limit — approved by default"

    if action == "trx_shutdown":
        shutdown_pct = parameters.get("shutdown_percentage", 0)
        if shutdown_pct > SAFETY_LIMITS["max_trx_shutdown_pct"]:
            limit_ok = False
            limit_reason = (f"TRX shutdown {shutdown_pct}% exceeds limit of "
                            f"{SAFETY_LIMITS['max_trx_shutdown_pct']}%")
        else:
            limit_reason = f"TRX shutdown {shutdown_pct}% within limits"
    elif action == "traffic_reroute":
        reroute_pct = parameters.get("percentage", 0)
        if reroute_pct > SAFETY_LIMITS["max_reroute_pct"]:
            limit_ok = False
            limit_reason = (f"Reroute {reroute_pct}% exceeds limit of "
                            f"{SAFETY_LIMITS['max_reroute_pct']}%")
        else:
            limit_reason = f"Reroute {reroute_pct}% within limits"
    elif action == "power_reduction":
        reduction_pct = parameters.get("reduction_percentage", 0)
        if reduction_pct > SAFETY_LIMITS["max_power_reduction_pct"]:
            limit_ok = False
            limit_reason = f"Power reduction {reduction_pct}% exceeds limit"
        else:
            limit_reason = f"Power reduction {reduction_pct}% approved"

    # Layer 2 — the real H-TRACE Safety Gate.
    gate = _core_gate(_build_action(action, parameters))

    allowed = limit_ok and gate["approved"]
    reasons = []
    if not limit_ok:
        reasons.append(limit_reason)
    if not gate["approved"]:
        reasons.extend(f"safety_gate:{r}" for r in gate["reasons"])

    result.update({
        "allowed": allowed,
        "reason": limit_reason if allowed else "; ".join(reasons),
        "limit_check": {"passed": limit_ok, "reason": limit_reason},
        "safety_gate": gate,
    })
    return result


def validate_action(action_type: str, tower_id: str, value: float) -> Dict:
    """
    Quick safety validation for a tower action — regional limits + real Safety Gate.

    Args:
        action_type: 'shutdown' | 'reroute' | 'power_change'
        tower_id: Target tower identifier
        value: Magnitude of the action (percentage or absolute)
    """
    allowed = True
    violations = []

    if action_type == "shutdown" and value > SAFETY_LIMITS["max_trx_shutdown_pct"]:
        allowed = False
        violations.append(f"Shutdown {value}% exceeds {SAFETY_LIMITS['max_trx_shutdown_pct']}% limit")

    if action_type == "reroute" and value > SAFETY_LIMITS["max_reroute_pct"]:
        allowed = False
        violations.append(f"Reroute {value}% exceeds {SAFETY_LIMITS['max_reroute_pct']}% limit")

    # Cross-check with the real Safety Gate where the action maps cleanly.
    _map = {"shutdown": "trx_shutdown", "reroute": "traffic_reroute",
            "power_change": "power_reduction"}
    gate = _core_gate(_build_action(_map.get(action_type, ""),
                                    {"tower_id": tower_id,
                                     "percentage": value,
                                     "reduction_percentage": value}))
    if not gate["approved"]:
        allowed = False
        violations.extend(f"safety_gate:{r}" for r in gate["reasons"])

    return {
        "allowed": allowed,
        "tower_id": tower_id,
        "action_type": action_type,
        "value": value,
        "violations": violations,
        "safety_gate": gate,
        "timestamp": datetime.now().isoformat(),
    }
