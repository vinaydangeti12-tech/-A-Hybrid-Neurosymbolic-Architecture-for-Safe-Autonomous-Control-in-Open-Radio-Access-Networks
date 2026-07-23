"""Remediation tools for the Principal Agent — executes automated network healing."""

import random
from datetime import datetime
from typing import Dict

# Real deterministic Safety Gate from the H-TRACE core. Defensive import so
# remediation still runs (with the basic range check) if the core is missing.
try:
    from agents.htrace_core import CORE, Action, ActionType
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE, Action, ActionType
    except Exception:
        CORE = None; Action = None; ActionType = None


def restart_agent(agent_name: str, reason: str = "health_check_failure") -> Dict:
    """
    Soft restart of a specific agent to recover from transient failures.

    Args:
        agent_name: Name of agent to restart
        reason: Reason code for audit log
    """
    success = random.choices([True, False], weights=[75, 25])[0]
    result = {
        "operation": "restart_agent",
        "agent_name": agent_name,
        "reason": reason,
        "timestamp": datetime.now().isoformat(),
        "success": success,
    }
    if success:
        result.update({
            "status": "restarted",
            "message": f"Agent {agent_name} successfully restarted",
            "restart_time_seconds": round(random.uniform(5, 30), 1),
            "new_status": "active",
        })
    else:
        result.update({
            "status": "failed",
            "message": f"Failed to restart {agent_name}",
            "error": "Agent did not respond after restart attempt",
            "recommended_action": "escalate_to_redeploy",
        })
    return result


def redeploy_agent(agent_name: str, version: str = "latest") -> Dict:
    """
    Full redeploy of an agent — more aggressive than restart, fresh instance.

    Args:
        agent_name: Name of agent to redeploy
        version: Target version (default: latest)
    """
    success = random.choices([True, False], weights=[80, 20])[0]
    result = {
        "operation": "redeploy_agent",
        "agent_name": agent_name,
        "version": version,
        "timestamp": datetime.now().isoformat(),
        "success": success,
    }
    if success:
        result.update({
            "status": "deployed",
            "message": f"Agent {agent_name} redeployed (version: {version})",
            "deployment_time_seconds": round(random.uniform(30, 120), 1),
            "new_instance_id": f"inst-{random.randint(10000, 99999)}",
            "health_check": "passed",
        })
    else:
        result.update({
            "status": "failed",
            "message": f"Redeploy failed for {agent_name}",
            "error": "Container health check failed",
            "recommended_action": "escalate_to_human_operator",
        })
    return result


def reroute_traffic(source_tower: str, target_tower: str, percentage: float = 50.0) -> Dict:
    """
    Reroute traffic between towers for load balancing or fault recovery.
    Safety Gate: percentage must be 0-100; target capacity is pre-checked.

    Args:
        source_tower: Tower to move traffic away from
        target_tower: Tower to receive the rerouted traffic
        percentage: Percentage of traffic to move (0-100)
    """
    if not 0 <= percentage <= 100:
        return {
            "operation": "reroute_traffic",
            "success": False,
            "error": "percentage must be between 0 and 100",
        }

    # Real Safety Gate: model the reroute as an OFFLOAD and let the deterministic
    # gate verify it will not overload the target cell before anything executes.
    gate = {"approved": True, "reasons": [], "deterministic": False}
    if CORE is not None and ActionType is not None:
        pred = CORE.forecast() if getattr(CORE, "fitted", False) else 500.0
        proposed = Action(ActionType.OFFLOAD, cell_id=source_tower,
                          predicted_load=float(pred),
                          offload_fraction=percentage / 100.0,
                          offload_target_load=300.0)
        d = CORE.gate.check(proposed)
        gate = {"approved": bool(d.approved), "reasons": list(d.reasons),
                "deterministic": True}
    if not gate["approved"]:
        return {
            "operation": "reroute_traffic",
            "source_tower": source_tower,
            "target_tower": target_tower,
            "percentage": percentage,
            "success": False,
            "status": "blocked_by_safety_gate",
            "message": f"Safety Gate blocked reroute {source_tower}->{target_tower}: "
                       + ", ".join(gate["reasons"]),
            "safety_gate": gate,
            "recommended_action": "find_alternative_tower",
            "timestamp": datetime.now().isoformat(),
        }

    success = random.choices([True, False], weights=[80, 20])[0]
    result = {
        "operation": "reroute_traffic",
        "source_tower": source_tower,
        "target_tower": target_tower,
        "percentage": percentage,
        "safety_gate": gate,
        "timestamp": datetime.now().isoformat(),
        "success": success,
    }
    if success:
        result.update({
            "status": "completed",
            "message": f"Rerouted {percentage}% traffic from {source_tower} to {target_tower}",
            "execution_time_seconds": round(random.uniform(10, 60), 1),
            "connections_moved": random.randint(100, 1000),
            "target_load_after": round(random.uniform(0.5, 0.85), 2),
        })
    else:
        result.update({
            "status": "failed",
            "message": f"Reroute from {source_tower} to {target_tower} failed",
            "error": "Target tower capacity would be exceeded — Safety Gate blocked action",
            "recommended_action": "find_alternative_tower",
        })
    return result
