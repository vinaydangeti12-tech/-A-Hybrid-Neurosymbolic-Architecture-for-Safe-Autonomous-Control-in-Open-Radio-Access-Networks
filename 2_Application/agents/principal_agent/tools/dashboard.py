"""Dashboard and metrics reporting tools for the Principal Agent."""

import random
from datetime import datetime, timedelta
from typing import Dict


def generate_health_dashboard() -> Dict:
    """Generate a comprehensive health dashboard for the TRACE system."""
    now = datetime.now()
    return {
        "generated_at": now.isoformat(),
        "system_overview": {
            "status": random.choices(["healthy", "degraded"], weights=[85, 15])[0],
            "uptime_percentage": round(random.uniform(99.5, 99.99), 3),
            "total_towers": 10,
            "active_towers": random.randint(9, 10),
            "total_agents": 7,
            "active_agents": random.randint(6, 7),
        },
        "performance_metrics": {
            "energy_savings_percent": round(random.uniform(28, 42), 2),
            "network_efficiency": round(random.uniform(0.90, 0.98), 3),
            "average_response_time_ms": random.randint(50, 200),
            "successful_requests_percent": round(random.uniform(98, 99.9), 2),
        },
        "resource_utilisation": {
            "cpu_usage_avg": random.randint(40, 70),
            "memory_usage_avg": random.randint(50, 75),
            "network_bandwidth_utilisation": round(random.uniform(0.4, 0.8), 2),
        },
        "energy_optimisation": {
            "towers_with_reduced_power": random.randint(3, 6),
            "estimated_kwh_saved_today": round(random.uniform(500, 1500), 2),
            "co2_reduction_kg": round(random.uniform(200, 600), 2),
        },
        "traffic_management": {
            "peak_traffic_normalised": round(random.uniform(0.6, 0.95), 3),
            "congestion_events_prevented": random.randint(1, 8),
            "load_balancing_actions": random.randint(5, 25),
        },
        "recent_incidents": [
            {
                "id": f"INC-{random.randint(1000, 9999)}",
                "severity": random.choice(["warning", "critical"]),
                "component": random.choice(["tower_3", "edge_agent_2", "network_link_1"]),
                "status": random.choice(["resolved", "investigating"]),
                "timestamp": (now - timedelta(minutes=random.randint(10, 180))).isoformat(),
            }
            for _ in range(random.randint(0, 3))
        ],
    }


def get_system_metrics(metric_type: str = "all") -> Dict:
    """
    Get system metrics. metric_type: 'all' | 'energy' | 'traffic' | 'performance' | 'health'
    """
    now = datetime.now()
    result: Dict = {
        "metric_type": metric_type,
        "generated_at": now.isoformat(),
    }

    if metric_type in ("all", "energy"):
        result["energy_metrics"] = {
            "current_consumption_kwh": round(random.uniform(80, 160), 2),
            "peak_consumption_kwh": round(random.uniform(160, 220), 2),
            "savings_percent": round(random.uniform(28, 42), 2),
            "trend": random.choice(["decreasing", "stable", "increasing"]),
        }

    if metric_type in ("all", "traffic"):
        result["traffic_metrics"] = {
            "current_traffic_normalised": round(random.uniform(0.3, 0.85), 3),
            "peak_traffic_normalised": round(random.uniform(0.7, 0.98), 3),
            "total_connections": random.randint(5000, 30000),
            "trend": random.choice(["increasing", "stable", "decreasing"]),
        }

    if metric_type in ("all", "performance"):
        result["performance_metrics"] = {
            "average_latency_ms": random.randint(20, 120),
            "p95_latency_ms": random.randint(120, 280),
            "success_rate": round(random.uniform(0.98, 0.999), 4),
            "error_rate": round(random.uniform(0.001, 0.02), 4),
        }

    if metric_type in ("all", "health"):
        result["health_metrics"] = {
            "healthy_components": random.randint(55, 68),
            "total_components": 68,
            "uptime_percentage": round(random.uniform(99.5, 99.99), 3),
            "mean_time_to_recovery_seconds": random.randint(60, 300),
            "incidents_count": random.randint(0, 4),
        }

    return result


def generate_incident_report(incident_id: str) -> Dict:
    """Generate a detailed incident report for a given incident ID."""
    now = datetime.now()
    incident_time = now - timedelta(minutes=random.randint(30, 180))
    resolution_time = incident_time + timedelta(minutes=random.randint(5, 60))
    return {
        "incident_id": incident_id,
        "severity": random.choice(["warning", "critical"]),
        "status": random.choice(["resolved", "investigating", "mitigated"]),
        "reported_at": incident_time.isoformat(),
        "resolved_at": resolution_time.isoformat() if random.random() > 0.4 else None,
        "duration_minutes": (resolution_time - incident_time).seconds // 60,
        "affected_components": [
            random.choice(["tower_3", "edge_agent_2", "regional_coordinator", "network_link_1"])
            for _ in range(random.randint(1, 3))
        ],
        "root_cause": random.choice([
            "High traffic load on TRX unit",
            "Network connectivity issue",
            "Agent process crash",
            "Memory leak in monitoring agent",
            "TRX overload — capacity exceeded",
        ]),
        "remediation_actions": [
            {
                "action": random.choice(["restart_agent", "reroute_traffic", "redeploy_agent"]),
                "timestamp": (incident_time + timedelta(minutes=random.randint(1, 10))).isoformat(),
                "success": True,
            }
        ],
        "impact": {
            "affected_towers": random.randint(1, 3),
            "affected_users": random.randint(100, 3000),
            "service_degradation_percent": round(random.uniform(5, 45), 2),
        },
    }
