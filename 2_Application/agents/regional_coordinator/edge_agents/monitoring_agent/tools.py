"""Monitoring Agent tools — collects RAN KPIs and power metrics."""

import random
from datetime import datetime
from typing import Dict, List, Optional

# Real H-TRACE core (Isolation Forest). Defensive import so the tool still works
# (threshold fallback) if the core or its ML deps are unavailable.
try:
    from agents.htrace_core import CORE
except Exception:  # pragma: no cover
    try:
        from htrace_core import CORE
    except Exception:
        CORE = None


def collect_ran_kpis(tower_id: str = "tower_1") -> Dict:
    """
    Collect Radio Access Network KPIs from a specific tower.
    Maps to the Network Operator KPI dataset (internet traffic, sessions, VPN, downstream).

    Args:
        tower_id: Tower identifier
    """
    kpi_value = round(random.uniform(100, 900), 2)
    return {
        "tower_id": tower_id,
        "timestamp": datetime.now().isoformat(),
        "kpis": {
            "internet_traffic_normalised": round(kpi_value / 1000, 3),
            "active_sessions": random.randint(50, 500),
            "vpn_traffic_normalised": round(random.uniform(0, 0.3), 3),
            "downstream_traffic_normalised": round(kpi_value * 0.6 / 1000, 3),
            "signal_strength_dbm": random.randint(-110, -60),
            "ber": round(random.uniform(0, 0.01), 5),
            "prb_utilisation_pct": round(random.uniform(20, 90), 2),
        },
        "raw_kpi_value": kpi_value,
    }


def collect_power_metrics(tower_id: str = "tower_1") -> Dict:
    """Collect power consumption and TRX status for a tower."""
    active_trx = random.randint(3, 10)
    total_trx = 10
    power_per_trx = random.uniform(60, 100)  # Watts
    return {
        "tower_id": tower_id,
        "timestamp": datetime.now().isoformat(),
        "power": {
            "total_consumption_w": round(active_trx * power_per_trx, 2),
            "per_trx_w": round(power_per_trx, 2),
            "active_trx": active_trx,
            "total_trx": total_trx,
            "shutdown_trx": total_trx - active_trx,
            "voltage_v": round(random.uniform(46, 54), 2),
            "power_factor": round(random.uniform(0.92, 0.99), 3),
        },
    }


def detect_anomaly(tower_id: str, kpi_value: float, threshold: float = 800.0) -> Dict:
    """
    SPOT a fault with the real H-TRACE Isolation Forest (unsupervised ML).

    The KPI sample is scored by the trained Isolation Forest in the H-TRACE
    core; a simple threshold is used only as a deterministic fallback when the
    ML core is unavailable. The detector is non-generative (it outputs a numeric
    score, never a command) — so it cannot hallucinate a control action.

    Args:
        tower_id: Tower identifier
        kpi_value: Current KPI measurement (0-1000 normalised range)
        threshold: Threshold used only by the deterministic fallback path
    """
    detector = "IsolationForest"
    if CORE is not None and getattr(CORE, "fitted", False):
        anomaly_score, is_anomaly = CORE.detect(float(kpi_value))
    else:
        # Deterministic fallback (pre-ML / core unavailable).
        detector = "threshold_fallback"
        is_anomaly = kpi_value > threshold or kpi_value < 50
        anomaly_score = min(1.0, abs(kpi_value - 500) / 500)

    if anomaly_score >= 0.85 or kpi_value > 950:
        severity = "critical"
    elif is_anomaly and kpi_value >= 500:
        severity = "high"
    elif kpi_value < 50:
        severity = "low_traffic"
    else:
        severity = "none"

    return {
        "tower_id": tower_id,
        "kpi_value": kpi_value,
        "detector": detector,
        "anomaly_score": round(float(anomaly_score), 4),
        "is_anomaly": bool(is_anomaly),
        "severity": severity,
        "timestamp": datetime.now().isoformat(),
    }
