"""
Regional Coordinator — AI tier (the LLM coordinator of H-TRACE).

Sits between the Principal Agent (AI Smart Manager) and the ML "Local Team"
(the edge child agents). It does non-real-time planning only: it takes the
Smart Manager's per-area goal and dispatches it to the non-generative ML models
that run the real-time control loop. It never bypasses the deterministic
Safety Gate.

Workflows (the ML Local Team pipeline):
  Energy Optimisation  (Sequential): Monitor → Predict → Decide → Act → Learn
  Congestion Mgmt      (Sequential): Predict → Decide → Act
"""

import os

from google.adk.agents import Agent, SequentialAgent
from google.adk.tools.agent_tool import AgentTool

from agents.regional_coordinator.edge_agents.monitoring_agent.agent import monitoring_agent
from agents.regional_coordinator.edge_agents.prediction_agent.agent import prediction_agent
from agents.regional_coordinator.edge_agents.decision_agent.agent import decision_xapp_agent
from agents.regional_coordinator.edge_agents.action_agent.agent import action_agent
from agents.regional_coordinator.edge_agents.learning_agent.agent import learning_agent
from agents.regional_coordinator.tools.telemetry_aggregator import aggregate_telemetry, get_regional_metrics
from agents.regional_coordinator.tools.policy_enforcer import enforce_policy, validate_action
from agents.regional_coordinator.tools.load_balancer import balance_load, get_tower_status


# Sequential pipeline: Scenario A — Night Mode energy optimisation
energy_optimisation_workflow = SequentialAgent(
    name="energy_optimisation_workflow",
    description="Sequential pipeline: Monitoring → Prediction → Decision → Action → Learning",
    sub_agents=[
        monitoring_agent,
        prediction_agent,
        decision_xapp_agent,
        action_agent,
        learning_agent,
    ],
)

# Congestion management uses AgentTools to avoid sub_agent parent conflicts
congestion_management_workflow = Agent(
    name="congestion_management_workflow",
    model=os.getenv("TRACE_MODEL_ID", "gemini-2.5-flash"),
    description="Congestion Management — Scenario B Festival Mode surge response",
    instruction="""
    Handle traffic surges and congestion events.

    Workflow:
    1. Call prediction_agent to detect surge probability
    2. Call decision_xapp_agent to determine load-balancing strategy
    3. Call action_agent to activate backup cells / reroute traffic
    """,
    tools=[
        AgentTool(prediction_agent),
        AgentTool(decision_xapp_agent),
        AgentTool(action_agent),
    ],
)


regional_coordinator = Agent(
    name="regional_coordinator",
    model=os.getenv("TRACE_MODEL_ID", "gemini-2.5-flash"),
    description="Regional Coordinator — AI LLM coordinator for the region-IE-01 ML Local Team",
    instruction="""
    You are the Regional Coordinator for H-TRACE — the AI (LLM) coordinator for
    region-IE-01. You do non-real-time planning only; the real-time control loop
    is run by the Machine Learning child agents you dispatch to.

    You manage a cluster of 10 O-RAN towers and coordinate the ML "Local Team"
    of 5 edge agents (non-generative models, so they cannot hallucinate):
    • Monitoring (Isolation Forest), Prediction (LSTM), Decision (xApp), Action, Learning

    Your responsibilities:
    1. Aggregate telemetry from all 10 towers every cycle
    2. Enforce ADK safety policies before any control action
    3. Orchestrate energy optimisation (Night Mode) via energy_optimisation_workflow
    4. Orchestrate congestion management (Festival Mode) via congestion_management_workflow
    5. Report regional health and incidents to the Principal Agent

    Tools:
    • aggregate_telemetry(tower_ids)    — aggregate KPIs from multiple towers
    • get_regional_metrics(metric)      — traffic, energy, performance metrics
    • enforce_policy(action, params)    — Safety Gate policy check
    • validate_action(type, tower, val) — quick safety validation
    • balance_load(towers, strategy)    — load-balancing recommendation
    • get_tower_status(tower_id)        — current tower health

    Escalate to Principal Agent when:
    - More than 2 towers simultaneously degraded
    - Self-healing fails after 2 attempts
    - Safety Gate blocks a required action

    Target KPIs: 30-40% energy saving (Night Mode), CBP < 0.01 (Festival Mode), MTTR < 5 min.
    """,
    sub_agents=[
        energy_optimisation_workflow,
        congestion_management_workflow,
    ],
    tools=[
        aggregate_telemetry,
        get_regional_metrics,
        enforce_policy,
        validate_action,
        balance_load,
        get_tower_status,
    ],
)
