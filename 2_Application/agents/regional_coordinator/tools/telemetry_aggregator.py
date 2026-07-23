"""Telemetry aggregation tools for the Regional Coordinator."""

import random
from datetime import datetime
from typing import Any, Dict, List, Optional


def aggregate_telemetry(tower_ids: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Aggregate telemetry from multiple towers in the region.
    In production this queries the real RAN KPI time series.

    Args:
        tower_ids: List of tower IDs; defaults to all 10 regional towers.
    """
    if tower_ids is None:
        tower_ids = [f"tower_{i}" for i in range(1, 11)]

    return {
        "timestamp": datetime.now().isoformat(),
        "region": "region-IE-01",
        "towers_count": len(tower_ids),
        "aggregated_metrics": {
            "total_traffic_normalised": round(random.uniform(0.3, 0.85), 3),
            "average_load_percent": round(random.uniform(35, 80), 2),
            "total_energy_kwh": round(random.uniform(400, 1600), 2),
            "total_connections": random.randint(3000, 18000),
            "average_latency_ms": random.randint(15, 90),
        },
        "tower_breakdown": [
            {
                "tower_id": tid,
                "traffic_normalised": round(random.uniform(0.2, 0.9), 3),
                "load_percent": round(random.uniform(25, 95), 2),
                "energy_kwh": round(random.uniform(40, 200), 2),
                "connections": random.randint(300, 2000),
                "status": random.choices(["healthy", "degraded"], weights=[90, 10])[0],
            }
            for tid in tower_ids
        ],
    }


def get_regional_metrics(metric_name: str = "all") -> Dict[str, Any]:
    """
    Get specific regional KPI metrics.

    Args:
        metric_name: 'traffic' | 'energy' | 'performance' | 'all'
    """
    metrics: Dict[str, Any] = {
        "timestamp": datetime.now().isoformat(),
        "region": "region-IE-01",
    }

    if metric_name in ("all", "traffic"):
        metrics["traffic"] = {
            "current_normalised": round(random.uniform(0.3, 0.85), 3),
            "peak_normalised": round(random.uniform(0.7, 0.98), 3),
            "total_connections": random.randint(5000, 20000),
        }

    if metric_name in ("all", "energy"):
        metrics["energy"] = {
            "current_consumption_kwh": round(random.uniform(600, 1500), 2),
            "savings_today_kwh": round(random.uniform(200, 700), 2),
            "efficiency_percent": round(random.uniform(28, 42), 2),
            "towers_optimised": random.randint(3, 7),
        }

    if metric_name in ("all", "performance"):
        metrics["performance"] = {
            "average_latency_ms": random.randint(20, 75),
            "success_rate": round(random.uniform(0.98, 0.999), 4),
            "dropped_calls": random.randint(0, 4),
            "call_blocking_probability": round(random.uniform(0, 0.02), 4),
        }

    return metrics
