"""
TRACE_v2 Dashboard Backend Server
Flask + Flask-SocketIO — no AWS, local-only.

REST endpoints + WebSocket streaming for the React dashboard.
Scenario endpoints allow activation of the 3 thesis evaluation scenarios.
"""

from __future__ import annotations

import os
import random
import sys
import threading
import time
from datetime import datetime

from timeutil import utcnow

if sys.platform == "win32":
    try:
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
        sys.stderr.reconfigure(encoding="utf-8", errors="replace")
    except Exception:
        pass

from flask import Flask, Response, jsonify, request, stream_with_context
from flask_cors import CORS
from flask_socketio import SocketIO, emit, join_room

from agent_bridge import AgentBridge
from agent_integration import agent_integration
from scenario_engine import activate_scenario, get_scenario_status, inject_fault, next_telemetry_point as scenario_next
from data_loader import load_real_series, load_synthetic_series, load_incidents, _ensure_extracted, _EXTRACT_DIR

app = Flask(__name__)
# Restrict cross-origin access to the local dashboard origins (override via env).
# CORS_ORIGINS="*" allows any origin — used when tunnelling via ngrok so a remote
# browser's WebSocket handshake (Origin = the ngrok URL) is accepted.
_cors_raw = os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173").strip()
_cors_origins = "*" if _cors_raw == "*" else [o.strip() for o in _cors_raw.split(",") if o.strip()]
CORS(app, origins=_cors_origins)
socketio = SocketIO(app, cors_allowed_origins=_cors_origins, async_mode="threading")

bridge = AgentBridge()
# region -> count of currently-subscribed clients. The stream loop emits to a
# region only while at least one client is subscribed; pruned on disconnect.
active_regions: dict = {}
# socket id -> set of regions it subscribed to, so disconnect can decrement.
_sid_regions: dict = {}
# Guards active_regions / _sid_regions: SocketIO handlers (per-client threads)
# and the stream loop all mutate these under threading async_mode.
_regions_lock = threading.Lock()


def _int_arg(name: str, default: int, lo: int | None = None, hi: int | None = None) -> int:
    """Parse an int query parameter safely; bad input falls back to the default."""
    try:
        value = int(request.args.get(name, default))
    except (TypeError, ValueError):
        value = default
    if lo is not None:
        value = max(lo, value)
    if hi is not None:
        value = min(hi, value)
    return value

# Print startup banner
print("\n" + "=" * 60)
print("  H-TRACE — Neurosymbolic O-RAN Control · Dashboard Backend")
print("=" * 60)
status = agent_integration.get_status()
print(f"  AI · Smart Manager (Principal) : {'OK' if status['principal_agent_available'] else 'Fallback'}")
print(f"  Google ADK                     : {'OK' if status['adk_available'] else 'Not loaded'}")
print(f"  Gemini (AI tier)               : {'OK' if status['gemini_available'] else 'Not available'}")
print(f"  ML Local Teams                 : Isolation Forest + LSTM")
print(f"  Symbolic Safety Gate           : Deterministic (0% false-pass)")
print(f"  Mode                           : {status['mode'].upper()}")
print("=" * 60 + "\n")


# ── Health & Telemetry ──────────────────────────────────────────────────────

@app.route("/api/health/<region>")
def get_health(region):
    return jsonify(bridge.get_system_health(region))


@app.route("/api/telemetry")
def get_telemetry():
    region = request.args.get("region", "region-IE-01")
    count = _int_arg("count", 100, lo=1, hi=2000)
    return jsonify(bridge.get_telemetry_series(region, count))


@app.route("/api/active-users/<region>")
def get_active_users(region):
    hist = bridge.get_users_history(region, 1)
    return jsonify(hist[-1] if hist else bridge.next_users_point(region))


# ── Issues ──────────────────────────────────────────────────────────────────

@app.route("/api/issues")
def get_issues():
    region = request.args.get("region", "region-IE-01")
    return jsonify(bridge.get_issues(region))


@app.route("/api/issues/create", methods=["POST"])
def force_create_issue():
    data = request.get_json(force=True, silent=True) or {}
    region = data.get("region", "region-IE-01")
    issue = bridge.force_create_issue(region, data.get("severity"), data.get("issue_type"))
    if issue:
        socketio.emit("issue", issue, room=region)
        return jsonify({"success": True, "issue": issue})
    return jsonify({"success": False, "error": "Could not create issue"}), 500


# ── Remediation ─────────────────────────────────────────────────────────────

@app.route("/api/remediation/trigger", methods=["POST"])
def trigger_remediation():
    data = request.get_json(force=True, silent=True) or {}
    issue_id = data.get("issueId")
    action = data.get("action")
    region = data.get("region", "region-IE-01")

    issues = bridge.get_issues(region)
    issue = next((i for i in issues if i.get("id") == issue_id), {
        "id": issue_id, "title": f"Issue {issue_id}", "severity": "medium",
        "suggestedAction": action or "restart_agent", "affectedTowers": ["Tower-1"],
        "activeAgent": "monitoring_agent",
    })

    agent_result = agent_integration.auto_remediate(issue, action)
    bridge_result, resolution = bridge.trigger_remediation(issue_id, action)
    resolution["agent_response"] = agent_result.get("agent_response")
    resolution["source"] = agent_result.get("source", "auto_heal")
    resolution["issueId"] = issue_id

    socketio.emit("resolution", resolution)
    return jsonify({
        "success": agent_result.get("success", True),
        "issueId": issue_id,
        "action": agent_result.get("operation", action),
        "timestamp": agent_result.get("timestamp", utcnow().isoformat()),
        "message": agent_result.get("message", "Remediation executed"),
        "agent_response": agent_result.get("agent_response"),
        "source": agent_result.get("source"),
    })


@app.route("/api/issue/analyze", methods=["POST"])
def analyze_issue():
    data = request.get_json(force=True, silent=True) or {}
    issue_id = data.get("issueId")
    region = data.get("region", "region-IE-01")
    issues = bridge.get_issues(region)
    issue = next((i for i in issues if i.get("id") == issue_id), data.get("issue", {}))
    if not issue:
        return jsonify({"success": False, "error": "Issue not found"}), 404
    analysis = agent_integration.analyze_issue(issue)
    return jsonify({"success": True, "issueId": issue_id, **analysis})


# ── Chat ────────────────────────────────────────────────────────────────────

@app.route("/api/chat", methods=["POST"])
def chat():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message", "") or "").strip()[:4000]   # bound size sent to the LLM
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400
    scenario = data.get("scenario", "")
    context  = data.get("context", "trace_agent_page")
    # Prefix the message with scenario context so the agent knows which RQ is active
    SCENARIO_LABELS = {
        "night_mode":   "[RQ1 — Night Mode / Scenario A active] ",
        "festival_mode":"[RQ2 — Festival Mode / Scenario B active] ",
        "self_healing": "[RQ3 — Self-Healing / Scenario C active] ",
    }
    prefixed = SCENARIO_LABELS.get(scenario, "") + message
    result = agent_integration.chat(prefixed, context)
    return jsonify(result)


@app.route("/api/chat/stream", methods=["POST"])
def chat_stream():
    data = request.get_json(force=True, silent=True) or {}
    message = (data.get("message", "") or "").strip()[:4000]   # bound size sent to the LLM
    if not message:
        return jsonify({"success": False, "error": "message is required"}), 400

    try:
        from gemini_service import gemini_service, GEMINI_AVAILABLE
        if GEMINI_AVAILABLE and gemini_service.is_available():
            def generate():
                import json as _json
                yield 'data: {"type":"start"}\n\n'
                full = ""
                for chunk in gemini_service.chat_stream(message):
                    full += chunk
                    yield f"data: {_json.dumps({'type':'chunk','content':chunk})}\n\n"
                yield f"data: {_json.dumps({'type':'end','full_response':full})}\n\n"
            return Response(stream_with_context(generate()), mimetype="text/event-stream",
                            headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})
    except Exception:
        pass

    result = agent_integration.chat(message)
    return jsonify(result)


# ── Scenarios ───────────────────────────────────────────────────────────────

@app.route("/api/scenario/activate", methods=["POST"])
def api_activate_scenario():
    """Activate one of the 3 thesis evaluation scenarios."""
    data = request.get_json(force=True, silent=True) or {}
    scenario = data.get("scenario", "baseline")
    allowed = {"baseline", "night_mode", "festival_mode", "self_healing"}
    if scenario not in allowed:
        return jsonify({"success": False, "error": f"scenario must be one of {allowed}"}), 400
    status = activate_scenario(scenario)
    socketio.emit("scenario_changed", status)
    return jsonify({"success": True, **status})


@app.route("/api/scenario/status")
def api_scenario_status():
    return jsonify(get_scenario_status())


@app.route("/api/scenario/inject_fault", methods=["POST"])
def api_inject_fault():
    data = request.get_json(force=True, silent=True) or {}
    result = inject_fault(data.get("fault_type", "cell_outage"))
    return jsonify(result)


# ── Dataset API ──────────────────────────────────────────────────────────────

@app.route("/api/dataset/overview")
def dataset_overview():
    """Return metadata about the loaded dataset."""
    available = _ensure_extracted()
    incidents = load_incidents() if available else []
    real_ids = list(range(1, 15))      # r1-r14
    synthetic_ids = list(range(1, 51)) # s1-s50 (the dataset ships 50 synthetic series)
    samples_per_series = 10738
    return jsonify({
        "available": available,
        "real_series": real_ids,
        "synthetic_series": synthetic_ids,
        "incidents_count": len(incidents),
        "samples_per_series": samples_per_series,
        "total_samples": samples_per_series * (len(real_ids) + len(synthetic_ids)),
        "sample_interval_seconds": 300,
        "duration_days": 37.3,
        "kpi_range": [0, 1000],
        "source": "Zenodo DOI:10.5281/zenodo.8147768",
    })


@app.route("/api/dataset/series/<series_id>")
def get_series(series_id: str):
    """
    Return a downsampled KPI series for charting.
    series_id: r1-r14 (real) or s1-s50 (synthetic)
    Query params: points (default 500), offset (default 0)
    """
    points = _int_arg("points", 500, lo=1, hi=2000)
    offset = _int_arg("offset", 0, lo=0)
    try:
        if series_id.startswith("r"):
            sid = int(series_id[1:])
            if not 1 <= sid <= 14:
                return jsonify({"error": "Series not found — real series are r1-r14"}), 404
            raw = load_real_series(sid)
        elif series_id.startswith("s"):
            sid = int(series_id[1:])
            if not 1 <= sid <= 50:
                return jsonify({"error": "Series not found — synthetic series are s1-s50"}), 404
            raw = load_synthetic_series(sid)
        else:
            return jsonify({"error": "Invalid series_id — use r1-r14 or s1-s50"}), 400
    except (ValueError, IndexError):
        return jsonify({"error": "Series not found"}), 404

    total = len(raw)
    offset = min(offset, total)
    segment = raw[offset:]
    step = max(1, len(segment) // points)
    downsampled = [
        {"t": ts, "v": round(v, 2), "idx": offset + i * step}
        for i, (ts, v) in enumerate(segment[::step])
    ][:points]

    incidents = load_incidents()
    anomaly_windows = [
        {"start": inc["start_sample"], "end": inc["end_sample"]}
        for inc in incidents
        if inc["series"] == series_id
    ]

    return jsonify({
        "series_id": series_id,
        "total_samples": total,
        "returned": len(downsampled),
        "data": downsampled,
        "anomaly_windows": anomaly_windows,
    })


@app.route("/api/dataset/incidents")
def dataset_incidents():
    """Return all labelled anomaly incidents."""
    return jsonify(load_incidents())


# ── Misc ─────────────────────────────────────────────────────────────────────

@app.route("/api/integration/status")
def get_integration_status():
    return jsonify(agent_integration.get_status())


@app.route("/api/resolutions")
def get_resolutions():
    region = request.args.get("region", "region-IE-01")
    limit = _int_arg("limit", 20, lo=1, hi=200)
    return jsonify(bridge.get_resolutions(region, limit))


@app.route("/api/agents/status")
def get_agent_status():
    return jsonify(bridge.get_agent_statuses())


@app.route("/api/demo/mode", methods=["POST"])
def set_demo_mode():
    data = request.get_json(force=True, silent=True) or {}
    result = bridge.set_demo_mode(data.get("enabled", True), data.get("auto_heal", True), data.get("interval", 10))
    return jsonify({"success": True, **result})


@app.route("/api/demo/status")
def get_demo_status():
    return jsonify(bridge.get_demo_status())


# ── WebSocket ────────────────────────────────────────────────────────────────

@socketio.on("connect")
def on_connect():
    emit("connected", {"status": "connected"})


@socketio.on("disconnect")
def on_disconnect():
    # Decrement this client's region subscriptions; drop a region from the
    # stream loop once no client remains subscribed to it.
    with _regions_lock:
        for region in _sid_regions.pop(request.sid, ()):
            remaining = active_regions.get(region, 0) - 1
            if remaining > 0:
                active_regions[region] = remaining
            else:
                active_regions.pop(region, None)


@socketio.on("subscribe")
def on_subscribe(data):
    region = data.get("region", "region-IE-01")
    join_room(region)
    with _regions_lock:
        subs = _sid_regions.setdefault(request.sid, set())
        if region not in subs:
            subs.add(region)
            active_regions[region] = active_regions.get(region, 0) + 1
    emit("telemetry", scenario_next(region))
    emit("activeUsers", bridge.next_users_point(region))
    health = bridge.get_system_health(region)
    emit("health", {"score": health["score"], "status": health["status"]})


def _auto_heal_task(region: str, heal_id: str):
    """Run auto-remediation (which may call Gemini) OFF the stream loop so a slow
    network call never stalls live telemetry for connected clients."""
    issues_list = bridge.get_issues(region)
    issue = next((i for i in issues_list if i.get("id") == heal_id), None)
    if not issue:
        return
    try:
        ar = agent_integration.auto_remediate(issue, issue.get("suggestedAction"))
        _, resolution = bridge.trigger_remediation(heal_id, issue.get("suggestedAction"))
        resolution["agent_response"] = ar.get("agent_response")
        resolution["source"] = ar.get("source", "auto_heal")
        resolution["issueId"] = heal_id
        resolution["auto_healed"] = True
        socketio.emit("resolution", resolution, room=region)
    except Exception as exc:
        # If remediation raises, the issue was flagged healing=True by
        # check_auto_heal and would otherwise be skipped forever (until the
        # 900s cleanup). Clear the flag so it can be retried on a later tick.
        print(f"[app] auto-heal failed for {heal_id}: {exc!r}", flush=True)
        bridge.clear_healing(heal_id)


def _stream_loop():
    issue_counters: dict = {}
    while True:
        socketio.sleep(1)
        now = int(time.time())

        with _regions_lock:
            active_snapshot = list(active_regions.keys())
        # Drop per-region counters for regions no clients are subscribed to
        # anymore, so this dict can't grow without bound over a long run.
        for stale in [r for r in issue_counters if r not in active_snapshot]:
            issue_counters.pop(stale, None)

        for region in active_snapshot:
            # Always route through scenario engine — it reads from the real
            # Zenodo dataset for all scenarios (baseline uses s1 synthetic,
            # night_mode/self_healing use r1 real, festival uses s1×5).
            pt = scenario_next(region)
            socketio.emit("telemetry", pt, room=region)

            if now % 2 == 0:
                socketio.emit("activeUsers", bridge.next_users_point(region), room=region)
            if now % 5 == 0:
                h = bridge.get_system_health(region)
                socketio.emit("health", {"score": h["score"], "status": h["status"]}, room=region)
            if now % 10 == 0:
                socketio.emit("scenario_status", get_scenario_status(), room=region)

            if bridge.demo_mode:
                issue_counters[region] = issue_counters.get(region, 0) + 1
                if issue_counters[region] >= bridge.demo_interval:
                    issue_counters[region] = 0
                    if random.random() < 0.65:
                        issue = bridge.maybe_new_issue(region)
                        if issue:
                            socketio.emit("issue", issue, room=region)

                heal_id = bridge.check_auto_heal(region)
                if heal_id:
                    # Dispatch off-loop: auto_remediate may call Gemini (slow).
                    socketio.start_background_task(_auto_heal_task, region, heal_id)
            else:
                if now % 30 == 0:
                    issue = bridge.maybe_new_issue(region)
                    if issue:
                        socketio.emit("issue", issue, room=region)


if __name__ == "__main__":
    socketio.start_background_task(_stream_loop)
    host = os.getenv("HOST", "127.0.0.1")
    try:
        port = int(os.getenv("PORT", "8000"))
    except ValueError:
        port = 8000
    debug = os.getenv("FLASK_DEBUG", "0") == "1"
    is_local = host in ("127.0.0.1", "localhost", "::1")
    # Safety: the Werkzeug debugger is a remote-code-execution surface. Never
    # allow it when the server is bound to a non-loopback interface.
    if debug and not is_local:
        print("[app] Refusing FLASK_DEBUG on a non-local host — disabling debug.")
        debug = False
    if not is_local:
        print("[app] WARNING: bound to a non-local host on the Werkzeug dev "
              "server. Use a production WSGI server (e.g. gunicorn -k gevent) "
              "for any real deployment.")
    print(f"Starting TRACE_v2 backend on http://{host}:{port}")
    # NOTE: this uses the Werkzeug dev server (fine for the demo / local use).
    # For production, serve via a WSGI server, e.g. gunicorn -k gevent.
    socketio.run(app, host=host, port=port, debug=debug, use_reloader=False,
                 allow_unsafe_werkzeug=True)
