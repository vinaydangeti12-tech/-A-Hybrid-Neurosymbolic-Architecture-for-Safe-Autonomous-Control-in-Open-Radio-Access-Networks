"""Action Agent — non-generative ML child agent (executes gate-approved commands).

A deterministic ADK ``BaseAgent`` (NOT an ``LlmAgent``): no language model. It
runs the ACT stage and executes ONLY actions the deterministic Safety Gate has
approved (read from session state). If the gate blocked the decision, nothing is
sent to the equipment — which is what guarantees no boundary-violating command
ever reaches hardware.
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from agents.regional_coordinator.edge_agents.ml_base import ml_event
from agents.regional_coordinator.edge_agents.action_agent.tools import (
    shutdown_trx_units,
    activate_backup_cells,
    isolate_failed_component,
)


class ActionMLAgent(BaseAgent):
    """ACT stage — executes ONLY gate-approved actions. Deterministic, no LLM."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        tower = state.get("tower_id", "tower_1")
        approved = bool(state.get("safety_approved", False))
        action = state.get("decision_action", "maintain_current_config")

        if not approved:
            result = {"executed": False, "reason": "safety_gate_blocked", "action": action}
            text = f"[Action] BLOCKED by Safety Gate — no command sent to equipment ({action})"
        elif action == "partial_trx_shutdown":
            result = shutdown_trx_units(tower, int(state.get("trx_to_shutdown", 3)))
            text = f"[Action] executed TRX shutdown -> {result.get('status')}"
        elif action in ("emergency_load_balancing", "proactive_load_balancing"):
            result = activate_backup_cells(tower, 2)
            text = f"[Action] executed load balancing -> {result.get('status')}"
        elif action in ("reroute_traffic", "restart_agent"):
            result = isolate_failed_component(tower, str(state.get("fault_type", "trx_unit")))
            text = f"[Action] executed self-heal -> {result.get('status')}"
        else:
            result = {"executed": False, "operation": "no_op", "action": action}
            text = f"[Action] no operation required ({action})"

        yield ml_event(self.name, text, {"action_result": result})


action_agent = ActionMLAgent(
    name="action_agent",
    description="Action Agent — non-generative actuator; executes only Safety-Gate-approved commands (ACT). No LLM.",
)
