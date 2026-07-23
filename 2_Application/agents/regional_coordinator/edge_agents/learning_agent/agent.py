"""Learning Agent — non-generative ML child agent (records outcomes, refines models).

A deterministic ADK ``BaseAgent`` (NOT an ``LlmAgent``): no language model. It
runs the LEARN stage — recording the outcome of the executed action so the
non-generative models (Isolation Forest / LSTM) can be refined — and never
controls hardware.
"""

from typing import AsyncGenerator

from google.adk.agents import BaseAgent
from google.adk.agents.invocation_context import InvocationContext
from google.adk.events import Event

from agents.regional_coordinator.edge_agents.ml_base import ml_event
from agents.regional_coordinator.edge_agents.learning_agent.tools import (
    record_action_outcome,
)


class LearningMLAgent(BaseAgent):
    """LEARN stage — records action outcomes for model refinement. No LLM."""

    async def _run_async_impl(self, ctx: InvocationContext) -> AsyncGenerator[Event, None]:
        state = ctx.session.state
        action = state.get("decision_action", "none")
        ar = state.get("action_result", {}) or {}
        success = bool(ar.get("success", ar.get("executed", False)))

        outcome = record_action_outcome(
            action_id=f"{state.get('tower_id', 'tower_1')}-{action}",
            action_type=action,
            success=success,
            metrics={"anomaly_score": state.get("anomaly_score"),
                     "predicted_load": state.get("predicted_load")},
        )
        text = (f"[Learning] recorded {action} -> signal={outcome['learning_signal']} "
                f"(queued_for_offline_retrain={outcome['queued_for_offline_retrain']})")
        yield ml_event(self.name, text, {"learning_result": outcome})


learning_agent = LearningMLAgent(
    name="learning_agent",
    description="Learning Agent — non-generative outcome recorder / model refiner (LEARN). No LLM.",
)
