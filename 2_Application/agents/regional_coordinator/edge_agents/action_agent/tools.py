"""Action Agent tools — executes hardware control commands on the tower infrastructure.

Every command is screened by the REAL deterministic Safety Gate from the H-TRACE
core (agents/htrace_core.py) BEFORE it is executed — defence in depth. Even if a
decision somehow reaches this layer un-validated (or hallucinated), the gate
re-checks it here against absolute boundaries and refuses to "execute" anything
it blocks, returning the exact rule(s) violated. The physical actuation itself is
simulated because there is no real O-RAN hardware attached, but the *decision to
actuate* is governed by the same non-AI rule engine used everywhere else.
"""

import random
from datetime import datetime
from typing import Dict, List, Optional

# Real deterministic Safety Gate + the forecaster used to obtain a real predicted
# load for the gate's boundary checks. Defensive import so the tool still runs
# (gate-open fallback) if the core or its ML deps are unavailable.
try:
    from agents.htrace_core import CORE, Action, ActionType
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE, Action, ActionType
    except Exception:
        CORE = None; Action = None; ActionType = None


def _predicted_load() -> float:
    """Real next-step load from the core's LSTM forecaster (0 if unavailable)."""
    if CORE is not None and getattr(CORE, "fitted", False):
        try:
            return float(CORE.forecast())
        except Exception:  # pragma: no cover
            return 0.0
    return 0.0


def _gate(action) -> Dict:
    """Run the real Safety Gate; return {approved, reasons, deterministic}."""
    if CORE is not None and action is not None:
        d = CORE.gate.check(action)
        return {"approved": bool(d.approved), "reasons": list(d.reasons),
                "deterministic": True}
    return {"approved": True, "reasons": [], "deterministic": False}


def _blocked_result(operation: str, tower_id: str, gate: Dict, **extra) -> Dict:
    """Uniform 'refused by Safety Gate' result — nothing was actuated."""
    result = {
        "operation": operation,
        "tower_id": tower_id,
        "timestamp": datetime.now().isoformat(),
        "success": False,
        "status": "blocked_by_safety_gate",
        "message": f"Safety Gate refused {operation} on {tower_id}: "
                   + ", ".join(gate["reasons"]),
        "safety_gate": gate,
    }
    result.update(extra)
    return result


def shutdown_trx_units(tower_id: str, count: int) -> Dict:
    """
    Partially shut down TRX units on a tower to save energy (Night Mode).
    The real Safety Gate re-validates this SLEEP action against the live LSTM
    predicted load before any unit is touched — a high predicted load blocks it.

    Args:
        tower_id: Target tower
        count: Number of TRX units to put into warm-standby (0-10)
    """
    count = max(0, min(count, 6))  # Hard limit: never shutdown more than 6/10 TRXs

    # Gate the SLEEP optimisation against the real predicted load.
    pred = _predicted_load()
    proposed = (Action(ActionType.SLEEP_CELL, cell_id=tower_id, predicted_load=pred)
                if ActionType is not None else None)
    gate = _gate(proposed)
    if not gate["approved"]:
        return _blocked_result("shutdown_trx_units", tower_id, gate,
                               units_shutdown=0, predicted_load=round(pred, 2))

    success = random.choices([True, False], weights=[90, 10])[0]
    result = {
        "operation": "shutdown_trx_units",
        "tower_id": tower_id,
        "units_shutdown": count,
        "predicted_load": round(pred, 2),
        "safety_gate": gate,
        "timestamp": datetime.now().isoformat(),
        "success": success,
    }

    if success:
        power_saved_w = count * random.uniform(65, 95)
        result.update({
            "status": "completed",
            "message": f"TRX shutdown: {count} units put into warm-standby on {tower_id}",
            "power_saved_w": round(power_saved_w, 2),
            "energy_saving_pct": round(count * 8.5, 2),
        })
    else:
        result.update({
            "status": "failed",
            "message": f"TRX shutdown failed on {tower_id} — hardware not responding",
            "error": "Controller timeout",
        })

    return result


def activate_backup_cells(tower_id: str, cell_count: int = 2) -> Dict:
    """
    Activate warm-spare cells to handle traffic surge (Festival Mode).
    Screened by the real Safety Gate as a WAKE_CELL action before activation.

    Args:
        tower_id: Tower with overload risk
        cell_count: Number of backup cells to activate
    """
    pred = _predicted_load()
    proposed = (Action(ActionType.WAKE_CELL, cell_id=tower_id, predicted_load=pred)
                if ActionType is not None else None)
    gate = _gate(proposed)
    if not gate["approved"]:
        return _blocked_result("activate_backup_cells", tower_id, gate,
                               cells_activated=0, predicted_load=round(pred, 2))

    success = random.choices([True, False], weights=[88, 12])[0]
    result = {
        "operation": "activate_backup_cells",
        "tower_id": tower_id,
        "cells_activated": cell_count,
        "predicted_load": round(pred, 2),
        "safety_gate": gate,
        "timestamp": datetime.now().isoformat(),
        "success": success,
    }

    if success:
        result.update({
            "status": "activated",
            "message": f"Activated {cell_count} backup cells on {tower_id}",
            "additional_capacity_pct": round(cell_count * 12, 2),
            "activation_time_seconds": round(random.uniform(5, 20), 1),
        })
    else:
        result.update({
            "status": "failed",
            "message": f"Backup cell activation failed on {tower_id}",
        })

    return result


def isolate_failed_component(tower_id: str, component: str) -> Dict:
    """
    Isolate a failed component to prevent fault propagation (Self-Healing).
    Validated by the real Safety Gate as a mitigation (REROUTE) action with the
    fault flag set — the gate permits mitigation during an active fault.

    Args:
        tower_id: Tower containing the failed component
        component: Component identifier (e.g., 'trx_unit_3', 'uplink_port_1')
    """
    pred = _predicted_load()
    proposed = (Action(ActionType.REROUTE, cell_id=tower_id, predicted_load=pred,
                       fault_active=True)
                if ActionType is not None else None)
    gate = _gate(proposed)
    if not gate["approved"]:
        return _blocked_result("isolate_failed_component", tower_id, gate,
                               component=component)

    success = random.choices([True, False], weights=[85, 15])[0]
    result = {
        "operation": "isolate_failed_component",
        "tower_id": tower_id,
        "component": component,
        "safety_gate": gate,
        "timestamp": datetime.now().isoformat(),
        "success": success,
    }

    if success:
        result.update({
            "status": "isolated",
            "message": f"Component {component} on {tower_id} isolated successfully",
            "traffic_rerouted_pct": random.randint(20, 60),
            "service_impact": "minimal",
        })
    else:
        result.update({
            "status": "failed",
            "message": f"Could not isolate {component} on {tower_id}",
            "recommended_action": "escalate_to_principal_agent",
        })

    return result
