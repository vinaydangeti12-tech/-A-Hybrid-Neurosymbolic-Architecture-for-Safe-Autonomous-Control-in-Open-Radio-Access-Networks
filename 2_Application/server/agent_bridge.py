"""
Agent Bridge for TRACE_v2
Adapts agent tool outputs for the Flask dashboard server.
No AWS/Bedrock — uses local tools + optional Gemini.
"""

from __future__ import annotations

import os
import random
import sys
import threading
import time
from collections import deque
from datetime import datetime, timedelta

from timeutil import utcnow
from typing import Deque, Dict, List, Optional
from uuid import uuid4

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from dotenv import load_dotenv
load_dotenv()

# ── Import agent tools (with fallbacks) ───────────────────────────────────────
try:
    _AGENTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
    if _AGENTS_DIR not in sys.path:
        sys.path.insert(0, _AGENTS_DIR)
    from agents.principal_agent.tools.health_monitor import check_system_health, get_agent_status as _get_agent_status
    from agents.principal_agent.tools.dashboard import generate_incident_report, get_system_metrics
    from agents.principal_agent.tools.remediation import restart_agent, redeploy_agent, reroute_traffic
    TOOLS_AVAILABLE = True
except ImportError as _e:
    TOOLS_AVAILABLE = False
    def check_system_health(): return {"overall_status": "healthy", "components": {}, "metrics": {}}
    def _get_agent_status(n): return {"status": "active", "uptime_seconds": 3600, "metrics": {}, "resource_usage": {}}
    def generate_incident_report(i): return {"incident_id": i, "root_cause": "Network Anomaly", "status": "Active", "affected_components": [f"Tower-{random.randint(1,10)}"], "remediation_actions": [{"action": "restart_agent"}]}
    def get_system_metrics(t="all"): return {"energy_metrics": {"current_consumption_kwh": random.uniform(80, 140), "peak_consumption_kwh": 160}, "traffic_metrics": {"current_traffic_normalised": random.uniform(0.3, 0.8), "peak_traffic_normalised": 0.95, "total_connections": random.randint(5000, 25000)}, "health_metrics": {"incidents_count": random.randint(0, 3)}}
    def restart_agent(n, reason=""): return {"success": True, "operation": "restart_agent", "message": f"Agent {n} restarted", "timestamp": utcnow().isoformat()}
    def redeploy_agent(n, v="latest"): return {"success": True, "operation": "redeploy_agent", "message": f"Agent {n} redeployed", "timestamp": utcnow().isoformat()}
    def reroute_traffic(src, dst, percentage=50): return {"success": True, "operation": "reroute_traffic", "message": f"Rerouted {percentage}% {src}→{dst}", "timestamp": utcnow().isoformat()}

from gemini_service import gemini_service, GEMINI_AVAILABLE


def _clamp(v: float, lo: float, hi: float) -> float:
    return max(lo, min(hi, v))


class AgentBridge:
    """Maps agent tool outputs to dashboard-friendly data structures."""

    SCORE_RANGES = {"healthy": (92, 98), "degraded": (68, 84), "critical": (44, 65)}
    REGIONS = ["region-IE-01", "region-IE-02", "region-DE-01"]
    AGENT_PIPELINE = ["Anomaly Detector", "Traffic Predictor", "Local Decision", "Action", "Learning"]
    REMEDIATION_ACTIONS = ["restart_agent", "redeploy_agent", "reroute_traffic"]

    ISSUE_TYPES = [
        {"title": "High Traffic Load",         "description": "Network traffic exceeding optimal levels",      "action": "reroute_traffic"},
        {"title": "Network Congestion",         "description": "Multiple towers reporting bandwidth saturation","action": "reroute_traffic"},
        {"title": "Energy Spike Detected",      "description": "Power consumption above threshold",            "action": "restart_agent"},
        {"title": "TRX Overload",               "description": "Transceiver capacity exceeded",               "action": "reroute_traffic"},
        {"title": "Agent Process Crash",        "description": "Edge agent process terminated unexpectedly",   "action": "redeploy_agent"},
        {"title": "Memory Leak Detected",       "description": "Gradual memory increase in monitoring agent",  "action": "restart_agent"},
        {"title": "Latency Spike",              "description": "Response times exceeding SLA thresholds",      "action": "reroute_traffic"},
        {"title": "Sleeping Cell Detected",     "description": "Cell not responding — potential hardware fault","action": "restart_agent"},
        {"title": "Signal Interference",        "description": "RF interference affecting coverage area",      "action": "reroute_traffic"},
        {"title": "Capacity Warning",           "description": "Tower approaching maximum user capacity limit","action": "reroute_traffic"},
    ]

    def __init__(self) -> None:
        self._lock = threading.Lock()
        self._telemetry: Dict[str, Deque[Dict]] = {}
        self._users: Dict[str, Deque[Dict]] = {}
        self._issues: Dict[str, Dict] = {}
        self._resolutions: Deque[Dict] = deque(maxlen=200)
        self._telemetry_idx = 0

        # Demo mode — on by default
        self.demo_mode = True
        self.auto_heal = True
        self.auto_heal_delay = 30
        self.demo_interval = 10

    # ── Buffers ────────────────────────────────────────────────────────────────
    def _buf(self, region: str) -> None:
        if region not in self._telemetry:
            self._telemetry[region] = deque(maxlen=600)
        if region not in self._users:
            self._users[region] = deque(maxlen=600)

    # ── Health ─────────────────────────────────────────────────────────────────
    def get_system_health(self, region: str) -> Dict:
        raw = check_system_health()
        lo, hi = self.SCORE_RANGES.get(raw.get("overall_status", "healthy"), (80, 95))
        score = round(random.uniform(lo, hi), 1)
        return {
            "region": region,
            "score": score,
            "status": raw.get("overall_status", "healthy").title(),
            "details": raw,
            "generated_at": utcnow().isoformat(),
        }

    # ── Telemetry ──────────────────────────────────────────────────────────────
    def _build_telemetry(self, region: str, seconds_back: int = 0) -> Dict:
        metrics = get_system_metrics("all")
        energy = metrics.get("energy_metrics", {})
        traffic = metrics.get("traffic_metrics", {})
        health = metrics.get("health_metrics", {})

        peak_e = energy.get("peak_consumption_kwh") or 160
        peak_t = traffic.get("peak_traffic_normalised") or 0.95
        energy_pct = _clamp((energy.get("current_consumption_kwh", 100) / peak_e) * 100, 0, 100)
        congestion_pct = _clamp((traffic.get("current_traffic_normalised", 0.5) / peak_t) * 100, 0, 100)
        anomaly_base = health.get("incidents_count", 0) * 16
        anomaly = _clamp(anomaly_base + random.uniform(4, 28), 0, 100)

        ts = (utcnow() - timedelta(seconds=seconds_back)).isoformat()
        return {
            "region": region,
            "timestamp": ts,
            "energy": round(energy_pct, 2),
            "congestion": round(congestion_pct, 2),
            "anomaly_score": round(anomaly, 2),
            "traffic_load": round(_clamp(congestion_pct + random.uniform(-4, 6), 0, 100), 2),
            "trx_utilization": round(_clamp(random.gauss(75, 7), 30, 100), 2),
            "power_draw": round(random.uniform(75, 130), 2),
        }

    def _build_users(self, region: str, seconds_back: int = 0) -> Dict:
        metrics = get_system_metrics("traffic")
        conns = metrics.get("traffic_metrics", {}).get("total_connections", random.randint(5000, 25000))
        active = int(conns * random.uniform(0.60, 0.95))
        ts = (utcnow() - timedelta(seconds=seconds_back)).isoformat()
        return {
            "region": region,
            "timestamp": ts,
            "activeUsers": active,
            "towerCluster": f"Tower-{random.randint(1, 8)}",
            "lastOptimization": random.choice(["Load Balancing", "TRX Optimisation", "Energy Saver", "None"]),
            "surgeDetected": random.random() > 0.92,
        }

    def next_telemetry_point(self, region: str) -> Dict:
        self._buf(region)
        pt = self._build_telemetry(region)
        with self._lock:
            self._telemetry[region].append(pt)
        return pt

    def next_users_point(self, region: str) -> Dict:
        self._buf(region)
        pt = self._build_users(region)
        with self._lock:
            self._users[region].append(pt)
        return pt

    def get_telemetry_series(self, region: str, count: int = 100) -> List[Dict]:
        self._buf(region)
        with self._lock:
            hist = list(self._telemetry[region])
        missing = count - len(hist)
        for i in range(missing, 0, -1):
            pt = self._build_telemetry(region, seconds_back=i)
            with self._lock:
                self._telemetry[region].append(pt)
        with self._lock:
            return list(self._telemetry[region])[-count:]

    def get_users_history(self, region: str, count: int = 60) -> List[Dict]:
        self._buf(region)
        with self._lock:
            hist = list(self._users[region])
        missing = count - len(hist)
        for i in range(missing, 0, -1):
            pt = self._build_users(region, seconds_back=i)
            with self._lock:
                self._users[region].append(pt)
        with self._lock:
            return list(self._users[region])[-count:]

    # ── Issues ─────────────────────────────────────────────────────────────────
    def _current_issues(self) -> Dict:
        with self._lock:
            return dict(self._issues)

    def _cleanup(self) -> None:
        now = time.time()
        with self._lock:
            for iid, issue in list(self._issues.items()):
                age = now - issue.get("created_at", 0)
                if issue.get("status") == "Resolved" and issue.get("resolved_at", 0) < now - 120:
                    del self._issues[iid]
                elif issue.get("status") != "Resolved" and age > 900:
                    del self._issues[iid]

    def get_issues(self, region: str) -> List[Dict]:
        self._cleanup()
        active = [i for i in self._current_issues().values()
                  if i.get("region") == region and i.get("status") != "Resolved"]
        return [self._serialize(i) for i in active]

    def maybe_new_issue(self, region: str) -> Optional[Dict]:
        self._cleanup()
        count = sum(1 for i in self._current_issues().values()
                    if i.get("region") == region and i.get("status") != "Resolved")
        if count >= (5 if self.demo_mode else 3):
            return None
        if random.random() < (0.6 if self.demo_mode else 0.25):
            return self._create_issue(region)
        return None

    def force_create_issue(self, region: str, severity: Optional[str] = None,
                           issue_type: Optional[str] = None) -> Optional[Dict]:
        self._cleanup()
        used = {i.get("title") for i in self._current_issues().values() if i.get("status") != "Resolved"}
        available = [t for t in self.ISSUE_TYPES if t["title"] not in used]
        if not available:
            # Clear one resolved issue and try again
            with self._lock:
                resolved = [k for k, v in self._issues.items() if v.get("status") == "Resolved"]
                if resolved:
                    del self._issues[resolved[0]]
            available = self.ISSUE_TYPES[:]

        if issue_type:
            sel = next((t for t in available if issue_type.lower() in t["title"].lower()), available[0])
        else:
            sel = random.choice(available)

        return self._create_issue(region, issue_type_override=sel, severity_override=severity)

    def _create_issue(self, region: str, issue_type_override=None, severity_override=None) -> Optional[Dict]:
        used = {i.get("title") for i in self._current_issues().values() if i.get("status") != "Resolved"}
        available = [t for t in self.ISSUE_TYPES if t["title"] not in used]
        if not available:
            return None

        sel = issue_type_override or random.choice(available)
        sev = severity_override or random.choice(["critical", "high", "medium"])
        iid = f"issue-{uuid4().hex[:8]}"
        incident = generate_incident_report(iid.upper())

        # NOTE: no synchronous Gemini call here. _create_issue runs inside the
        # 1-second SocketIO stream loop; a blocking network call would freeze
        # telemetry for every client. Deterministic text is used instead, and
        # AI enrichment happens lazily on the /api/issue/analyze request path.
        ai_analysis = None

        issue = {
            "id": iid,
            "region": region,
            "title": sel["title"],
            "severity": sev,
            "description": sel["description"],
            "impactScore": random.randint(55, 98),
            "affectedTowers": incident.get("affected_components", [f"Tower-{random.randint(1,10)}"]),
            "status": "Active",
            "agentTrace": self.AGENT_PIPELINE,
            "activeAgent": random.choice(self.AGENT_PIPELINE[:3]),
            "suggestedAction": sel["action"],
            "detailedAnalysis": ai_analysis or f"The ML Local Teams (Isolation Forest) SPOTted elevated risk on {incident.get('affected_components', ['tower_1'])[0]}; the Smart Manager is supervising remediation.",
            "remediationSteps": [a.get("action", "review_telemetry") for a in incident.get("remediation_actions", [])] or ["Analyse telemetry", "Execute remediation", "Verify stability"],
            "agentLogs": [
                {"timestamp": (utcnow() - timedelta(seconds=i * 15)).isoformat(), "agent": a, "message": f"{a} reviewed incident {iid}"}
                for i, a in enumerate(self.AGENT_PIPELINE)
            ],
            "created_at": time.time(),
        }
        with self._lock:
            self._issues[iid] = issue
        return self._serialize(issue)

    @staticmethod
    def _serialize(issue: Dict) -> Dict:
        out = dict(issue)
        out.pop("created_at", None)
        return out

    # ── Auto-heal check ────────────────────────────────────────────────────────
    def check_auto_heal(self, region: str) -> Optional[str]:
        if not self.auto_heal:
            return None
        now = time.time()
        with self._lock:
            for iid, issue in self._issues.items():
                if issue.get("status") == "Resolved" or issue.get("region") != region:
                    continue
                # Skip issues already being healed — auto_remediate may call a
                # slow Gemini request, so without this flag the 1-second stream
                # loop would re-dispatch the SAME issue every tick, spawning
                # duplicate background tasks, Gemini calls and resolution emits.
                if issue.get("healing"):
                    continue
                if now - issue.get("created_at", now) >= self.auto_heal_delay:
                    issue["healing"] = True
                    return iid
        return None

    def clear_healing(self, issue_id: str) -> None:
        """Reset the in-progress 'healing' flag so a failed auto-heal can retry."""
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue:
                issue.pop("healing", None)

    # ── Remediation ────────────────────────────────────────────────────────────
    def trigger_remediation(self, issue_id: str, action: Optional[str] = None):
        with self._lock:
            issue = self._issues.get(issue_id)
            if issue:
                issue["status"] = "Resolved"
                issue["resolved_at"] = time.time()

        action = action if action in self.REMEDIATION_ACTIONS else "restart_agent"
        target = (issue or {}).get("activeAgent", "monitoring_agent")

        if action == "redeploy_agent":
            result = redeploy_agent(target)
        elif action == "reroute_traffic":
            # `or [...]` also covers an empty list, so towers[0]/[-1] can't IndexError.
            towers = (issue or {}).get("affectedTowers") or ["Tower-1", "Tower-2"]
            result = reroute_traffic(towers[0], towers[-1], random.randint(30, 70))
        else:
            result = restart_agent(target)

        resolution = self._build_resolution(issue, result)
        with self._lock:
            self._resolutions.append(resolution)
        return result, resolution

    def _build_resolution(self, issue: Optional[Dict], result: Dict) -> Dict:
        title = issue.get("title") if issue else "Ad-hoc remediation"
        region = issue.get("region") if issue else random.choice(self.REGIONS)
        return {
            "id": f"res-{uuid4().hex[:6]}",
            "region": region,
            "timestamp": utcnow().isoformat(),
            "title": "Automated Remediation Completed",
            "summary": f"{title} resolved via {result.get('operation', 'action')}",
            "initiatingAgent": (issue or {}).get("activeAgent", "Smart Manager"),
            "actions": [result.get("message", "Remediation executed"), "Stability verification completed"],
            "rollbackStatus": "Available" if result.get("success") else "Manual Review",
            "confidenceScore": f"{random.randint(84, 99)}%",
        }

    def get_resolutions(self, region: str, limit: int = 20) -> List[Dict]:
        with self._lock:
            items = [r for r in self._resolutions if r.get("region") == region]
        if not items:
            incident = generate_incident_report(f"HIST-{uuid4().hex[:4]}".upper())
            items = [{
                "id": f"res-{uuid4().hex[:6]}",
                "region": region,
                "timestamp": utcnow().isoformat(),
                "title": "Historical Remediation",
                "summary": incident.get("root_cause", "Stability event") + " mitigated",
                "initiatingAgent": random.choice(self.AGENT_PIPELINE),
                "actions": ["Applied policy fix", "Verified KPIs"],
                "rollbackStatus": "Available",
                "confidenceScore": f"{random.randint(80, 97)}%",
            } for _ in range(3)]
        return list(reversed(items[-limit:]))

    def get_agent_statuses(self) -> List[Dict]:
        names = ["principal_agent", "regional_coordinator", "monitoring_agent",
                 "prediction_agent", "decision_xapp_agent", "action_agent", "learning_agent"]
        statuses = []
        for n in names:
            d = _get_agent_status(n)
            statuses.append({
                "name": n.replace("_", " ").title(),
                "status": d.get("status", "active"),
                "uptime": f"{d.get('uptime_seconds', 0) // 3600}h",
                "metrics": d.get("metrics", {}),
            })
        return statuses

    def set_demo_mode(self, enabled: bool, auto_heal: bool = True, interval: int = 10) -> Dict:
        self.demo_mode = enabled
        self.auto_heal = auto_heal
        self.demo_interval = interval
        return {"demo_mode": enabled, "auto_heal": auto_heal, "demo_interval": interval}

    def get_demo_status(self) -> Dict:
        active = sum(1 for i in self._current_issues().values() if i.get("status") != "Resolved")
        return {"demo_mode": self.demo_mode, "auto_heal": self.auto_heal,
                "demo_interval": self.demo_interval, "active_issues_count": active}
