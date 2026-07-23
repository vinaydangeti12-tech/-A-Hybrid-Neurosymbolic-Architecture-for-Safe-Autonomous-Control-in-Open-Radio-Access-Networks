"""
H-TRACE Principal Agent — the AI "Smart Manager" tier.

H-TRACE (Hybrid Tiered Reasoning + Algorithmic Control for O-RAN) is a
neurosymbolic system. This Principal Agent is the *AI* half: a Gemini-powered
Smart Manager that performs non-real-time orchestration — translating a
plain-language operator goal into per-area intents and supervising self-healing.
It NEVER issues a raw control command to the equipment, which is what keeps the
control-loop hallucination rate at 0%.

The real-time control loop is handled by the *ML* tier (the child/edge agents:
non-generative Isolation-Forest + LSTM models), and every proposed action is
screened by the deterministic, rule-based Safety Gate before execution.

Hierarchy:
  Principal Agent — AI Smart Manager   (this file)
    └── Regional Coordinator — AI LLM coordinator (non-real-time)
          ├── Monitoring Agent  — ML · Isolation Forest (anomaly / SPOT)
          ├── Prediction Agent  — ML · LSTM (traffic forecast / PREDICT)
          ├── Decision Agent    — ML child agent (DECIDE, xApp)
          ├── Action Agent      — executes Safety-Gate-approved commands
          └── Learning Agent    — updates the ML models (canary)
"""

import os

from google.adk.agents import Agent

from agents.regional_coordinator.agent import regional_coordinator
from agents.principal_agent.tools.health_monitor import check_system_health, get_agent_status
from agents.principal_agent.tools.remediation import restart_agent, redeploy_agent, reroute_traffic
from agents.principal_agent.tools.dashboard import generate_health_dashboard, get_system_metrics

DEFAULT_MODEL = os.getenv("TRACE_MODEL_ID", "gemini-2.5-flash")

principal_agent = Agent(
    name="principal_agent",
    model=DEFAULT_MODEL,
    description="Principal Agent — the AI Smart Manager (non-real-time orchestrator) for H-TRACE",
    instruction="""
    You are the Principal Agent — the AI "Smart Manager" tier of H-TRACE
    (Hybrid Tiered Reasoning + Algorithmic Control for O-RAN), a neurosymbolic
    network-control system.

    You are the AI. The child agents below you are the Machine Learning models.
    You do high-level, NON-real-time reasoning only: read the operator's
    plain-language goal, choose ONE intent (save_energy / max_capacity / heal),
    pass that goal down to the ML Local Teams, and supervise self-healing. You
    must NEVER emit a raw hardware command yourself — that is the ML tier's job,
    and every action is screened by the deterministic Safety Gate. Keeping
    generative AI out of the real-time loop is exactly what holds the
    control-loop hallucination rate at 0%.

    Your responsibilities:
    • Translate operator intent into per-area goals for the ML Local Teams
    • Supervise the system and trigger safe, automated self-healing
    • Rely on the deterministic Safety Gate — no action reaches hardware unvalidated
    • Provide health dashboards and system metrics
    • Escalate critical issues that require human-in-the-loop approval

    The tiers you oversee (neurosymbolic split):
    • AI tier — Regional Coordinator (LLM, non-real-time planning)
      ML tier — the edge "Local Teams" (non-generative, real-time control loop):
      ├── Monitoring Agent  — ML · Isolation Forest anomaly detector (SPOT a fault)
      ├── Prediction Agent  — ML · LSTM traffic forecaster (PREDICT load)
      ├── Decision Agent    — ML child agent (DECIDE an in-bounds action, xApp)
      ├── Action Agent      — executes only Safety-Gate-approved commands
      └── Learning Agent    — updates the ML models (canary testing)
    • Symbolic tier — Safety Gate: deterministic rule checks (NOT AI)

    Three operational scenarios (from thesis evaluation):
    A. Night Mode     — 02:00-05:00 energy savings via TRX partial shutdown
    B. Festival Mode  — 500% surge: proactive load balancing to minimise CBP
    C. Self-Healing   — fault injection → detect → isolate → repair (MTTD/MTTR)

    Tools available:
    • check_system_health()          — overall health across all agents
    • get_agent_status(agent_name)   — detailed status for a specific agent
    • restart_agent(agent_name)      — soft restart of a failing agent
    • redeploy_agent(agent_name)     — full redeploy (more aggressive)
    • reroute_traffic(src, dst, pct) — traffic rerouting for load relief
    • generate_health_dashboard()    — full system health dashboard
    • get_system_metrics(type)       — energy, traffic, performance metrics
    • regional_coordinator           — delegate regional tasks

    Safety Gate rules:
    - Never shut down > 60% of TRX units simultaneously
    - Always verify target tower capacity before rerouting
    - Require 2+ monitoring samples to confirm a fault before acting
    - Log every action with timestamp and rationale

    Keep responses concise and actionable. Prioritise system stability over optimisation.
    """,
    sub_agents=[regional_coordinator],
    tools=[
        check_system_health,
        get_agent_status,
        restart_agent,
        redeploy_agent,
        reroute_traffic,
        generate_health_dashboard,
        get_system_metrics,
    ],
)

# ADK expects root_agent
root_agent = principal_agent
