"""Health monitoring tools for the Principal Agent."""

import random
from datetime import datetime
from typing import Dict

# Real H-TRACE core, so health reflects the actual ML backend state (Isolation
# Forest / LSTM fitted) rather than only simulated infrastructure metrics.
try:
    from agents.htrace_core import CORE
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE
    except Exception:
        CORE = None


def _ml_core_health() -> Dict:
    """Real fitted state of the H-TRACE ML core (facts, not simulated)."""
    if CORE is None:
        return {"status": "unavailable", "core_available": False}
    b = CORE.backend
    fitted = bool(b.get("fitted"))
    return {
        "status": "healthy" if fitted else "degraded",
        "core_available": True,
        "core_fitted": fitted,
        "isolation_forest_fitted": bool(b.get("sklearn")),
        "lstm_fitted": bool(b.get("torch_lstm")),
        "safety_gate": "deterministic_rule_engine",
    }


def check_system_health() -> Dict:
    """
    Check overall system health across all agents and infrastructure.
    Returns system health status, component details, and current metrics.
    """
    status = random.choices(
        ["healthy", "degraded", "critical"],
        weights=[70, 20, 10],
    )[0]

    result = {
        "timestamp": datetime.now().isoformat(),
        "overall_status": status,
        "components": {
            "parent_agents": {
                "status": random.choices(["healthy", "degraded"], weights=[85, 15])[0],
                "active_count": 1,
                "total_count": 1,
            },
            "edge_agents": {
                "status": random.choices(["healthy", "degraded"], weights=[90, 10])[0],
                "active_count": random.randint(4, 5),
                "total_count": 5,
            },
            "towers": {
                "status": random.choices(["healthy", "degraded"], weights=[92, 8])[0],
                "active_count": random.randint(8, 10),
                "total_count": 10,
            },
            "ml_core": _ml_core_health(),
        },
        "metrics": {
            "cpu_usage_avg": random.randint(30, 85),
            "memory_usage_avg": random.randint(40, 80),
            "network_latency_ms": random.randint(10, 100),
            "error_rate": round(random.uniform(0, 0.05), 4),
        },
    }

    if status != "healthy":
        result["issues"] = [
            {
                "severity": "warning" if status == "degraded" else "critical",
                "component": random.choice(["edge_agent_tower_3", "regional_coordinator", "network_link_1"]),
                "message": (
                    "High resource utilisation detected" if status == "degraded"
                    else "Agent unresponsive — initiating self-healing"
                ),
                "timestamp": datetime.now().isoformat(),
            }
        ]

    return result


def get_agent_status(agent_name: str) -> Dict:
    """
    Get detailed status information for a specific agent.

    Args:
        agent_name: e.g. 'monitoring_agent', 'prediction_agent', 'principal_agent'
    """
    status = random.choices(
        ["active", "inactive", "error"],
        weights=[85, 10, 5],
    )[0]

    result = {
        "agent_name": agent_name,
        "status": status,
        "timestamp": datetime.now().isoformat(),
        "uptime_seconds": random.randint(3600, 86400),
        "last_heartbeat": datetime.now().isoformat(),
        "metrics": {
            "requests_processed": random.randint(1000, 10000),
            "average_response_time_ms": random.randint(50, 500),
            "error_count": random.randint(0, 10),
            "success_rate": round(random.uniform(0.95, 1.0), 4),
        },
        "resource_usage": {
            "cpu_percent": random.randint(20, 90),
            "memory_mb": random.randint(128, 1024),
            "threads": random.randint(5, 20),
        },
    }

    if status != "active":
        result["error_details"] = {
            "error_type": "timeout" if status == "inactive" else "exception",
            "message": (
                "Agent stopped responding" if status == "inactive"
                else "Runtime error in agent execution"
            ),
            "occurred_at": datetime.now().isoformat(),
        }

    return result
