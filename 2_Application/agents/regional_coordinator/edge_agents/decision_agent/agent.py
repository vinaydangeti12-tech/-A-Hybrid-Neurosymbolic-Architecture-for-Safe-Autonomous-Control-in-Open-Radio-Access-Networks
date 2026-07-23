"""Decision Agent (xApp) — non-generative ML child agent (policy + Safety Gate).

A deterministic ADK ``BaseAgent`` (NOT an ``LlmAgent``): no language model in
this real-time path. It runs the DECIDE stage — turning the Isolation-Forest and
LSTM outputs into ONE structured action and screening it through the real
deterministic Safety Gate — then writes the gate-validated decision to session
state for the Action agent. There is no "final say" here: only a gate-approved
action proceeds.
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from agents.regional_coordinator.edge_agents.ml_base import ml_event
from agents.regional_coordinator.edge_agents.decision_agent.tools import (
    evaluate_energy_policy,
    evaluate_congestion_policy,
    evaluate_healing_policy,
)


class DecisionMLAgent(BaseAgent):
    """DECIDE stage — deterministic policy + Safety Gate. No LLM."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        tower = state.get("tower_id", "tower_1")
        intent = state.get("intent", "save_energy")
        pred = float(state.get("predicted_load", 150.0))
        fault = bool(state.get("fault_active", False))

        if fault:
            res = evaluate_healing_policy(state.get("fault_type", "trx_failure"), [tower])
            approved, action, gate = res["safety_gate_cleared"], res["decision"], res["safety_gate"]
        elif intent == "max_capacity":
            res = evaluate_congestion_policy(tower, float(state.get("surge_probability", 0.0)), pred / 1000.0)
            approved, action, gate = res["safety_validated"], res["strategy"], res["safety_gate"]
            state["trx_to_shutdown"] = 0
        else:
            res = evaluate_energy_policy(tower, {"forecasts": [{"predicted_kpi": pred}],
                                                 "low_traffic_window_active": pred < 200})
            approved, action, gate = res["safety_validated"], res["decision"], res["safety_gate"]
            state["trx_to_shutdown"] = res.get("trx_to_shutdown", 0)

        delta = {
            "decision_result": res,
            "decision_action": action,
            "safety_approved": bool(approved),
            "safety_gate": gate,
        }
        text = (f"[Decision · Safety Gate {'APPROVED' if approved else 'BLOCKED'}] "
                f"action={action} reasons={gate.get('reasons')}")
        yield ml_event(self.name, text, delta)


decision_xapp_agent = DecisionMLAgent(
    name="decision_xapp_agent",
    description="Decision xApp Agent — non-generative policy arbitration + deterministic Safety Gate (DECIDE). No LLM.",
)
