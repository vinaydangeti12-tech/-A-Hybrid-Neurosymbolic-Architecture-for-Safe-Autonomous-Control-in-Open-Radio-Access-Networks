"""Load balancing tools for the Regional Coordinator."""

import random
from datetime import datetime
from typing import Dict, List, Optional

# Real deterministic Safety Gate from the H-TRACE core. Defensive import so load
# balancing still proposes reroutes (un-gated) if the core is unavailable.
try:
    from agents.htrace_core import CORE, Action, ActionType
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE, Action, ActionType
    except Exception:
        CORE = None; Action = None; ActionType = None


def _gate_reroute(source: str, pct: int) -> Dict:
    """Validate a reroute (modelled as OFFLOAD) with the real Safety Gate."""
    if CORE is not None and ActionType is not None:
        pred = CORE.forecast() if getattr(CORE, "fitted", False) else 500.0
        d = CORE.gate.check(Action(ActionType.OFFLOAD, cell_id=source,
                                   predicted_load=float(pred),
                                   offload_fraction=pct / 100.0,
                                   offload_target_load=300.0))
        return {"approved": bool(d.approved), "reasons": list(d.reasons),
                "deterministic": True}
    return {"approved": True, "reasons": [], "deterministic": False}


def balance_load(source_towers: Optional[List[str]] = None, strategy: str = "least_loaded") -> Dict:
    """
    Compute and apply load-balancing decisions across the tower cluster.

    Args:
        source_towers: Towers to consider for rebalancing (default: all)
        strategy: 'least_loaded' | 'round_robin' | 'geographic'
    """
    if source_towers is None:
        source_towers = [f"tower_{i}" for i in range(1, 11)]

    overloaded = [t for t in source_towers if random.random() > 0.75]
    underloaded = [t for t in source_towers if random.random() > 0.6 and t not in overloaded]

    actions = []
    blocked = []
    for src in overloaded[:2]:
        if underloaded:
            dst = random.choice(underloaded)
            pct = random.randint(20, 40)
            gate = _gate_reroute(src, pct)
            entry = {
                "action": "reroute",
                "source": src,
                "destination": dst,
                "percentage": pct,
                "estimated_relief_ms": random.randint(5, 30),
                "safety_gate": gate,
            }
            # Only emit reroutes the deterministic Safety Gate approves.
            (actions if gate["approved"] else blocked).append(entry)

    return {
        "timestamp": datetime.now().isoformat(),
        "strategy": strategy,
        "overloaded_towers": overloaded,
        "underloaded_towers": underloaded,
        "actions": actions,
        "blocked_by_safety_gate": blocked,
        "estimated_efficiency_gain_pct": round(random.uniform(5, 20), 2) if actions else 0,
    }


def get_tower_status(tower_id: Optional[str] = None) -> Dict:
    """
    Get current status of one or all towers.

    Args:
        tower_id: Specific tower ID; if None returns all towers.
    """
    towers = [tower_id] if tower_id else [f"tower_{i}" for i in range(1, 11)]

    statuses = []
    for tid in towers:
        load = round(random.uniform(20, 95), 2)
        statuses.append({
            "tower_id": tid,
            "status": "healthy" if load < 85 else "degraded",
            "load_percent": load,
            "active_connections": random.randint(200, 2000),
            "energy_kwh": round(random.uniform(40, 180), 2),
            "active_trx": random.randint(4, 10),
            "total_trx": 10,
            "last_seen": datetime.now().isoformat(),
        })

    return {
        "timestamp": datetime.now().isoformat(),
        "towers": statuses,
        "summary": {
            "total": len(statuses),
            "healthy": sum(1 for s in statuses if s["status"] == "healthy"),
            "degraded": sum(1 for s in statuses if s["status"] == "degraded"),
        },
    }
